"""Pipeline Route C 테스트 — DocumentToMarkdown + MarkdownToStructured"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.v2.pipeline.base import PipelineContext
from app.services.v2.pipeline.steps.document_to_md import DocumentToMarkdownStep
from app.services.v2.pipeline.steps.md_to_structured import MarkdownToStructuredStep
from app.services.v2.pipeline.engine import execute_route_c


def make_ctx(spec=None):
    ctx = PipelineContext(dataset_id="test-ds", version_no=1, route="C")
    if spec:
        ctx.spec = spec
    return ctx


SAMPLE_MD_ROW = {
    "filename": "policy.pdf",
    "markdown_text": """# Policy\n\nDate: 2024-01-15\nAuthor: John\nDepartment: Legal""",
}


# ── DocumentToMarkdownStep ─────────────────────────────────────────────

def test_document_to_md_markitdown_bytes():
    """bytes 컨텐츠를 markitdown 전략으로 처리"""
    step = DocumentToMarkdownStep()
    ctx = make_ctx({"document_to_md": {"strategy": "markitdown"}})
    data = [{"filename": "test.txt", "content": b"Hello world content"}]
    result = step.run(ctx, data)
    assert len(result) == 1
    assert "markdown_text" in result[0]
    assert result[0]["extraction_strategy"] == "markitdown"


def test_document_to_md_string_content():
    """문자열 컨텐츠 처리"""
    step = DocumentToMarkdownStep()
    ctx = make_ctx({"document_to_md": {"strategy": "markitdown"}})
    data = [{"filename": "note.txt", "content": "Simple text content"}]
    result = step.run(ctx, data)
    assert result[0]["markdown_text"] != "" or "extraction_error" not in result[0]


def test_document_to_md_ocr_no_paddleocr():
    """PaddleOCR 없을 때 빈 문자열 반환 (graceful fallback)"""
    step = DocumentToMarkdownStep()
    ctx = make_ctx({"document_to_md": {"strategy": "ocr"}})
    data = [{"filename": "scan.png", "content": b"\x89PNG\r\n"}]
    result = step.run(ctx, data)
    assert len(result) == 1
    assert "markdown_text" in result[0]  # 오류 없이 처리됨


def test_document_to_md_vlm_stub():
    """VLM 전략은 stub 텍스트 반환"""
    step = DocumentToMarkdownStep()
    ctx = make_ctx({"document_to_md": {"strategy": "vlm"}})
    data = [{"filename": "chart.png", "content": b""}]
    result = step.run(ctx, data)
    assert "VLM extraction stub" in result[0]["markdown_text"]


def test_document_to_md_sets_meta():
    """처리 후 ctx.meta에 통계 기록"""
    step = DocumentToMarkdownStep()
    ctx = make_ctx({"document_to_md": {"strategy": "markitdown"}})
    step.run(ctx, [{"filename": "f.txt", "content": b"test"}])
    assert "document_to_md" in ctx.meta
    assert ctx.meta["document_to_md"]["processed"] == 1


def test_document_to_md_error_graceful():
    """변환 오류 시 빈 markdown_text + error 필드 반환"""
    step = DocumentToMarkdownStep()
    ctx = make_ctx({"document_to_md": {"strategy": "markitdown"}})
    # content 없는 row
    data = [{"filename": "mystery.pdf"}]
    result = step.run(ctx, data)
    assert len(result) == 1
    assert "markdown_text" in result[0]


# ── MarkdownToStructuredStep ───────────────────────────────────────────

def test_md_to_structured_no_schema_passthrough():
    """target_schema 없으면 데이터 그대로 통과"""
    step = MarkdownToStructuredStep()
    ctx = make_ctx({"md_to_structured": {}})
    result = step.run(ctx, [SAMPLE_MD_ROW])
    assert result[0] == SAMPLE_MD_ROW


def test_md_to_structured_with_mock_llm():
    """LLM mock으로 구조화 추출 성공 케이스"""
    step = MarkdownToStructuredStep()
    ctx = make_ctx({
        "md_to_structured": {
            "target_schema": {"date": "날짜", "author": "작성자"},
            "model_id": "test-model",
        }
    })
    with patch("app.services.v2.pipeline.steps.md_to_structured.MarkdownToStructuredStep._extract") as mock_extract:
        mock_extract.return_value = {"date": "2024-01-15", "author": "John"}
        result = step.run(ctx, [SAMPLE_MD_ROW])
    assert result[0]["date"] == "2024-01-15"
    assert result[0]["author"] == "John"
    assert result[0]["structured_extraction_ok"] is True


def test_md_to_structured_llm_failure_graceful():
    """LLM 호출 실패 시 오류 필드 추가 (크래시 없음)"""
    step = MarkdownToStructuredStep()
    ctx = make_ctx({
        "md_to_structured": {
            "target_schema": {"date": "날짜"},
        }
    })
    with patch("app.services.v2.pipeline.steps.md_to_structured.MarkdownToStructuredStep._extract",
               side_effect=RuntimeError("LLM timeout")):
        result = step.run(ctx, [SAMPLE_MD_ROW])
    assert result[0]["structured_extraction_ok"] is False
    assert "structured_extraction_error" in result[0]


def test_md_to_structured_no_markdown_text():
    """markdown_text 없는 row는 그대로 통과"""
    step = MarkdownToStructuredStep()
    ctx = make_ctx({
        "md_to_structured": {"target_schema": {"date": "날짜"}}
    })
    data = [{"filename": "test.pdf"}]  # markdown_text 없음
    result = step.run(ctx, data)
    assert len(result) == 1


# ── Route C 통합 테스트 ───────────────────────────────────────────────

def test_execute_route_c_basic():
    """Route C 전체 체인 실행 (빈 content → markitdown)"""
    ctx = make_ctx({
        "document_to_md": {"strategy": "markitdown"},
        "md_to_structured": {"target_schema": {"date": "날짜"}},
    })
    data = [{"filename": "test.txt", "content": b"Report date: 2024-01-15"}]
    result, ctx2 = execute_route_c(ctx, data)
    assert len(result) == 1
    assert ctx2.rows_out == 1
    assert "markdown_text" in result[0]


def test_execute_route_c_empty():
    """빈 데이터 입력"""
    ctx = make_ctx({"document_to_md": {"strategy": "markitdown"}})
    result, ctx2 = execute_route_c(ctx, [])
    assert result == []
    assert ctx2.rows_out == 0


def test_execute_route_c_preserves_filename():
    """filename 필드가 유지됨"""
    ctx = make_ctx({"document_to_md": {"strategy": "markitdown"}})
    data = [{"filename": "report.pdf", "content": b"content"}]
    result, _ = execute_route_c(ctx, data)
    assert result[0]["filename"] == "report.pdf"
