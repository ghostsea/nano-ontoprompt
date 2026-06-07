"""NL2CypherService 单元测试（LLM Mock）"""
import pytest
from unittest.mock import patch
from app.services.v2.graph.nl2cypher import NL2CypherService, CypherPlan


def test_rule_translate_all_nodes():
    svc = NL2CypherService()
    plan = svc._rule_translate("所有节点有哪些")
    assert "MATCH" in plan.cypher
    assert plan.confidence > 0


def test_rule_translate_default():
    svc = NL2CypherService()
    plan = svc._rule_translate("随便一个查询")
    assert "MATCH (n)" in plan.cypher
    assert plan.confidence == 0.3


def test_validate_read_only_blocks_create():
    svc = NL2CypherService()
    with pytest.raises(ValueError, match="CREATE"):
        svc._validate_read_only("CREATE (n:Test) RETURN n")


def test_validate_read_only_blocks_delete():
    svc = NL2CypherService()
    with pytest.raises(ValueError, match="DELETE"):
        svc._validate_read_only("MATCH (n) DELETE n")


def test_validate_read_only_allows_match():
    svc = NL2CypherService()
    svc._validate_read_only("MATCH (n) WHERE n.id = $id RETURN n LIMIT 10")


def test_translate_falls_back_on_llm_error():
    svc = NL2CypherService()
    with patch.object(svc, '_llm_translate', side_effect=Exception("no API")):
        plan = svc.translate("有哪些供应商")
    assert isinstance(plan, CypherPlan)
    assert "MATCH" in plan.cypher


def test_translate_uses_llm_when_available():
    svc = NL2CypherService()
    expected = CypherPlan(
        cypher="MATCH (n:Supplier) WHERE n.ontology_id = $ontology_id RETURN n LIMIT 20",
        explanation="查询所有供应商",
        confidence=0.95,
    )
    with patch.object(svc, '_llm_translate', return_value=expected):
        plan = svc.translate("有哪些供应商")
    assert plan.cypher == expected.cypher
    assert plan.confidence == 0.95
