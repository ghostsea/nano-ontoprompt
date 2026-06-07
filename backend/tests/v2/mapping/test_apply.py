"""MappingService.apply_mapping 单元测试"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.v2.mapping.mapping_service import MappingService
from app.models.v2.mapping import OntologyMapping


def make_mapping_obj(field_mapping=None):
    m = OntologyMapping(
        id="map-1",
        ontology_id="ont-1",
        curated_dataset_id="ds-1",
        entity_class="Order",
        field_mapping=field_mapping or {
            "order_id": "id",
            "customer_name": "customerName",
            "__primary_key__": "order_id",
        },
        status="draft",
        confidence=0.9,
    )
    return m


def make_db(mapping_obj):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = mapping_obj
    db.commit = MagicMock()
    return db


DATA = [
    {"order_id": "ORD-001", "customer_name": "Alice", "amount": "1200"},
    {"order_id": "ORD-002", "customer_name": "Bob",   "amount": "800"},
]


def test_apply_mapping_returns_summary():
    db = make_db(make_mapping_obj())
    svc = MappingService(db)
    with patch("app.services.v2.graph.neo4j_service.GraphDatabase") as mock_neo4j:
        mock_neo4j.driver.side_effect = Exception("offline")
        result = svc.apply_mapping("map-1", DATA)
    assert result["total_rows"] == 2
    assert result["entity_class"] == "Order"
    assert result["mapping_id"] == "map-1"


def test_apply_mapping_updates_status():
    m = make_mapping_obj()
    db = make_db(m)
    svc = MappingService(db)
    with patch("app.services.v2.graph.neo4j_service.GraphDatabase") as mock_neo4j:
        mock_neo4j.driver.side_effect = Exception("offline")
        svc.apply_mapping("map-1", DATA)
    assert m.status == "applied"
    db.commit.assert_called()


def test_apply_mapping_not_found_raises():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    svc = MappingService(db)
    with pytest.raises(ValueError, match="not found"):
        svc.apply_mapping("nonexistent", DATA)


def test_apply_mapping_empty_data():
    db = make_db(make_mapping_obj())
    svc = MappingService(db)
    with patch("app.services.v2.graph.neo4j_service.GraphDatabase") as mock_neo4j:
        mock_neo4j.driver.side_effect = Exception("offline")
        result = svc.apply_mapping("map-1", [])
    assert result["total_rows"] == 0


def test_create_mapping_saves_to_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    svc = MappingService(db)
    svc.create_mapping(
        ontology_id="ont-1",
        curated_dataset_id="ds-1",
        entity_class="Order",
        field_mapping={"order_id": "id"},
    )
    db.add.assert_called_once()
    db.commit.assert_called_once()
