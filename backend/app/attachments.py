import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.attachments_repository import RecordAttachmentRepository, record_attachment_key
from app.config import DOCUMENT_STORAGE_S3, Settings, get_settings
from app.models import RecordAttachment
from app.schemas import AttachmentScanResult, AttachmentStatus
from app.security_audit import log_security_event, user_hash

DOCUMENT_STORAGE_NOT_CONFIGURED = "Secure document storage is not configured for this environment."
DOCUMENT_STORAGE_UNAVAILABLE = "Secure document storage is temporarily unavailable."
ATTACHMENT_NOT_AVAILABLE = "File is not available for download."
UPLOAD_NOT_READY = "Upload has not completed yet."
FILE_FAILED_SECURITY_SCAN = "File failed security scan."

ALLOWED_CONTENT_TYPES = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
}
DISPLAY_EXTENSION_BY_CONTENT_TYPE = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
MAGIC_SIGNATURES = {
    "application/pdf": b"%PDF-",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}
GUARDDUTY_SCAN_TAG = "GuardDutyMalwareScanStatus"
UPLOAD_INTENT_EXPIRATION_SECONDS = 5 * 60
DOWNLOAD_URL_EXPIRATION_SECONDS = 60
ACTIVE_ATTACHMENT_STATUSES = {
    AttachmentStatus.PENDING_UPLOAD,
    AttachmentStatus.UPLOADED,
    AttachmentStatus.SCANNING,
    AttachmentStatus.AVAILABLE,
}
TERMINAL_UNAVAILABLE_SCAN_RESULTS = {
    AttachmentScanResult.THREATS_FOUND,
    AttachmentScanResult.UNSUPPORTED,
    AttachmentScanResult.ACCESS_DENIED,
    AttachmentScanResult.FAILED,
}


@dataclass(frozen=True)
class AttachmentObjectHead:
    content_length: int
    content_type: str
    server_side_encryption: str | None = None
    kms_key_id: str | None = None
    etag: str | None = None


class AttachmentValidationError(Exception):
    def __init__(self, safe_message: str):
        self.safe_message = safe_message
        super().__init__(safe_message)


class DocumentStorageConfigurationError(Exception):
    safe_message = DOCUMENT_STORAGE_NOT_CONFIGURED


class DocumentStorageOperationError(Exception):
    safe_message = DOCUMENT_STORAGE_UNAVAILABLE


class DisabledDocumentStorageService:
    configured = False

    def create_presigned_upload(self, *_args, **_kwargs):
        raise DocumentStorageConfigurationError()

    def head_quarantine_object(self, _key: str) -> AttachmentObjectHead:
        raise DocumentStorageConfigurationError()

    def head_clean_object(self, _key: str) -> AttachmentObjectHead:
        raise DocumentStorageConfigurationError()

    def delete_quarantine_object(self, _key: str) -> None:
        raise DocumentStorageConfigurationError()

    def delete_clean_object(self, _key: str) -> None:
        raise DocumentStorageConfigurationError()

    def get_scan_result(self, _key: str) -> AttachmentScanResult | None:
        raise DocumentStorageConfigurationError()

    def read_magic_bytes(self, _key: str, _byte_count: int) -> bytes:
        raise DocumentStorageConfigurationError()

    def promote_to_clean(self, _attachment: RecordAttachment, _content_disposition: str) -> None:
        raise DocumentStorageConfigurationError()

    def create_presigned_download(self, *_args, **_kwargs):
        raise DocumentStorageConfigurationError()


class S3DocumentStorageService:
    configured = True

    def __init__(self, settings: Settings | None = None, s3_client=None):
        self.settings = settings or get_settings()
        if not self.settings.document_storage_configured:
            raise DocumentStorageConfigurationError()
        self.s3_client = s3_client

    @property
    def quarantine_bucket(self) -> str:
        return self.settings.documents_quarantine_bucket

    @property
    def clean_bucket(self) -> str:
        return self.settings.documents_clean_bucket

    @property
    def kms_key_arn(self) -> str:
        return self.settings.documents_kms_key_arn

    def create_presigned_upload(
        self,
        attachment: RecordAttachment,
        *,
        max_size_bytes: int,
        expires_in_seconds: int = UPLOAD_INTENT_EXPIRATION_SECONDS,
    ) -> dict:
        if not attachment.quarantine_object_key:
            raise DocumentStorageOperationError()

        fields = {
            "Content-Type": attachment.content_type,
            "x-amz-server-side-encryption": "aws:kms",
            "x-amz-server-side-encryption-aws-kms-key-id": self.kms_key_arn,
        }
        conditions = [
            {"key": attachment.quarantine_object_key},
            {"Content-Type": attachment.content_type},
            ["content-length-range", 1, max_size_bytes],
            {"x-amz-server-side-encryption": "aws:kms"},
            {"x-amz-server-side-encryption-aws-kms-key-id": self.kms_key_arn},
        ]
        try:
            return self._client().generate_presigned_post(
                Bucket=self.quarantine_bucket,
                Key=attachment.quarantine_object_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expires_in_seconds,
            )
        except Exception as exc:
            raise DocumentStorageOperationError() from exc

    def head_quarantine_object(self, key: str) -> AttachmentObjectHead:
        return self._head_object(self.quarantine_bucket, key)

    def head_clean_object(self, key: str) -> AttachmentObjectHead:
        return self._head_object(self.clean_bucket, key)

    def delete_quarantine_object(self, key: str) -> None:
        self._delete_object(self.quarantine_bucket, key)

    def delete_clean_object(self, key: str) -> None:
        self._delete_object(self.clean_bucket, key)

    def get_scan_result(self, key: str) -> AttachmentScanResult | None:
        try:
            response = self._client().get_object_tagging(Bucket=self.quarantine_bucket, Key=key)
        except Exception as exc:
            raise DocumentStorageOperationError() from exc

        for tag in response.get("TagSet", []):
            if tag.get("Key") == GUARDDUTY_SCAN_TAG:
                return scan_result_from_guardduty_value(tag.get("Value"))

        return None

    def read_magic_bytes(self, key: str, byte_count: int) -> bytes:
        try:
            response = self._client().get_object(
                Bucket=self.quarantine_bucket,
                Key=key,
                Range=f"bytes=0-{max(byte_count - 1, 0)}",
            )
            body = response.get("Body")
            return body.read(byte_count) if body is not None else b""
        except Exception as exc:
            raise DocumentStorageOperationError() from exc

    def promote_to_clean(self, attachment: RecordAttachment, content_disposition: str) -> None:
        if not attachment.quarantine_object_key or not attachment.clean_object_key:
            raise DocumentStorageOperationError()

        try:
            self._client().copy_object(
                Bucket=self.clean_bucket,
                Key=attachment.clean_object_key,
                CopySource={"Bucket": self.quarantine_bucket, "Key": attachment.quarantine_object_key},
                ContentType=attachment.content_type,
                ContentDisposition=content_disposition,
                CacheControl="no-store, private",
                MetadataDirective="REPLACE",
                TaggingDirective="REPLACE",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=self.kms_key_arn,
            )
        except Exception as exc:
            raise DocumentStorageOperationError() from exc

    def create_presigned_download(
        self,
        attachment: RecordAttachment,
        *,
        content_disposition: str,
        expires_in_seconds: int = DOWNLOAD_URL_EXPIRATION_SECONDS,
    ) -> str:
        if not attachment.clean_object_key:
            raise DocumentStorageOperationError()

        try:
            return self._client().generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.clean_bucket,
                    "Key": attachment.clean_object_key,
                    "ResponseContentDisposition": content_disposition,
                    "ResponseContentType": attachment.content_type,
                    "ResponseCacheControl": "no-store, private",
                },
                ExpiresIn=expires_in_seconds,
            )
        except Exception as exc:
            raise DocumentStorageOperationError() from exc

    def _head_object(self, bucket: str, key: str) -> AttachmentObjectHead:
        try:
            response = self._client().head_object(Bucket=bucket, Key=key)
        except Exception as exc:
            raise DocumentStorageOperationError() from exc

        return AttachmentObjectHead(
            content_length=int(response.get("ContentLength", 0)),
            content_type=response.get("ContentType", ""),
            server_side_encryption=response.get("ServerSideEncryption"),
            kms_key_id=response.get("SSEKMSKeyId"),
            etag=response.get("ETag"),
        )

    def _delete_object(self, bucket: str, key: str) -> None:
        try:
            self._client().delete_object(Bucket=bucket, Key=key)
        except Exception as exc:
            raise DocumentStorageOperationError() from exc

    def _client(self):
        if self.s3_client is not None:
            return self.s3_client

        import boto3
        from botocore.config import Config

        self.s3_client = boto3.client(
            "s3",
            region_name=self.settings.aws_region,
            config=Config(signature_version="s3v4"),
        )
        return self.s3_client


def create_document_storage_service(settings: Settings | None = None):
    resolved_settings = settings or get_settings()
    if resolved_settings.document_storage_mode != DOCUMENT_STORAGE_S3:
        return DisabledDocumentStorageService()
    return S3DocumentStorageService(resolved_settings)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_upload_request(filename: str, content_type: str, size_bytes: int, max_size_bytes: int) -> str:
    normalized_content_type = content_type.strip().lower()
    if normalized_content_type not in ALLOWED_CONTENT_TYPES:
        raise AttachmentValidationError("Only PDF, JPEG, and PNG files are supported.")
    if size_bytes <= 0:
        raise AttachmentValidationError("File must not be empty.")
    if size_bytes > max_size_bytes:
        raise AttachmentValidationError("File is larger than the 10 MB limit.")

    original_extension = file_extension(re.split(r"[\\/]+", filename.strip())[-1])
    if original_extension not in ALLOWED_CONTENT_TYPES[normalized_content_type]:
        raise AttachmentValidationError("Filename extension does not match the selected file type.")

    display_name = sanitize_display_filename(filename, normalized_content_type)
    return display_name


def sanitize_display_filename(filename: str, content_type: str) -> str:
    without_paths = re.split(r"[\\/]+", filename.strip())[-1]
    without_controls = "".join(character for character in without_paths if character >= " " and character != "\x7f")
    collapsed = re.sub(r"\s+", " ", without_controls).strip().strip(".")
    if not collapsed:
        collapsed = "document"

    extension = file_extension(collapsed)
    allowed_extensions = ALLOWED_CONTENT_TYPES[content_type]
    if extension not in allowed_extensions:
        extension = DISPLAY_EXTENSION_BY_CONTENT_TYPE[content_type]
        stem = re.sub(r"\.[^.]*$", "", collapsed).strip().strip(".") or "document"
    else:
        stem = collapsed[: -len(extension)].strip().strip(".") or "document"

    safe_stem = re.sub(r'["<>:|?*\x00-\x1f]', "_", stem)
    safe_stem = safe_stem.replace("/", "_").replace("\\", "_").strip()
    if not safe_stem:
        safe_stem = "document"

    max_stem_length = 120 - len(extension)
    return f"{safe_stem[:max_stem_length]}{extension}"


def file_extension(filename: str) -> str:
    dot_index = filename.rfind(".")
    if dot_index == -1:
        return ""
    return filename[dot_index:].lower()


def owner_hash_for_user(user_id: str) -> str:
    return user_hash(user_id)


def new_record_attachment(
    *,
    user_id: str,
    record_id: str,
    filename: str,
    content_type: str,
    size_bytes: int,
    settings: Settings,
    now: datetime | None = None,
    attachment_id: str | None = None,
) -> RecordAttachment:
    created_at = now or utc_now()
    normalized_content_type = content_type.strip().lower()
    display_name = validate_upload_request(
        filename,
        normalized_content_type,
        size_bytes,
        settings.attachment_max_size_bytes,
    )
    attachment_id = attachment_id or str(uuid4())
    owner_hash = owner_hash_for_user(user_id)
    return RecordAttachment(
        attachment_id=attachment_id,
        user_id=user_id,
        owner_hash=owner_hash,
        record_id=record_id,
        record_attachment_key=record_attachment_key(record_id, attachment_id),
        display_name=display_name,
        content_type=normalized_content_type,
        size_bytes=size_bytes,
        status=AttachmentStatus.PENDING_UPLOAD,
        scan_result=AttachmentScanResult.PENDING,
        quarantine_object_key=f"quarantine/{owner_hash}/{record_id}/{attachment_id}/object",
        clean_object_key=None,
        upload_expires_at=created_at + timedelta(seconds=UPLOAD_INTENT_EXPIRATION_SECONDS),
        created_at=created_at,
        encryption_key_arn=settings.documents_kms_key_arn or None,
    )


def validate_uploaded_object(
    attachment: RecordAttachment,
    head: AttachmentObjectHead,
    *,
    expected_kms_key_arn: str,
    max_size_bytes: int,
) -> None:
    if head.content_length <= 0:
        raise AttachmentValidationError("Uploaded file is empty.")
    if head.content_length > max_size_bytes:
        raise AttachmentValidationError("Uploaded file is larger than the 10 MB limit.")
    if head.content_length != attachment.size_bytes:
        raise AttachmentValidationError("Uploaded file size did not match the requested upload.")
    if head.content_type != attachment.content_type:
        raise AttachmentValidationError("Uploaded file type did not match the requested upload.")
    if head.server_side_encryption != "aws:kms" or head.kms_key_id != expected_kms_key_arn:
        raise AttachmentValidationError("Uploaded file encryption did not match LifeLedger requirements.")


def validate_magic_bytes(attachment: RecordAttachment, magic_bytes: bytes) -> None:
    expected_signature = MAGIC_SIGNATURES.get(attachment.content_type)
    if expected_signature is None or not magic_bytes.startswith(expected_signature):
        raise AttachmentValidationError("Uploaded file content does not match the selected file type.")


def scan_result_from_guardduty_value(value: str | None) -> AttachmentScanResult | None:
    normalized = (value or "").strip().upper()
    mapping = {
        "NO_THREATS_FOUND": AttachmentScanResult.NO_THREATS_FOUND,
        "THREATS_FOUND": AttachmentScanResult.THREATS_FOUND,
        "UNSUPPORTED": AttachmentScanResult.UNSUPPORTED,
        "ACCESS_DENIED": AttachmentScanResult.ACCESS_DENIED,
        "FAILED": AttachmentScanResult.FAILED,
    }
    return mapping.get(normalized)


def guardduty_value_from_scan_result(scan_result: AttachmentScanResult | None) -> str | None:
    if scan_result is None or scan_result == AttachmentScanResult.PENDING:
        return None
    return scan_result.value.upper()


def attachment_content_disposition(attachment: RecordAttachment, disposition_type: str = "attachment") -> str:
    safe_name = re.sub(r'[^A-Za-z0-9._ -]', "_", attachment.display_name).strip() or "document"
    disposition = "inline" if disposition_type == "inline" else "attachment"
    return f'{disposition}; filename="{safe_name[:120]}"'


def complete_attachment_upload(
    *,
    attachment: RecordAttachment,
    storage,
    settings: Settings,
    now: datetime | None = None,
) -> RecordAttachment:
    if attachment.status in {
        AttachmentStatus.UPLOADED,
        AttachmentStatus.SCANNING,
        AttachmentStatus.AVAILABLE,
        AttachmentStatus.REJECTED,
        AttachmentStatus.SCAN_FAILED,
    }:
        return attachment
    if attachment.status != AttachmentStatus.PENDING_UPLOAD:
        raise AttachmentValidationError(UPLOAD_NOT_READY)
    if not attachment.quarantine_object_key:
        raise AttachmentValidationError(UPLOAD_NOT_READY)

    head = storage.head_quarantine_object(attachment.quarantine_object_key)
    validate_uploaded_object(
        attachment,
        head,
        expected_kms_key_arn=settings.documents_kms_key_arn,
        max_size_bytes=settings.attachment_max_size_bytes,
    )
    completed_at = now or utc_now()
    return attachment.model_copy(
        update={
            "status": AttachmentStatus.SCANNING,
            "scan_result": AttachmentScanResult.PENDING,
            "uploaded_at": completed_at,
            "etag": head.etag,
        }
    )


def reconcile_attachment_scan_status(
    *,
    attachment: RecordAttachment,
    repo: RecordAttachmentRepository,
    storage,
    settings: Settings,
    now: datetime | None = None,
) -> RecordAttachment:
    if attachment.status == AttachmentStatus.AVAILABLE:
        return attachment
    if attachment.status not in {
        AttachmentStatus.UPLOADED,
        AttachmentStatus.SCANNING,
        AttachmentStatus.REJECTED,
        AttachmentStatus.SCAN_FAILED,
    }:
        return attachment
    if not attachment.quarantine_object_key:
        return attachment

    current_time = now or utc_now()
    scan_result = storage.get_scan_result(attachment.quarantine_object_key)
    if scan_result is None:
        if attachment.status != AttachmentStatus.SCANNING or attachment.scan_result != AttachmentScanResult.PENDING:
            updated = attachment.model_copy(
                update={"status": AttachmentStatus.SCANNING, "scan_result": AttachmentScanResult.PENDING}
            )
            return repo.update_attachment(updated)
        return attachment

    if scan_result == AttachmentScanResult.NO_THREATS_FOUND:
        return promote_clean_attachment(
            attachment=attachment,
            repo=repo,
            storage=storage,
            settings=settings,
            scan_completed_at=current_time,
        )

    return reject_scanned_attachment(
        attachment=attachment,
        repo=repo,
        storage=storage,
        scan_result=scan_result,
        scan_completed_at=current_time,
    )


def promote_clean_attachment(
    *,
    attachment: RecordAttachment,
    repo: RecordAttachmentRepository,
    storage,
    settings: Settings,
    scan_completed_at: datetime,
) -> RecordAttachment:
    if attachment.status == AttachmentStatus.AVAILABLE and attachment.clean_object_key:
        return attachment
    if not attachment.quarantine_object_key:
        return attachment

    clean_object_key = attachment.clean_object_key or (
        f"clean/{attachment.owner_hash}/{attachment.record_id}/{attachment.attachment_id}/object"
    )
    promote_candidate = attachment.model_copy(update={"clean_object_key": clean_object_key})

    try:
        head = storage.head_quarantine_object(attachment.quarantine_object_key)
        validate_uploaded_object(
            attachment,
            head,
            expected_kms_key_arn=settings.documents_kms_key_arn,
            max_size_bytes=settings.attachment_max_size_bytes,
        )
        magic = storage.read_magic_bytes(
            attachment.quarantine_object_key,
            len(MAGIC_SIGNATURES[attachment.content_type]),
        )
        validate_magic_bytes(attachment, magic)
        storage.promote_to_clean(promote_candidate, attachment_content_disposition(attachment))
        storage.head_clean_object(clean_object_key)
        storage.delete_quarantine_object(attachment.quarantine_object_key)
    except AttachmentValidationError:
        storage.delete_quarantine_object(attachment.quarantine_object_key)
        updated = attachment.model_copy(
            update={
                "status": AttachmentStatus.REJECTED,
                "scan_result": AttachmentScanResult.FAILED,
                "scan_completed_at": scan_completed_at,
                "quarantine_object_key": None,
                "clean_object_key": None,
            }
        )
        saved = repo.update_attachment(updated)
        log_security_event(
            "attachment_scan_failed",
            user_id=attachment.user_id,
            record_id=attachment.record_id,
            attachment_id=attachment.attachment_id,
            content_type=attachment.content_type,
            size=attachment.size_bytes,
            result="validation_failed",
        )
        return saved

    updated = attachment.model_copy(
        update={
            "status": AttachmentStatus.AVAILABLE,
            "scan_result": AttachmentScanResult.NO_THREATS_FOUND,
            "scan_completed_at": scan_completed_at,
            "available_at": scan_completed_at,
            "quarantine_object_key": None,
            "clean_object_key": clean_object_key,
        }
    )
    saved = repo.update_attachment(updated)
    log_security_event(
        "attachment_scan_passed",
        user_id=attachment.user_id,
        record_id=attachment.record_id,
        attachment_id=attachment.attachment_id,
        content_type=attachment.content_type,
        size=attachment.size_bytes,
        result="no_threats_found",
    )
    return saved


def reject_scanned_attachment(
    *,
    attachment: RecordAttachment,
    repo: RecordAttachmentRepository,
    storage,
    scan_result: AttachmentScanResult,
    scan_completed_at: datetime,
) -> RecordAttachment:
    if scan_result not in TERMINAL_UNAVAILABLE_SCAN_RESULTS:
        return attachment
    if attachment.quarantine_object_key:
        storage.delete_quarantine_object(attachment.quarantine_object_key)

    status = AttachmentStatus.SCAN_FAILED if scan_result == AttachmentScanResult.FAILED else AttachmentStatus.REJECTED
    updated = attachment.model_copy(
        update={
            "status": status,
            "scan_result": scan_result,
            "scan_completed_at": scan_completed_at,
            "quarantine_object_key": None,
            "clean_object_key": None,
        }
    )
    saved = repo.update_attachment(updated)
    event_name = "attachment_scan_rejected" if status == AttachmentStatus.REJECTED else "attachment_scan_failed"
    log_security_event(
        event_name,
        user_id=attachment.user_id,
        record_id=attachment.record_id,
        attachment_id=attachment.attachment_id,
        content_type=attachment.content_type,
        size=attachment.size_bytes,
        result=scan_result.value,
    )
    return saved


def active_attachment_count(attachments: list[RecordAttachment]) -> int:
    return sum(1 for attachment in attachments if attachment.status in ACTIVE_ATTACHMENT_STATUSES)


def sort_attachments(attachments: list[RecordAttachment]) -> list[RecordAttachment]:
    return sorted(attachments, key=lambda item: item.created_at)
