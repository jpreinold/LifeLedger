from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.attachments import AttachmentObjectHead, DisabledDocumentStorageService, S3DocumentStorageService, owner_hash_for_user
from app.attachments_repository import LocalRecordAttachmentRepository
from app.auth import UserContext, get_current_user
from app.config import load_settings
from app.main import (
    app,
    get_app_settings,
    get_document_storage_service,
    get_linked_item_repository,
    get_record_attachment_repository,
    get_record_repository,
)
from app.linked_items_repository import LocalLinkedItemRepository
from app.models import Record, RecordAttachment
from app.records_repository import LocalRecordRepository
from app.schemas import AttachmentScanResult, RecordStatus


DOCUMENTS_KMS_KEY_ARN = "arn:aws:kms:us-east-1:123456789012:key/documents"


@pytest.fixture()
def attachment_context(tmp_path):
    settings = load_settings(
        {
            "DOCUMENT_STORAGE_MODE": "s3",
            "DOCUMENTS_QUARANTINE_BUCKET": "quarantine-bucket",
            "DOCUMENTS_CLEAN_BUCKET": "clean-bucket",
            "DOCUMENTS_KMS_KEY_ARN": DOCUMENTS_KMS_KEY_ARN,
            "ATTACHMENT_MAX_SIZE_BYTES": str(10 * 1024 * 1024),
            "ATTACHMENT_MAX_PER_RECORD": "5",
        }
    )
    record_repo = LocalRecordRepository(tmp_path / "records.json")
    attachment_repo = LocalRecordAttachmentRepository(tmp_path / "attachments.json")
    linked_repo = LocalLinkedItemRepository(tmp_path / "linked-items.json")
    storage = FakeDocumentStorage(settings)

    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_record_repository] = lambda: record_repo
    app.dependency_overrides[get_record_attachment_repository] = lambda: attachment_repo
    app.dependency_overrides[get_linked_item_repository] = lambda: linked_repo
    app.dependency_overrides[get_document_storage_service] = lambda: storage

    with TestClient(app) as test_client:
        yield test_client, record_repo, attachment_repo, storage, settings

    app.dependency_overrides.clear()


class FakeDocumentStorage:
    configured = True

    def __init__(self, settings):
        self.settings = settings
        self.uploads = []
        self.quarantine_heads = {}
        self.clean_heads = {}
        self.tags = {}
        self.magic = {}
        self.deleted_quarantine = []
        self.deleted_clean = []
        self.promoted = []
        self.presigned_gets = []

    def create_presigned_upload(self, attachment, *, max_size_bytes, expires_in_seconds):
        self.uploads.append(
            {
                "key": attachment.quarantine_object_key,
                "max_size_bytes": max_size_bytes,
                "expires_in_seconds": expires_in_seconds,
            }
        )
        return {
            "url": "https://quarantine-bucket.s3.us-east-1.amazonaws.com/",
            "fields": {
                "key": attachment.quarantine_object_key,
                "Content-Type": attachment.content_type,
                "x-amz-server-side-encryption": "aws:kms",
                "x-amz-server-side-encryption-aws-kms-key-id": self.settings.documents_kms_key_arn,
            },
        }

    def head_quarantine_object(self, key):
        return self.quarantine_heads[key]

    def head_clean_object(self, key):
        return self.clean_heads[key]

    def delete_quarantine_object(self, key):
        self.deleted_quarantine.append(key)
        self.quarantine_heads.pop(key, None)

    def delete_clean_object(self, key):
        self.deleted_clean.append(key)
        self.clean_heads.pop(key, None)

    def get_scan_result(self, key):
        return self.tags.get(key)

    def read_magic_bytes(self, key, byte_count):
        return self.magic.get(key, b"")[:byte_count]

    def promote_to_clean(self, attachment, content_disposition):
        self.promoted.append((attachment.quarantine_object_key, attachment.clean_object_key, content_disposition))
        self.clean_heads[attachment.clean_object_key] = AttachmentObjectHead(
            content_length=attachment.size_bytes,
            content_type=attachment.content_type,
            server_side_encryption="aws:kms",
            kms_key_id=self.settings.documents_kms_key_arn,
            etag='"clean-etag"',
        )

    def create_presigned_download(self, attachment, *, content_disposition, expires_in_seconds):
        assert expires_in_seconds == 60
        self.presigned_gets.append(
            {
                "attachment_id": attachment.attachment_id,
                "content_disposition": content_disposition,
                "expires_in_seconds": expires_in_seconds,
            }
        )
        mode = "preview" if content_disposition.startswith("inline;") else "download"
        return f"https://clean-bucket.s3.us-east-1.amazonaws.com/{mode}/{attachment.attachment_id}?X-Amz-Expires=60"


def set_auth_user(user_id: str):
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id=user_id)


def create_record(record_repo: LocalRecordRepository, user_id="user-a") -> Record:
    now = datetime.now(timezone.utc)
    record = Record(
        id=str(uuid4()),
        user_id=user_id,
        record_type="passport",
        title="Passport",
        category="Documents",
        status=RecordStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    return record_repo.create_record(record)


def create_upload_intent(client: TestClient, record_id: str, **overrides):
    payload = {
        "filename": "Passport Scan.pdf",
        "content_type": "application/pdf",
        "size_bytes": 512,
    }
    payload.update(overrides)
    response = client.post(f"/records/{record_id}/attachments/upload-intent", json=payload)
    assert response.status_code == 201
    return response.json()


def test_s3_storage_client_uses_signature_v4_for_kms_presigned_posts(monkeypatch):
    settings = load_settings(
        {
            "AWS_REGION": "us-west-2",
            "DOCUMENT_STORAGE_MODE": "s3",
            "DOCUMENTS_QUARANTINE_BUCKET": "quarantine-bucket",
            "DOCUMENTS_CLEAN_BUCKET": "clean-bucket",
            "DOCUMENTS_KMS_KEY_ARN": DOCUMENTS_KMS_KEY_ARN,
        }
    )
    captured = {}
    fake_client = object()

    def fake_boto3_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr("boto3.client", fake_boto3_client)

    storage = S3DocumentStorageService(settings)

    assert storage._client() is fake_client
    assert captured["service_name"] == "s3"
    assert captured["region_name"] == "us-west-2"
    assert captured["config"].signature_version == "s3v4"


def test_s3_promotion_replaces_tags_instead_of_copying_quarantine_tags():
    settings = load_settings(
        {
            "DOCUMENT_STORAGE_MODE": "s3",
            "DOCUMENTS_QUARANTINE_BUCKET": "quarantine-bucket",
            "DOCUMENTS_CLEAN_BUCKET": "clean-bucket",
            "DOCUMENTS_KMS_KEY_ARN": DOCUMENTS_KMS_KEY_ARN,
        }
    )
    fake_client = CapturingS3Client()
    storage = S3DocumentStorageService(settings, s3_client=fake_client)
    now = datetime.now(timezone.utc)
    attachment = RecordAttachment(
        attachment_id="attachment-1",
        user_id="user-a",
        owner_hash="owner-hash",
        record_id="record-1",
        record_attachment_key="record-1#attachment-1",
        display_name="Document.pdf",
        content_type="application/pdf",
        size_bytes=8,
        quarantine_object_key="quarantine/owner-hash/record-1/attachment-1/object",
        clean_object_key="clean/owner-hash/record-1/attachment-1/object",
        status="scanning",
        scan_result="pending",
        upload_expires_at=now,
        created_at=now,
        uploaded_at=now,
        scan_completed_at=None,
        available_at=None,
        deleted_at=None,
        etag=None,
        encryption_key_arn=DOCUMENTS_KMS_KEY_ARN,
    )

    storage.promote_to_clean(attachment, 'attachment; filename="Document.pdf"')

    assert fake_client.copy_kwargs["TaggingDirective"] == "REPLACE"
    assert fake_client.copy_kwargs["ServerSideEncryption"] == "aws:kms"
    assert fake_client.copy_kwargs["SSEKMSKeyId"] == DOCUMENTS_KMS_KEY_ARN


class CapturingS3Client:
    def __init__(self):
        self.copy_kwargs = {}

    def copy_object(self, **kwargs):
        self.copy_kwargs = kwargs
        return {}


class UserObjectS3Client:
    def __init__(self, owner_hash):
        self.owner_hash = owner_hash
        self.deleted = []

    def list_objects_v2(self, *, Bucket, Prefix, MaxKeys):
        object_class = "quarantine" if Bucket == "quarantine-bucket" else "clean"
        return {
            "Contents": [
                {"Key": f"{object_class}/{self.owner_hash}/record-1/attachment-1/object"},
            ][:MaxKeys]
            if Prefix == f"{object_class}/{self.owner_hash}/"
            else []
        }

    def delete_object(self, *, Bucket, Key):
        self.deleted.append((Bucket, Key))


def test_s3_storage_lists_and_deletes_every_user_owned_object_class_with_bounded_prefixes():
    settings = load_settings(
        {
            "DOCUMENT_STORAGE_MODE": "s3",
            "DOCUMENTS_QUARANTINE_BUCKET": "quarantine-bucket",
            "DOCUMENTS_CLEAN_BUCKET": "clean-bucket",
            "DOCUMENTS_KMS_KEY_ARN": DOCUMENTS_KMS_KEY_ARN,
        }
    )
    owner_hash = owner_hash_for_user("user-a")
    client = UserObjectS3Client(owner_hash)
    storage = S3DocumentStorageService(settings, s3_client=client)

    objects = storage.list_user_objects("user-a", limit=10)
    deleted = storage.delete_user_objects("user-a", limit=10)

    assert {item[0] for item in objects} == {"quarantine", "clean"}
    assert deleted == 2
    assert {item[0] for item in client.deleted} == {"quarantine-bucket", "clean-bucket"}


def prepare_completed_attachment(client, record_repo, attachment_repo, storage, *, user_id="user-a"):
    set_auth_user(user_id)
    record = create_record(record_repo, user_id=user_id)
    intent = create_upload_intent(client, record.id, filename="Passport Scan.pdf")
    attachment = attachment_repo.get_attachment(user_id, record.id, intent["attachment_id"])
    assert attachment is not None
    storage.quarantine_heads[attachment.quarantine_object_key] = AttachmentObjectHead(
        content_length=attachment.size_bytes,
        content_type=attachment.content_type,
        server_side_encryption="aws:kms",
        kms_key_id=DOCUMENTS_KMS_KEY_ARN,
        etag='"etag"',
    )
    response = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/complete")
    assert response.status_code == 200
    return record, attachment_repo.get_attachment(user_id, record.id, attachment.attachment_id)


def test_upload_intent_is_user_scoped_and_uses_non_pii_object_key(attachment_context, caplog):
    client, record_repo, attachment_repo, storage, _settings = attachment_context
    caplog.set_level("INFO", logger="app.security")
    set_auth_user("user-a@example.com")
    record = create_record(record_repo, user_id="user-a@example.com")

    response = client.post(
        f"/records/{record.id}/attachments/upload-intent",
        json={"filename": "Passport Scan 123.pdf", "content_type": "application/pdf", "size_bytes": 1024},
    )

    assert response.status_code == 201
    body = response.json()
    assert "user_id" not in body
    assert body["max_size_bytes"] == 10 * 1024 * 1024
    assert body["upload"]["fields"]["Content-Type"] == "application/pdf"
    assert body["upload"]["fields"]["x-amz-server-side-encryption"] == "aws:kms"

    key = body["upload"]["fields"]["key"]
    assert key.startswith("quarantine/")
    assert "Passport" not in key
    assert "Scan" not in key
    assert "user-a" not in key
    assert storage.uploads[0]["expires_in_seconds"] == 300

    saved = attachment_repo.get_attachment("user-a@example.com", record.id, body["attachment_id"])
    assert saved is not None
    assert saved.display_name == "Passport Scan 123.pdf"
    assert "Passport Scan" not in caplog.text
    assert "https://quarantine-bucket" not in caplog.text

    set_auth_user("user-b")
    blocked = client.post(
        f"/records/{record.id}/attachments/upload-intent",
        json={"filename": "other.pdf", "content_type": "application/pdf", "size_bytes": 1024},
    )
    assert blocked.status_code == 404


def test_upload_intent_idempotency_reuses_metadata_and_rejects_a_different_file(attachment_context):
    client, record_repo, attachment_repo, storage, _settings = attachment_context
    set_auth_user("user-a")
    record = create_record(record_repo, user_id="user-a")
    headers = {"Idempotency-Key": "guided-passport-setup:document"}
    payload = {"filename": "Passport.pdf", "content_type": "application/pdf", "size_bytes": 1024}

    first = client.post(f"/records/{record.id}/attachments/upload-intent", json=payload, headers=headers)
    second = client.post(f"/records/{record.id}/attachments/upload-intent", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["attachment_id"] == first.json()["attachment_id"]
    assert len(attachment_repo.list_for_record("user-a", record.id)) == 1
    assert len(storage.uploads) == 2

    mismatch = client.post(
        f"/records/{record.id}/attachments/upload-intent",
        json={**payload, "filename": "Different.pdf"},
        headers=headers,
    )
    assert mismatch.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"filename": "empty.pdf", "content_type": "application/pdf", "size_bytes": 0},
        {"filename": "large.pdf", "content_type": "application/pdf", "size_bytes": 10 * 1024 * 1024 + 1},
        {"filename": "script.svg", "content_type": "image/svg+xml", "size_bytes": 100},
        {"filename": "photo.png", "content_type": "image/jpeg", "size_bytes": 100},
        {"filename": "archive.zip", "content_type": "application/pdf", "size_bytes": 100},
    ],
)
def test_upload_intent_rejects_disallowed_files(attachment_context, payload):
    client, record_repo, _attachment_repo, _storage, _settings = attachment_context
    set_auth_user("user-a")
    record = create_record(record_repo, user_id="user-a")

    response = client.post(f"/records/{record.id}/attachments/upload-intent", json=payload)

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store, private"


def test_complete_validates_s3_metadata_before_scanning(attachment_context):
    client, record_repo, attachment_repo, storage, _settings = attachment_context
    set_auth_user("user-a")
    record = create_record(record_repo, user_id="user-a")
    intent = create_upload_intent(client, record.id)
    attachment = attachment_repo.get_attachment("user-a", record.id, intent["attachment_id"])
    assert attachment is not None
    storage.quarantine_heads[attachment.quarantine_object_key] = AttachmentObjectHead(
        content_length=attachment.size_bytes,
        content_type="image/png",
        server_side_encryption="aws:kms",
        kms_key_id=DOCUMENTS_KMS_KEY_ARN,
        etag='"etag"',
    )

    response = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/complete")

    assert response.status_code == 422
    assert attachment.quarantine_object_key in storage.deleted_quarantine
    rejected = attachment_repo.get_attachment("user-a", record.id, attachment.attachment_id)
    assert rejected.status == "rejected"
    assert rejected.quarantine_object_key is None


def test_scanning_attachment_is_not_downloadable_until_clean_tag_promotes_it(attachment_context):
    client, record_repo, attachment_repo, storage, _settings = attachment_context
    record, attachment = prepare_completed_attachment(client, record_repo, attachment_repo, storage)

    blocked = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/download-url")
    assert blocked.status_code == 409
    preview_blocked = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/preview-url")
    assert preview_blocked.status_code == 409

    storage.tags[attachment.quarantine_object_key] = AttachmentScanResult.NO_THREATS_FOUND
    storage.magic[attachment.quarantine_object_key] = b"%PDF-1.7"
    refreshed = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/refresh-status")

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["status"] == "available"
    assert body["scan_result"] == "no_threats_found"
    assert "clean_object_key" not in body
    assert "quarantine_object_key" not in body
    assert storage.promoted
    assert attachment.quarantine_object_key in storage.deleted_quarantine

    list_body = client.get(f"/records/{record.id}/attachments").json()
    assert "https://" not in str(list_body)
    assert "object_key" not in str(list_body)

    download = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/download-url")
    assert download.status_code == 200
    assert download.headers["cache-control"] == "no-store, private"
    assert download.json()["url"].startswith("https://clean-bucket.s3.us-east-1.amazonaws.com/download/")
    assert storage.presigned_gets[-1]["content_disposition"].startswith("attachment; filename=")

    preview = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/preview-url")
    assert preview.status_code == 200
    assert preview.headers["cache-control"] == "no-store, private"
    assert preview.json()["url"].startswith("https://clean-bucket.s3.us-east-1.amazonaws.com/preview/")
    assert storage.presigned_gets[-1]["content_disposition"].startswith("inline; filename=")


@pytest.mark.parametrize(
    ("scan_result", "expected_status"),
    [
        (AttachmentScanResult.THREATS_FOUND, "rejected"),
        (AttachmentScanResult.UNSUPPORTED, "rejected"),
        (AttachmentScanResult.ACCESS_DENIED, "rejected"),
        (AttachmentScanResult.FAILED, "scan_failed"),
    ],
)
def test_non_clean_scan_results_never_promote_or_download(attachment_context, scan_result, expected_status):
    client, record_repo, attachment_repo, storage, _settings = attachment_context
    record, attachment = prepare_completed_attachment(client, record_repo, attachment_repo, storage)
    storage.tags[attachment.quarantine_object_key] = scan_result

    refreshed = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/refresh-status")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == expected_status
    assert storage.promoted == []
    assert attachment.quarantine_object_key in storage.deleted_quarantine
    assert client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/download-url").status_code == 409


def test_magic_byte_mismatch_rejects_clean_tagged_file(attachment_context):
    client, record_repo, attachment_repo, storage, _settings = attachment_context
    record, attachment = prepare_completed_attachment(client, record_repo, attachment_repo, storage)
    storage.tags[attachment.quarantine_object_key] = AttachmentScanResult.NO_THREATS_FOUND
    storage.magic[attachment.quarantine_object_key] = b"not-a-pdf"

    refreshed = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/refresh-status")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "rejected"
    assert storage.promoted == []
    assert client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/download-url").status_code == 409


def test_user_cannot_access_another_users_attachments(attachment_context):
    client, record_repo, attachment_repo, storage, _settings = attachment_context
    record, attachment = prepare_completed_attachment(client, record_repo, attachment_repo, storage, user_id="user-a")

    set_auth_user("user-b")

    assert client.get(f"/records/{record.id}/attachments").status_code == 404
    assert client.get(f"/records/{record.id}/attachments/{attachment.attachment_id}").status_code == 404
    assert client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/download-url").status_code == 404
    assert client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/preview-url").status_code == 404
    assert client.delete(f"/records/{record.id}/attachments/{attachment.attachment_id}").status_code == 404


def test_delete_attachment_and_record_delete_remove_stored_objects(attachment_context):
    client, record_repo, attachment_repo, storage, _settings = attachment_context
    record, attachment = prepare_completed_attachment(client, record_repo, attachment_repo, storage)
    storage.tags[attachment.quarantine_object_key] = AttachmentScanResult.NO_THREATS_FOUND
    storage.magic[attachment.quarantine_object_key] = b"%PDF-1.7"
    assert client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/refresh-status").status_code == 200
    available = attachment_repo.get_attachment("user-a", record.id, attachment.attachment_id)
    assert available.clean_object_key

    delete_response = client.delete(f"/records/{record.id}/attachments/{attachment.attachment_id}")

    assert delete_response.status_code == 204
    assert available.clean_object_key in storage.deleted_clean
    assert attachment_repo.list_for_record("user-a", record.id) == []

    second_intent = create_upload_intent(client, record.id, filename="Second.pdf")
    pending = attachment_repo.get_attachment("user-a", record.id, second_intent["attachment_id"])
    assert pending is not None
    storage.quarantine_heads[pending.quarantine_object_key] = AttachmentObjectHead(
        content_length=pending.size_bytes,
        content_type=pending.content_type,
        server_side_encryption="aws:kms",
        kms_key_id=DOCUMENTS_KMS_KEY_ARN,
        etag='"etag"',
    )
    delete_record_response = client.delete(f"/records/{record.id}")

    assert delete_record_response.status_code == 204
    assert pending.quarantine_object_key in storage.deleted_quarantine
    assert attachment_repo.list_for_record("user-a", record.id) == []
    assert record_repo.get_record("user-a", record.id) is None


def test_disabled_document_storage_fails_closed(attachment_context):
    client, record_repo, _attachment_repo, _storage, _settings = attachment_context
    app.dependency_overrides[get_document_storage_service] = lambda: DisabledDocumentStorageService()
    set_auth_user("user-a")
    record = create_record(record_repo, user_id="user-a")

    response = client.post(
        f"/records/{record.id}/attachments/upload-intent",
        json={"filename": "Passport.pdf", "content_type": "application/pdf", "size_bytes": 512},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Secure document storage is not configured for this environment."
    assert response.headers["cache-control"] == "no-store, private"


def test_attachment_completion_is_safe_to_retry(attachment_context):
    client, record_repo, attachment_repo, storage, _settings = attachment_context
    record, attachment = prepare_completed_attachment(client, record_repo, attachment_repo, storage)
    first_status = attachment.status
    head_count = len(storage.quarantine_heads)

    retried = client.post(f"/records/{record.id}/attachments/{attachment.attachment_id}/complete")

    assert retried.status_code == 200
    assert retried.json()["attachment_id"] == attachment.attachment_id
    assert retried.json()["status"] == first_status
    assert len(attachment_repo.list_for_record("user-a", record.id)) == 1
    assert len(storage.quarantine_heads) == head_count
