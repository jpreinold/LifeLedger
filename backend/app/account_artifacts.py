from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol


class AccountArtifactStore(Protocol):
    def put(self, user_id: str, operation_id: str, content: bytes, *, expires_in_seconds: int) -> tuple[str, int]: ...

    def create_download_url(self, artifact_key: str, *, expires_in_seconds: int) -> str: ...

    def delete(self, artifact_key: str) -> None: ...

    def read(self, artifact_key: str) -> bytes: ...

    def list_for_user(self, user_id: str, *, limit: int = 100) -> list[str]: ...

    def delete_for_user(self, user_id: str, *, limit: int = 100) -> int: ...


class LocalAccountArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, user_id: str, operation_id: str, content: bytes, *, expires_in_seconds: int) -> tuple[str, int]:
        owner = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        artifact_key = f"exports/{owner}/{operation_id}.zip"
        path = self._path(artifact_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return artifact_key, len(content)

    def create_download_url(self, artifact_key: str, *, expires_in_seconds: int) -> str:
        return self._path(artifact_key).resolve().as_uri()

    def delete(self, artifact_key: str) -> None:
        self._path(artifact_key).unlink(missing_ok=True)

    def read(self, artifact_key: str) -> bytes:
        return self._path(artifact_key).read_bytes()

    def list_for_user(self, user_id: str, *, limit: int = 100) -> list[str]:
        owner = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        directory = self.root / "exports" / owner
        if not directory.exists():
            return []
        return [path.relative_to(self.root).as_posix() for path in sorted(directory.glob("*.zip"))[:limit]]

    def delete_for_user(self, user_id: str, *, limit: int = 100) -> int:
        keys = self.list_for_user(user_id, limit=limit)
        for artifact_key in keys:
            self.delete(artifact_key)
        return len(keys)

    def _path(self, artifact_key: str) -> Path:
        candidate = (self.root / artifact_key).resolve()
        if self.root.resolve() not in candidate.parents:
            raise ValueError("Invalid artifact key.")
        return candidate


class S3AccountArtifactStore:
    def __init__(self, bucket: str, kms_key_arn: str, region_name: str, client=None):
        self.bucket = bucket
        self.kms_key_arn = kms_key_arn
        self.region_name = region_name
        self.client = client or self._build_client(region_name)

    def put(self, user_id: str, operation_id: str, content: bytes, *, expires_in_seconds: int) -> tuple[str, int]:
        owner = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        artifact_key = f"exports/{owner}/{operation_id}.zip"
        self.client.put_object(
            Bucket=self.bucket,
            Key=artifact_key,
            Body=content,
            ContentType="application/zip",
            CacheControl="no-store, max-age=0",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=self.kms_key_arn,
        )
        return artifact_key, len(content)

    def create_download_url(self, artifact_key: str, *, expires_in_seconds: int) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": artifact_key,
                "ResponseCacheControl": "no-store, max-age=0",
                "ResponseContentDisposition": 'attachment; filename="lifeledger-export.zip"',
            },
            ExpiresIn=expires_in_seconds,
        )

    def delete(self, artifact_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=artifact_key)

    def read(self, artifact_key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=artifact_key)["Body"].read()

    def list_for_user(self, user_id: str, *, limit: int = 100) -> list[str]:
        owner = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        response = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=f"exports/{owner}/",
            MaxKeys=max(1, min(limit, 1000)),
        )
        return [item["Key"] for item in response.get("Contents", [])]

    def delete_for_user(self, user_id: str, *, limit: int = 100) -> int:
        keys = self.list_for_user(user_id, limit=limit)
        for artifact_key in keys:
            self.delete(artifact_key)
        return len(keys)

    @staticmethod
    def _build_client(region_name: str):
        import boto3

        return boto3.client("s3", region_name=region_name)
