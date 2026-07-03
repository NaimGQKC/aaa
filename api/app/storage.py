"""Object storage abstraction: local filesystem (dev) or S3-compatible
(MinIO in compose, Scaleway Object Storage in production).

Layout (spec §4.2):
  deals/{deal_id}/originals/{document_id}/{filename}
  deals/{deal_id}/derived/{document_id}/ocr/{n}.json
  deals/{deal_id}/reports/{report_id}.{ext}
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings


class Storage:
    def put(self, key: str, data: bytes) -> str:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError(f"storage key escapes root: {key}")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3Storage(Storage):
    def __init__(self) -> None:
        import boto3  # optional dependency [s3]

        s = get_settings()
        self.bucket = s.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name=s.s3_region,
        )
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = S3Storage() if s.storage_backend == "s3" else LocalStorage(s.local_storage_dir)
    return _storage


def original_key(deal_id: str, document_id: str, filename: str) -> str:
    return f"deals/{deal_id}/originals/{document_id}/{filename}"


def derived_key(deal_id: str, document_id: str, *parts: str) -> str:
    return f"deals/{deal_id}/derived/{document_id}/" + "/".join(parts)


def report_key(deal_id: str, report_id: str, ext: str) -> str:
    return f"deals/{deal_id}/reports/{report_id}.{ext}"
