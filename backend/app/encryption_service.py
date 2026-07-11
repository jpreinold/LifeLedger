import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import (
    RECORD_ENCRYPTION_DISABLED,
    RECORD_ENCRYPTION_KMS,
    RECORD_ENCRYPTION_LOCAL,
    Settings,
    get_settings,
)
from app.security_audit import user_hash

ENCRYPTION_VERSION = 1
PROTECTED_STORAGE_NOT_CONFIGURED = "Protected record storage is not configured for this environment."
PROTECTED_STORAGE_UNAVAILABLE = "Protected record storage is temporarily unavailable."


class KmsClient(Protocol):
    def generate_data_key(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def decrypt(self, **kwargs: Any) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class EncryptedPayload:
    ciphertext: str
    encrypted_data_key: str
    nonce: str
    encryption_version: int = ENCRYPTION_VERSION
    key_arn: str | None = None


class EncryptionConfigurationError(Exception):
    safe_message = PROTECTED_STORAGE_NOT_CONFIGURED


class EncryptionOperationError(Exception):
    safe_message = PROTECTED_STORAGE_UNAVAILABLE


class EncryptionService:
    def __init__(self, settings: Settings | None = None, kms_client: KmsClient | None = None):
        self.settings = settings or get_settings()
        self.kms_client = kms_client

    @property
    def mode(self) -> str:
        return self.settings.record_encryption_mode

    @property
    def enabled(self) -> bool:
        return self.mode in {RECORD_ENCRYPTION_LOCAL, RECORD_ENCRYPTION_KMS}

    def encrypt_json(self, payload: dict[str, Any], context: dict[str, str]) -> EncryptedPayload:
        if not self.enabled:
            raise EncryptionConfigurationError()

        aad = canonical_context_bytes(context)
        plaintext = canonical_json_bytes(payload)
        data_key, encrypted_data_key, key_arn = self._data_key_for_encrypt(context)
        nonce = os.urandom(12)

        try:
            ciphertext = AESGCM(data_key).encrypt(nonce, plaintext, aad)
        except Exception as exc:
            raise EncryptionOperationError() from exc
        finally:
            data_key = b""
            plaintext = b""

        return EncryptedPayload(
            ciphertext=base64.b64encode(ciphertext).decode("ascii"),
            encrypted_data_key=encrypted_data_key,
            nonce=base64.b64encode(nonce).decode("ascii"),
            encryption_version=ENCRYPTION_VERSION,
            key_arn=key_arn,
        )

    def decrypt_json(self, encrypted: EncryptedPayload, context: dict[str, str]) -> dict[str, Any]:
        if encrypted.encryption_version != ENCRYPTION_VERSION:
            raise EncryptionOperationError()
        if not self.enabled:
            raise EncryptionConfigurationError()

        aad = canonical_context_bytes(context)
        nonce = decode_b64(encrypted.nonce)
        ciphertext = decode_b64(encrypted.ciphertext)
        data_key = self._data_key_for_decrypt(encrypted.encrypted_data_key, context)

        try:
            plaintext = AESGCM(data_key).decrypt(nonce, ciphertext, aad)
            decoded = json.loads(plaintext.decode("utf-8"))
        except (InvalidTag, ValueError, json.JSONDecodeError) as exc:
            raise EncryptionOperationError() from exc
        finally:
            data_key = b""

        if not isinstance(decoded, dict):
            raise EncryptionOperationError()
        return decoded

    def _data_key_for_encrypt(self, context: dict[str, str]) -> tuple[bytes, str, str | None]:
        if self.mode == RECORD_ENCRYPTION_LOCAL:
            return self._local_data_key_for_encrypt(context)

        if self.mode == RECORD_ENCRYPTION_KMS:
            if not self.settings.data_encryption_kms_key_arn:
                raise EncryptionConfigurationError()

            try:
                response = self._kms_client().generate_data_key(
                    KeyId=self.settings.data_encryption_kms_key_arn,
                    KeySpec="AES_256",
                    EncryptionContext=context,
                )
            except Exception as exc:
                raise EncryptionOperationError() from exc

            plaintext = response.get("Plaintext")
            encrypted_key = response.get("CiphertextBlob")
            if not isinstance(plaintext, bytes) or not isinstance(encrypted_key, bytes) or len(plaintext) != 32:
                raise EncryptionOperationError()

            key_id = response.get("KeyId")
            return (
                plaintext,
                base64.b64encode(encrypted_key).decode("ascii"),
                key_id if isinstance(key_id, str) else self.settings.data_encryption_kms_key_arn,
            )

        raise EncryptionConfigurationError()

    def _data_key_for_decrypt(self, encrypted_data_key: str, context: dict[str, str]) -> bytes:
        if self.mode == RECORD_ENCRYPTION_LOCAL:
            return self._local_data_key_for_decrypt(encrypted_data_key, context)

        if self.mode == RECORD_ENCRYPTION_KMS:
            if not self.settings.data_encryption_kms_key_arn:
                raise EncryptionConfigurationError()
            try:
                response = self._kms_client().decrypt(
                    CiphertextBlob=decode_b64(encrypted_data_key),
                    EncryptionContext=context,
                    KeyId=self.settings.data_encryption_kms_key_arn,
                )
            except Exception as exc:
                raise EncryptionOperationError() from exc

            plaintext = response.get("Plaintext")
            if not isinstance(plaintext, bytes) or len(plaintext) != 32:
                raise EncryptionOperationError()
            return plaintext

        raise EncryptionConfigurationError()

    def _local_data_key_for_encrypt(self, context: dict[str, str]) -> tuple[bytes, str, str | None]:
        wrapping_key = self._local_wrapping_key()
        data_key = os.urandom(32)
        key_nonce = os.urandom(12)
        wrapped_key = AESGCM(wrapping_key).encrypt(
            key_nonce,
            data_key,
            canonical_context_bytes({**context, "wrapped": "data-key"}),
        )
        encoded = {
            "nonce": base64.b64encode(key_nonce).decode("ascii"),
            "ciphertext": base64.b64encode(wrapped_key).decode("ascii"),
        }
        return data_key, base64.b64encode(canonical_json_bytes(encoded)).decode("ascii"), "local"

    def _local_data_key_for_decrypt(self, encrypted_data_key: str, context: dict[str, str]) -> bytes:
        wrapping_key = self._local_wrapping_key()
        try:
            wrapped = json.loads(decode_b64(encrypted_data_key).decode("utf-8"))
            key_nonce = decode_b64(wrapped["nonce"])
            wrapped_key = decode_b64(wrapped["ciphertext"])
            return AESGCM(wrapping_key).decrypt(
                key_nonce,
                wrapped_key,
                canonical_context_bytes({**context, "wrapped": "data-key"}),
            )
        except (InvalidTag, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise EncryptionOperationError() from exc

    def _local_wrapping_key(self) -> bytes:
        key_text = self.settings.local_records_encryption_key
        if not key_text:
            raise EncryptionConfigurationError()

        key = decode_b64(key_text)
        if len(key) != 32:
            raise EncryptionConfigurationError()
        return key

    def _kms_client(self) -> KmsClient:
        if self.kms_client is not None:
            return self.kms_client

        import boto3

        self.kms_client = boto3.client("kms", region_name=self.settings.aws_region)
        return self.kms_client


def record_encryption_context(user_id: str, record_id: str) -> dict[str, str]:
    return {
        "app": "lifeledger",
        "purpose": "record-protected",
        "owner_hash": user_hash(user_id),
        "resource_id": record_id,
        "version": str(ENCRYPTION_VERSION),
    }


def google_token_encryption_context(user_id: str) -> dict[str, str]:
    return {
        "app": "lifeledger",
        "purpose": "google-oauth-token",
        "owner_hash": user_hash(user_id),
        "resource_id": "google-calendar",
        "version": str(ENCRYPTION_VERSION),
    }


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_context_bytes(context: dict[str, str]) -> bytes:
    return canonical_json_bytes(context)


def decode_b64(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as exc:
        raise EncryptionOperationError() from exc


def encryption_updated_at() -> datetime:
    return datetime.now(timezone.utc)
