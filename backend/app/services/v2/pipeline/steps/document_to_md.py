"""문서 → Markdown 변환 Step (전략 패턴)"""
from __future__ import annotations
import logging
from pathlib import Path
from app.services.v2.pipeline.base import PipelineStep, PipelineContext

logger = logging.getLogger(__name__)


class DocumentToMarkdownStep(PipelineStep):
    """
    문서를 Markdown 텍스트로 변환합니다.

    spec 옵션:
      strategy: "markitdown" | "ocr" | "vlm" (기본: "markitdown")
      model_id: str — VLM 전략에서 사용할 모델 ID (vlm 전략 필수)

    input: data의 각 row는 {"storage_uri": "s3://...", "filename": "..."}
    output: 각 row에 "markdown_text" 필드 추가
    """

    def run(self, ctx: PipelineContext, data: list[dict]) -> list[dict]:
        spec = ctx.spec.get("document_to_md", {})
        strategy = spec.get("strategy", "markitdown")

        result = []
        already_md = 0
        converted = 0

        for row in data:
            row = dict(row)

            # PRD media_reference: 添加来源文件引用字段
            if "filename" in row and "source_file" not in row:
                row["source_file"] = row["filename"]
            if ctx.dataset_id and "source_dataset_id" not in row:
                row["source_dataset_id"] = ctx.dataset_id

            # 已有非空 markdown_text 则跳过转换（来自 pipeline_run_task 预处理）
            if row.get("markdown_text"):
                row.setdefault("extraction_strategy", "passthrough")
                already_md += 1
                result.append(row)
                continue

            try:
                md = self._convert(row, strategy, spec, ctx)
                row["markdown_text"] = md
                row["extraction_strategy"] = strategy
                converted += 1
            except Exception as e:
                logger.warning(f"DocumentToMarkdown failed for {row.get('filename')}: {e}")
                row["markdown_text"] = ""
                row["extraction_error"] = str(e)
            result.append(row)

        ctx.meta["document_to_md"] = {
            "strategy": strategy,
            "processed": len(result),
            "converted": converted,
            "passthrough": already_md,
        }
        return result

    def _convert(self, row: dict, strategy: str, spec: dict, ctx: PipelineContext) -> str:
        filename = row.get("filename", "")
        content = row.get("content", b"")  # bytes 또는 문자열

        if strategy == "markitdown":
            return self._convert_markitdown(content, filename)
        elif strategy == "ocr":
            return self._convert_ocr(content, filename)
        elif strategy == "vlm":
            return self._convert_vlm(content, filename, spec, ctx)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def _convert_markitdown(self, content: bytes | str, filename: str) -> str:
        """MarkItDown으로 문서를 Markdown으로 변환"""
        try:
            from markitdown import MarkItDown
            import tempfile
            import os
            md_converter = MarkItDown()

            if isinstance(content, bytes):
                # 임시 파일 생성
                suffix = Path(filename).suffix or ".bin"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    result = md_converter.convert(tmp_path)
                    return result.text_content if hasattr(result, "text_content") else str(result)
                finally:
                    os.unlink(tmp_path)
            else:
                return str(content)
        except Exception as e:
            logger.warning(f"MarkItDown conversion failed for {filename}: {e}")
            # MarkItDown 실패 시 텍스트 디코딩으로 폴백
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="replace")
            return str(content)

    def _convert_ocr(self, content: bytes | str, filename: str) -> str:
        """PaddleOCR로 스캔 문서에서 텍스트 추출 (의존성 없을 시 빈 문자열)"""
        try:
            from paddleocr import PaddleOCR
            import tempfile
            import os

            ocr = PaddleOCR(use_angle_cls=True, lang="ch")
            if isinstance(content, bytes):
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    result = ocr.ocr(tmp_path, cls=True)
                    lines = []
                    for line in result:
                        if line:
                            for word_info in line:
                                if word_info and len(word_info) > 1:
                                    lines.append(word_info[1][0])
                    return "\n".join(lines)
                finally:
                    os.unlink(tmp_path)
            return ""
        except ImportError:
            logger.info("PaddleOCR not available, returning empty string")
            return ""
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return ""

    def _convert_vlm(self, content: bytes | str, filename: str, spec: dict, ctx: PipelineContext) -> str:
        """VLM(Claude/GPT-4V 등)으로 문서 이미지를 텍스트로 변환 (Stub)"""
        # VLM 호출은 실제 LLM 서비스와 연동이 필요하므로 stub 반환
        return f"[VLM extraction stub for: {filename}]"
