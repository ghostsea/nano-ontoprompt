"""
MinIO 기반 오브젝트 스토리지 서비스.
버킷: raw-datasets, curated-datasets, media, intermediate
"""
from __future__ import annotations

import io
import os
from typing import BinaryIO

import logging

try:
    from minio import Minio
    from minio.error import S3Error
    _MINIO_AVAILABLE = True
except ImportError:
    Minio = None  # type: ignore
    S3Error = Exception  # type: ignore
    _MINIO_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)

BUCKETS = ["raw-datasets", "curated-datasets", "media", "intermediate"]


class StorageService:
    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool | None = None,
    ):
        self._available = False
        if not _MINIO_AVAILABLE:
            logger.warning("MinIO client not installed — storage unavailable")
            self._client = None
            return
        try:
            self._client = Minio(
                endpoint or settings.minio_endpoint,
                access_key=access_key or settings.minio_access_key,
                secret_key=secret_key or settings.minio_secret_key,
                secure=secure if secure is not None else settings.minio_use_ssl,
            )
            self._client.list_buckets()  # 연결 검증
            self._available = True
            logger.info("MinIO connected")
        except Exception as e:
            logger.warning(f"MinIO unavailable: {e}")
            self._available = False

    # ── 本地文件系统 fallback ─────────────────────────────────────
    _LOCAL_BASE = os.path.join(os.path.dirname(__file__), "../../../../storage")

    @property
    def available(self) -> bool:
        return True  # 本地 fallback 始终可用

    def _require_available(self):
        pass  # 本地 fallback 不需要 MinIO

    def _local_path(self, bucket: str, key: str) -> str:
        p = os.path.join(self._LOCAL_BASE, bucket, key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def ensure_bucket(self, bucket: str) -> None:
        """버킷이 없으면 생성합니다."""
        self._require_available()
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    def ensure_default_buckets(self) -> None:
        """4개 기본 버킷을 모두 초기화합니다."""
        for b in BUCKETS:
            self.ensure_bucket(b)

    def put_object(
        self,
        bucket: str,
        key: str,
        data: BinaryIO,
        content_type: str = "application/octet-stream",
        length: int = -1,
    ) -> str:
        """오브젝트를 업로드하고 URI(s3://bucket/key)를 반환합니다."""
        self.ensure_bucket(bucket)
        # minio-py는 length=-1 시 chunked read 사용
        self._client.put_object(
            bucket, key, data, length=length, content_type=content_type
        )
        return f"s3://{bucket}/{key}"

    def put_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """bytes를 업로드합니다. MinIO 미연결 시 로컬 파일로 fallback."""
        if self._available and self._client:
            return self.put_object(bucket, key, io.BytesIO(data), content_type, length=len(data))
        # 로컬 fallback
        local = self._local_path(bucket, key)
        with open(local, "wb") as f:
            f.write(data)
        return f"s3://{bucket}/{key}"

    def get_object(self, uri: str) -> bytes:
        """s3://bucket/key URI로부터 오브젝트를 다운로드합니다. 로컬 fallback 포함."""
        bucket, key = self._parse_uri(uri)
        if self._available and self._client:
            resp = self._client.get_object(bucket, key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        # 로컬 fallback
        local = self._local_path(bucket, key)
        if os.path.exists(local):
            with open(local, "rb") as f:
                return f.read()
        raise FileNotFoundError(f"Object not found locally: {uri}")

    def get_stream(self, uri: str) -> BinaryIO:
        """s3://bucket/key URI로부터 스트림을 반환합니다."""
        bucket, key = self._parse_uri(uri)
        return self._client.get_object(bucket, key)

    def presigned_get(self, uri: str, expires_seconds: int = 3600) -> str:
        """다운로드용 presigned URL을 생성합니다."""
        from datetime import timedelta
        bucket, key = self._parse_uri(uri)
        url = self._client.presigned_get_object(
            bucket, key, expires=timedelta(seconds=expires_seconds)
        )
        return url

    def delete_object(self, uri: str) -> None:
        """오브젝트를 삭제합니다."""
        bucket, key = self._parse_uri(uri)
        self._client.remove_object(bucket, key)

    def list_prefix(self, bucket: str, prefix: str) -> list[str]:
        """prefix 하위의 오브젝트 키 목록을 반환합니다."""
        objects = self._client.list_objects(bucket, prefix=prefix, recursive=True)
        return [f"s3://{bucket}/{obj.object_name}" for obj in objects]

    def object_exists(self, uri: str) -> bool:
        """오브젝트 존재 여부를 확인합니다."""
        bucket, key = self._parse_uri(uri)
        try:
            self._client.stat_object(bucket, key)
            return True
        except S3Error:
            return False

    @staticmethod
    def _parse_uri(uri: str) -> tuple[str, str]:
        """s3://bucket/key → (bucket, key)"""
        if not uri.startswith("s3://"):
            raise ValueError(f"Invalid storage URI: {uri!r}. Expected s3://bucket/key")
        path = uri[5:]
        bucket, _, key = path.partition("/")
        if not bucket or not key:
            raise ValueError(f"Invalid storage URI: {uri!r}")
        return bucket, key


# 싱글턴 인스턴스 (FastAPI 의존성 주입에서 사용)
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
