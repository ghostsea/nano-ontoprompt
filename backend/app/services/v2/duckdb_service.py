"""DuckDB 임베디드 분석 엔진 서비스"""
from __future__ import annotations
import logging
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)

# DuckDB 가용성을 서브프로세스로 사전 검사 (import 자체가 크래시를 일으킬 수 있으므로)
def _probe_duckdb() -> bool:
    """별도 프로세스에서 DuckDB import 가능 여부 확인"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import duckdb; duckdb.connect(':memory:').close()"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


# 모듈 로드 시 한 번만 검사
_DUCKDB_PROBED: bool | None = None


def _is_duckdb_available() -> bool:
    global _DUCKDB_PROBED
    if _DUCKDB_PROBED is None:
        _DUCKDB_PROBED = _probe_duckdb()
    return _DUCKDB_PROBED


class DuckDBService:
    """DuckDB를 사용한 대용량 파일 처리 서비스"""

    def __init__(self, memory_limit: str = "2GB", threads: int = 4):
        self._memory_limit = memory_limit
        self._threads = threads
        self._conn = None
        # 프로브 결과를 기반으로 가용성 설정 (크래시 방지)
        if _is_duckdb_available():
            try:
                import duckdb
                self._conn = duckdb.connect(":memory:")
                self._conn.execute(f"SET memory_limit='{memory_limit}'")
                self._conn.execute(f"SET threads={threads}")
                self._available = True
            except Exception as e:
                logger.warning(f"DuckDB connection failed: {e}")
                self._available = False
                self._conn = None
        else:
            logger.info("DuckDB not available on this system (probe failed)")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def execute(self, sql: str, params: dict | None = None) -> list[dict]:
        """SQL 실행 후 결과를 dict 목록으로 반환"""
        if not self._available:
            raise RuntimeError("DuckDB not available")
        result = self._conn.execute(sql, list(params.values()) if params else [])
        cols = [desc[0] for desc in result.description]
        return [dict(zip(cols, row)) for row in result.fetchall()]

    def infer_schema(self, data: list[dict]) -> list[dict]:
        """데이터에서 schema를 추론 (컬럼명 + 타입 + null 비율) — pandas 기반, DuckDB 불필요"""
        if not data:
            return []
        import pandas as pd
        df = pd.DataFrame(data)
        schema = []
        for col in df.columns:
            null_pct = df[col].isna().sum() / len(df) * 100
            dtype = str(df[col].dtype)
            schema.append({
                "name": col,
                "type": self._map_dtype(dtype),
                "null_pct": round(null_pct, 2),
                "sample": str(df[col].dropna().iloc[0]) if not df[col].dropna().empty else None,
            })
        return schema

    def split_wide_table(self, data: list[dict], split_config: dict[str, list[str]]) -> dict[str, list[dict]]:
        """
        split_config 예시:
          {"clean_orders": ["order_id", "amount"], "clean_customers": ["customer_id", "name"]}
        각 테이블명 → 해당 컬럼의 데이터 (중복 제거) — 순수 Python, DuckDB 불필요
        """
        result = {}
        for table_name, columns in split_config.items():
            existing_cols = [c for c in columns if c in (data[0].keys() if data else [])]
            if not existing_cols:
                result[table_name] = []
                continue
            seen: set[str] = set()
            rows: list[dict] = []
            for row in data:
                sub = {c: row.get(c) for c in existing_cols}
                key = str(sorted(sub.items()))
                if key not in seen:
                    seen.add(key)
                    rows.append(sub)
            result[table_name] = rows
        return result

    def preview(self, data: list[dict], limit: int = 100) -> list[dict]:
        """데이터 미리보기 (Python 슬라이싱)"""
        return data[:limit]

    @staticmethod
    def _map_dtype(dtype: str) -> str:
        mapping = {
            "int64": "integer", "int32": "integer",
            "float64": "float", "float32": "float",
            "bool": "boolean", "object": "string",
            "datetime64": "datetime",
        }
        for k, v in mapping.items():
            if k in dtype:
                return v
        return "string"
