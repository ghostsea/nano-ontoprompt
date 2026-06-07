"""안전한 Cypher 쿼리 빌더 — SQL 인젝션 방어"""
from __future__ import annotations
import re


LABEL_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


def validate_label(label: str) -> str:
    """Neo4j 레이블 이름 검증 (인젝션 방어)"""
    if not LABEL_PATTERN.match(label):
        raise ValueError(f"Invalid Neo4j label: {label!r}")
    return label


def build_match_by_id(label: str, node_id: str) -> tuple[str, dict]:
    label = validate_label(label)
    return (
        f"MATCH (n:{label} {{id: $id}}) RETURN n",
        {"id": node_id},
    )


def build_neighbors(label: str, node_id: str, depth: int = 1) -> tuple[str, dict]:
    label = validate_label(label)
    depth = max(1, min(depth, 5))  # 최대 5단계
    return (
        f"MATCH (n:{label} {{id: $id}})-[r*1..{depth}]-(m) RETURN n, r, m LIMIT 100",
        {"id": node_id},
    )


def build_shortest_path(src_id: str, tgt_id: str) -> tuple[str, dict]:
    return (
        "MATCH (s {id: $src}), (t {id: $tgt}), p = shortestPath((s)-[*]-(t)) RETURN p",
        {"src": src_id, "tgt": tgt_id},
    )
