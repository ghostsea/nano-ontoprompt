"""ChromaDB 벡터 데이터베이스 서비스"""
from __future__ import annotations
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import chromadb
except ImportError:
    chromadb = None


class ChromaService:
    """ChromaDB 연결 및 벡터 저장/검색 서비스"""

    def __init__(self, host: str | None = None, port: int | None = None):
        from app.config import settings
        self._host = host or settings.chroma_host
        self._port = port or settings.chroma_port
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        try:
            if chromadb is None:
                raise ImportError("chromadb not installed")
            self._client = chromadb.HttpClient(host=self._host, port=self._port)
            self._client.heartbeat()
            self._available = True
            logger.info("ChromaDB connected")
        except Exception as e:
            logger.warning(f"ChromaDB unavailable: {e}")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    # ── 컬렉션 관리 ──────────────────────────────────────────────────

    def get_or_create_collection(self, name: str) -> Any | None:
        """컬렉션 반환 또는 생성 (코사인 거리 사용)"""
        if not self._available:
            return None
        try:
            return self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            logger.warning(f"ChromaDB collection error: {e}")
            return None

    def delete_collection(self, name: str) -> bool:
        if not self._available:
            return False
        try:
            self._client.delete_collection(name)
            return True
        except Exception:
            return False

    # ── 쓰기 ─────────────────────────────────────────────────────────

    def upsert_entities(self, ontology_id: str, entities: list[dict]) -> int:
        """엔티티를 컬렉션에 업서트 (텍스트 임베딩 자동)"""
        if not self._available or not entities:
            return 0
        collection = self.get_or_create_collection(f"ontology_{ontology_id}")
        if not collection:
            return 0

        ids = [e.get("id", str(i)) for i, e in enumerate(entities)]
        documents = [self._entity_to_text(e) for e in entities]
        metadatas = [
            {
                "entity_type": str(e.get("type", "")),
                "name_cn": str(e.get("name_cn", "")),
                "name_en": str(e.get("name_en", "")),
                "confidence": float(e.get("confidence", 0.0)),
            }
            for e in entities
        ]

        try:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            return len(ids)
        except Exception as e:
            logger.warning(f"ChromaDB upsert error: {e}")
            return 0

    def delete_entities(self, ontology_id: str, entity_ids: list[str]) -> bool:
        """지정 ID의 엔티티 삭제"""
        if not self._available:
            return False
        collection = self.get_or_create_collection(f"ontology_{ontology_id}")
        if not collection:
            return False
        try:
            collection.delete(ids=entity_ids)
            return True
        except Exception:
            return False

    # ── 검색 ─────────────────────────────────────────────────────────

    def semantic_search(
        self,
        ontology_id: str,
        query: str,
        n_results: int = 10,
        entity_type: str | None = None,
    ) -> list[dict]:
        """시맨틱 검색 — ChromaDB 벡터 유사도 검색"""
        if not self._available:
            return []
        collection = self.get_or_create_collection(f"ontology_{ontology_id}")
        if not collection:
            return []

        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if entity_type:
            kwargs["where"] = {"entity_type": entity_type}

        try:
            results = collection.query(**kwargs)
            hits = []
            ids = results.get("ids", [[]])[0]
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for i, eid in enumerate(ids):
                hits.append({
                    "id": eid,
                    "document": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "score": 1.0 - (distances[i] if i < len(distances) else 1.0),
                })
            return hits
        except Exception as e:
            logger.warning(f"ChromaDB search error: {e}")
            return []

    def keyword_search(
        self,
        ontology_id: str,
        keyword: str,
        n_results: int = 20,
    ) -> list[dict]:
        """키워드 검색 — document에 keyword가 포함된 결과 필터링"""
        if not self._available:
            return []
        collection = self.get_or_create_collection(f"ontology_{ontology_id}")
        if not collection:
            return []

        try:
            results = collection.query(
                query_texts=[keyword],
                n_results=n_results,
                where_document={"$contains": keyword},
                include=["documents", "metadatas"],
            )
            ids = results.get("ids", [[]])[0]
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            return [
                {"id": ids[i], "document": docs[i], "metadata": metas[i]}
                for i in range(len(ids))
            ]
        except Exception as e:
            logger.warning(f"ChromaDB keyword search error: {e}")
            return []

    def count(self, ontology_id: str) -> int:
        """컬렉션 내 문서 수"""
        if not self._available:
            return 0
        collection = self.get_or_create_collection(f"ontology_{ontology_id}")
        if not collection:
            return 0
        try:
            return collection.count()
        except Exception:
            return 0

    @staticmethod
    def _entity_to_text(entity: dict) -> str:
        """엔티티 → 임베딩용 텍스트 변환"""
        parts = [
            entity.get("name_cn", ""),
            entity.get("name_en", ""),
            entity.get("type", ""),
            entity.get("description", ""),
            json.dumps(entity.get("properties", {}), ensure_ascii=False),
        ]
        return " ".join(p for p in parts if p)


def get_chroma_service() -> ChromaService:
    return ChromaService()
