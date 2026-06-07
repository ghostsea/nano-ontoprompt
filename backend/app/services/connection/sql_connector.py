"""관계형 DB Connector — MySQL / PostgreSQL"""
from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, inspect, text

from app.services.connection.base import ConnectorBase


class SQLConnector(ConnectorBase):
    """
    SQLAlchemy 기반 관계형 DB Connector.
    config 예시:
      {
        "connection_string": "postgresql://user:pass@host:5432/db",
        "query": "SELECT * FROM orders",
        "watermark_column": "updated_at"   # APPEND 모드용
      }
    """

    def __init__(self, config: dict):
        self._config = config
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            self._engine = create_engine(
                self._config["connection_string"],
                pool_pre_ping=True,
                connect_args={"connect_timeout": 10},
            )
        return self._engine

    def test_connection(self) -> bool:
        try:
            with self._get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def list_resources(self) -> list[str]:
        """데이터베이스 내 테이블 목록 반환"""
        inspector = inspect(self._get_engine())
        return inspector.get_table_names()

    def pull_sample(self, resource: str, limit: int = 100) -> list[dict]:
        """테이블에서 샘플 데이터 조회"""
        with self._get_engine().connect() as conn:
            result = conn.execute(
                text(f"SELECT * FROM {resource} LIMIT :limit"),
                {"limit": limit},
            )
            cols = list(result.keys())
            return [dict(zip(cols, row)) for row in result]

    def pull_full(self, resource: str) -> list[dict]:
        """테이블 전체 데이터 조회"""
        import pandas as pd
        query = self._config.get("query") or f"SELECT * FROM {resource}"
        return pd.read_sql(query, self._get_engine()).to_dict(orient="records")

    def pull_delta(self, resource: str, since: str | None = None) -> list[dict]:
        """증분 데이터 조회 (watermark_column 기반)"""
        watermark_col = self._config.get("watermark_column")
        if not watermark_col or not since:
            return self.pull_full(resource)

        base_query = self._config.get("query") or f"SELECT * FROM {resource}"
        # 서브쿼리로 감싸서 WHERE 절 추가
        delta_query = f"""
            SELECT * FROM ({base_query}) _t
            WHERE {watermark_col} > :since
        """
        with self._get_engine().connect() as conn:
            result = conn.execute(text(delta_query), {"since": since})
            cols = list(result.keys())
            return [dict(zip(cols, row)) for row in result]
