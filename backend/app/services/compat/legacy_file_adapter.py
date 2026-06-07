"""
v1 로컬 파일 저장 ↔ MinIO 호환 어댑터.
v1 코드가 로컬 경로로 저장한 파일을 MinIO로 동기화할 때 사용합니다.
"""
from __future__ import annotations

import os
from pathlib import Path

from app.config import settings
from app.services.storage_service import StorageService, get_storage_service


class LegacyFileAdapter:
    """v1의 로컬 uploads/ 파일을 MinIO media 버킷으로 복사합니다."""

    BUCKET = "media"

    def __init__(self, storage: StorageService | None = None):
        self._storage = storage or get_storage_service()

    def upload_from_local(self, local_path: str, key_prefix: str = "legacy") -> str:
        """
        로컬 파일을 MinIO로 업로드하고 URI를 반환합니다.
        key: {key_prefix}/{filename}
        """
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        key = f"{key_prefix}/{path.name}"
        content_type = self._guess_content_type(path.suffix)

        with open(local_path, "rb") as f:
            uri = self._storage.put_object(
                self.BUCKET, key, f, content_type=content_type
            )
        return uri

    def get_local_path(self, filename: str) -> str:
        """v1 업로드 디렉터리 내 파일의 전체 경로를 반환합니다."""
        return os.path.join(settings.uploads_dir, filename)

    @staticmethod
    def _guess_content_type(suffix: str) -> str:
        mapping = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".csv": "text/csv",
            ".json": "application/json",
            ".md": "text/markdown",
            ".txt": "text/plain",
        }
        return mapping.get(suffix.lower(), "application/octet-stream")
