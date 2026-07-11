import base64
import os
from dataclasses import replace

import pytest

from app.config import load_settings
from app.encryption_service import (
    EncryptionConfigurationError,
    EncryptionOperationError,
    EncryptionService,
    record_encryption_context,
)


def local_key() -> str:
    return base64.b64encode(b"0" * 32).decode("ascii")


def local_encryption_service() -> EncryptionService:
    return EncryptionService(
        load_settings(
            {
                "RECORD_ENCRYPTION_MODE": "local",
                "LOCAL_RECORDS_ENCRYPTION_KEY": local_key(),
            }
        )
    )


def test_local_encryption_mode_round_trips_payload():
    service = local_encryption_service()
    context = record_encryption_context("user-a", "record-a")

    encrypted = service.encrypt_json({"document_number": "P1234567"}, context)
    decrypted = service.decrypt_json(encrypted, context)

    assert decrypted == {"document_number": "P1234567"}
    assert "P1234567" not in encrypted.ciphertext


def test_encryption_uses_unique_nonce_and_wrapped_data_key():
    service = local_encryption_service()
    context = record_encryption_context("user-a", "record-a")

    first = service.encrypt_json({"document_number": "P1234567"}, context)
    second = service.encrypt_json({"document_number": "P1234567"}, context)

    assert first.nonce != second.nonce
    assert first.encrypted_data_key != second.encrypted_data_key
    assert first.ciphertext != second.ciphertext


def test_tampering_fails_decryption():
    service = local_encryption_service()
    context = record_encryption_context("user-a", "record-a")
    encrypted = service.encrypt_json({"document_number": "P1234567"}, context)
    tampered_ciphertext = base64.b64encode(os.urandom(32)).decode("ascii")

    with pytest.raises(EncryptionOperationError):
        service.decrypt_json(replace(encrypted, ciphertext=tampered_ciphertext), context)


def test_wrong_encryption_context_fails_decryption():
    service = local_encryption_service()
    encrypted = service.encrypt_json({"document_number": "P1234567"}, record_encryption_context("user-a", "record-a"))

    with pytest.raises(EncryptionOperationError):
        service.decrypt_json(encrypted, record_encryption_context("user-b", "record-a"))

    with pytest.raises(EncryptionOperationError):
        service.decrypt_json(encrypted, record_encryption_context("user-a", "record-b"))


def test_local_mode_missing_key_fails_safely():
    service = EncryptionService(load_settings({"RECORD_ENCRYPTION_MODE": "local"}))

    with pytest.raises(EncryptionConfigurationError) as exc:
        service.encrypt_json({"document_number": "P1234567"}, record_encryption_context("user-a", "record-a"))

    assert exc.value.safe_message == "Protected record storage is not configured for this environment."
