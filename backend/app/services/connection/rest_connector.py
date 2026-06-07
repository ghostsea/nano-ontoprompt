"""REST API Connector — 페이징 및 증분(since 파라미터) 지원"""
from __future__ import annotations
import logging
from typing import Any
from app.services.connection.base import ConnectorBase

logger = logging.getLogger(__name__)


class RestConnector(ConnectorBase):
    """
    REST API 데이터 소스 커넥터.

    config 예시:
    {
        "base_url": "https://api.example.com/v1",
        "endpoints": ["/orders", "/customers"],   # list_resources()가 이 목록 반환
        "auth": {
            "type": "bearer",   # bearer | basic | api_key
            "token": "xxx"      # bearer 토큰
        },
        "params": {"page_size": 100},     # 모든 요청에 추가할 공통 파라미터
        "pagination": {
            "type": "page",     # page | cursor | offset (현재 page 구현)
            "page_param": "page",
            "size_param": "page_size",
            "data_path": "data"   # JSON 응답에서 데이터 배열 필드명 (예: "data", "results")
        },
        "delta_param": "since"    # 증분 파라미터명, GET 요청에 ?since=<timestamp> 추가
    }
    """

    def __init__(self, config: dict):
        self._config = config
        self._session = None

    def _get_session(self):
        """httpx 세션 인스턴스 반환 (지연 초기화)"""
        if self._session is None:
            try:
                import httpx
            except ImportError:
                raise RuntimeError("httpx 미설치, pip install httpx 실행 필요")
            auth_cfg = self._config.get("auth", {})
            headers = {}
            if auth_cfg.get("type") == "bearer":
                headers["Authorization"] = f"Bearer {auth_cfg.get('token', '')}"
            elif auth_cfg.get("type") == "api_key":
                headers[auth_cfg.get("header", "X-API-Key")] = auth_cfg.get("token", "")
            self._session = httpx.Client(
                base_url=self._config.get("base_url", ""),
                headers=headers,
                timeout=30.0,
            )
        return self._session

    def test_connection(self) -> bool:
        """연결 테스트 — 첫 번째 엔드포인트에 요청하여 상태 확인"""
        endpoints = self._config.get("endpoints", [])
        if not endpoints:
            return False
        try:
            resp = self._get_session().get(endpoints[0], params={"page": 1, "page_size": 1})
            return resp.status_code < 400
        except Exception as e:
            logger.warning(f"REST 연결 테스트 실패: {e}")
            return False

    def list_resources(self) -> list[str]:
        """config에 정의된 엔드포인트 목록 반환"""
        return self._config.get("endpoints", [])

    def pull_sample(self, resource: str, limit: int = 100) -> list[dict]:
        """엔드포인트에서 샘플 데이터 조회"""
        try:
            params = dict(self._config.get("params", {}))
            params.update({"page": 1, "page_size": min(limit, 100)})
            resp = self._get_session().get(resource, params=params)
            resp.raise_for_status()
            return self._extract_records(resp.json())[:limit]
        except Exception as e:
            logger.warning(f"REST pull_sample 실패: {e}")
            return []

    def pull_full(self, resource: str) -> list[dict]:
        """페이징을 통해 전체 데이터 조회"""
        pagination = self._config.get("pagination", {})
        page_param = pagination.get("page_param", "page")
        size_param = pagination.get("size_param", "page_size")

        all_records = []
        page = 1
        base_params = dict(self._config.get("params", {}))

        try:
            session = self._get_session()
            while True:
                params = {**base_params, page_param: page, size_param: 100}
                resp = session.get(resource, params=params)
                resp.raise_for_status()
                data = resp.json()
                records = self._extract_records(data)
                if not records:
                    break
                all_records.extend(records)
                # 다음 페이지 존재 여부 확인
                if isinstance(data, dict):
                    if not data.get("next") and len(records) < 100:
                        break
                else:
                    break
                page += 1
                if page > 100:  # 안전 상한선
                    break
        except Exception as e:
            logger.warning(f"REST pull_full 실패: {e}")

        return all_records

    def pull_delta(self, resource: str, since: str | None = None) -> list[dict]:
        """증분 조회: since 파라미터를 쿼리스트링에 추가하여 요청"""
        if not since:
            return self.pull_full(resource)
        delta_param = self._config.get("delta_param", "since")
        try:
            params = dict(self._config.get("params", {}))
            params[delta_param] = since
            resp = self._get_session().get(resource, params=params)
            resp.raise_for_status()
            return self._extract_records(resp.json())
        except Exception as e:
            logger.warning(f"REST pull_delta 실패: {e}")
            return []

    def _extract_records(self, data: Any) -> list[dict]:
        """API 응답에서 레코드 목록 추출"""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            data_path = self._config.get("pagination", {}).get("data_path", "")
            for key in [data_path, "data", "results", "items", "records"]:
                if key and key in data and isinstance(data[key], list):
                    return data[key]
        return []
