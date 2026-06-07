"""Connector 추상 기반 클래스"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class ConnectorBase(ABC):
    """모든 Connector가 구현해야 하는 인터페이스"""

    @abstractmethod
    def test_connection(self) -> bool:
        """연결 테스트. 성공 시 True, 실패 시 False 또는 예외."""
        ...

    @abstractmethod
    def list_resources(self) -> list[str]:
        """사용 가능한 리소스 목록 (테이블명, 컬렉션명, 엔드포인트 등)."""
        ...

    @abstractmethod
    def pull_sample(self, resource: str, limit: int = 100) -> list[dict]:
        """샘플 데이터 (최대 limit 행) 조회."""
        ...

    @abstractmethod
    def pull_full(self, resource: str) -> Any:
        """전체 데이터를 반환. 대용량은 제너레이터 또는 파일 경로로 반환 가능."""
        ...

    def pull_delta(self, resource: str, since: str | None = None) -> Any:
        """증분 데이터 조회. 기본 구현은 pull_full과 동일."""
        return self.pull_full(resource)
