"""파일 업로드 Connector — MinIO 기반"""
from __future__ import annotations

import mimetypes
from typing import Any

from app.services.connection.base import ConnectorBase
from app.services.storage_service import StorageService, get_storage_service


class FileConnector(ConnectorBase):
    """
    로컬 파일 업로드를 Connection으로 취급하는 Connector.
    config 예시: {"bucket": "raw-datasets", "prefix": "uploads/conn-id/"}
    """

    BUCKET = "raw-datasets"

    def __init__(self, config: dict, storage: StorageService | None = None):
        self._config = config
        self._storage = storage or get_storage_service()
        self._prefix = config.get("prefix", "uploads/")

    def test_connection(self) -> bool:
        try:
            self._storage.ensure_bucket(self.BUCKET)
            return True
        except Exception:
            return False

    def list_resources(self) -> list[str]:
        """MinIO prefix 하위 파일 URI 목록"""
        return self._storage.list_prefix(self.BUCKET, self._prefix)

    def pull_sample(self, resource: str, limit: int = 100) -> list[dict]:
        """파일 메타정보를 반환 (실제 파싱은 Transform 단계에서)"""
        return [{"uri": resource, "type": "file"}]

    def pull_full(self, resource: str) -> bytes:
        """파일 내용을 bytes로 반환"""
        return self._storage.get_object(resource)

    def upload_file(self, filename: str, data: bytes, content_type: str = "") -> str:
        """파일을 MinIO에 업로드하고 URI를 반환"""
        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or "application/octet-stream"
        key = f"{self._prefix}{filename}"
        return self._storage.put_bytes(self.BUCKET, key, data, content_type)
