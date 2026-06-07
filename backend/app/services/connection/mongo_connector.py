"""MongoDB Connector — SNAPSHOT 및 증분(기반 _id 수위선) 지원"""
from __future__ import annotations
import logging
from typing import Any
from app.services.connection.base import ConnectorBase

logger = logging.getLogger(__name__)


class MongoConnector(ConnectorBase):
    """
    MongoDB 데이터 소스 커넥터.

    config 예시:
    {
        "uri": "mongodb://user:pass@host:27017/dbname",
        "database": "mydb",
        "collection": "orders"   # 선택 사항, 미지정 시 list_resources()가 모든 컬렉션 반환
    }
    """

    def __init__(self, config: dict):
        self._config = config
        self._client = None
        self._db = None

    def _get_db(self):
        """MongoDB 데이터베이스 인스턴스를 반환 (지연 초기화)"""
        if self._db is None:
            try:
                from pymongo import MongoClient
                self._client = MongoClient(
                    self._config["uri"],
                    serverSelectionTimeoutMS=5000,
                )
                db_name = self._config.get("database", "")
                if not db_name:
                    # URI에서 데이터베이스 이름 파싱
                    db_name = self._config["uri"].split("/")[-1].split("?")[0] or "test"
                self._db = self._client[db_name]
            except ImportError:
                raise RuntimeError("pymongo 미설치, pip install pymongo 실행 필요")
        return self._db

    def test_connection(self) -> bool:
        """연결 테스트 — 성공 시 True, 실패 시 False 반환 (예외 미발생)"""
        try:
            db = self._get_db()
            db.list_collection_names()
            return True
        except Exception as e:
            logger.warning(f"MongoDB 연결 테스트 실패: {e}")
            return False

    def list_resources(self) -> list[str]:
        """데이터베이스의 모든 컬렉션 이름 반환"""
        try:
            return self._get_db().list_collection_names()
        except Exception as e:
            logger.warning(f"MongoDB list_resources 실패: {e}")
            return []

    def pull_sample(self, resource: str, limit: int = 100) -> list[dict]:
        """컬렉션에서 샘플 데이터 조회"""
        try:
            collection = self._get_db()[resource]
            docs = list(collection.find({}, {"_id": 0}).limit(limit))
            return docs
        except Exception as e:
            logger.warning(f"MongoDB pull_sample 실패: {e}")
            return []

    def pull_full(self, resource: str) -> list[dict]:
        """전체 데이터 조회 (_id 필드 제외, 직렬화 문제 방지)"""
        try:
            collection = self._get_db()[resource]
            docs = []
            for doc in collection.find({}, {"_id": 0}):
                docs.append(doc)
            return docs
        except Exception as e:
            logger.warning(f"MongoDB pull_full 실패: {e}")
            return []

    def pull_delta(self, resource: str, since: str | None = None) -> list[dict]:
        """
        증분 조회: _id(ObjectId는 삽입 타임스탬프 포함)를 수위선으로 사용.
        since에 이전 동기화의 최대 _id 문자열을 전달.
        """
        if not since:
            return self.pull_full(resource)
        try:
            from bson import ObjectId
            collection = self._get_db()[resource]
            docs = []
            for doc in collection.find({"_id": {"$gt": ObjectId(since)}}, {"_id": 0}):
                docs.append(doc)
            return docs
        except Exception as e:
            logger.warning(f"MongoDB pull_delta 실패: {e}")
            return self.pull_full(resource)
