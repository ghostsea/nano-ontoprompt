"""安全的 Cypher 查询构建器 — 防注入"""
from __future__ import annotations
import re


LABEL_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')


def validate_label(label: str) -> str:
    """校验 Neo4j 标签名 (防注入)"""
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
    depth = max(1, min(depth, 5))  # 最多 5 层
    return (
        f"MATCH (n:{label} {{id: $id}})-[r*1..{depth}]-(m) RETURN n, r, m LIMIT 100",
        {"id": node_id},
    )


def build_shortest_path(src_id: str, tgt_id: str) -> tuple[str, dict]:
    return (
        "MATCH (s {id: $src}), (t {id: $tgt}), p = shortestPath((s)-[*]-(t)) RETURN p",
        {"src": src_id, "tgt": tgt_id},
    )
