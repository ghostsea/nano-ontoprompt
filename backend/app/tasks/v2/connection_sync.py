"""
Celery 태스크 — Connection 동기화 (Milestone 1.4 stub)
실제 구현은 Milestone 1.5 이후에 추가됩니다.
"""
from __future__ import annotations


def sync_connection(connection_id: str, mode: str = "full") -> dict:
    """
    Connection 데이터를 동기화합니다.

    Args:
        connection_id: 동기화할 Connection ID
        mode: "full" | "delta"

    Returns:
        {"status": "ok", "rows": int}
    """
    pass


def sync_all_connections() -> list[dict]:
    """
    활성 상태인 모든 Connection을 순차적으로 동기화합니다.

    Returns:
        각 Connection 동기화 결과 목록
    """
    pass
