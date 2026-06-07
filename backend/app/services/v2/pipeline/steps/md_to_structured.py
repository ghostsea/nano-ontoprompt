"""Markdown → 구조화 JSON 추출 Step"""
from __future__ import annotations
import json
import re
import logging
from app.services.v2.pipeline.base import PipelineStep, PipelineContext

logger = logging.getLogger(__name__)


def _get_first_model():
    """DB 에서 첫 번째 사용 가능한 LLM 모델 설정 반환"""
    try:
        from app.database import SessionLocal
        from app.models.model_config import ModelConfig
        db = SessionLocal()
        try:
            return db.query(ModelConfig).first()
        finally:
            db.close()
    except Exception:
        return None


def _call_with_model(model_config, messages: list[dict]) -> str | None:
    """사용자 설정 모델을 사용해 LLM 호출"""
    if not model_config:
        return None
    try:
        from app.services import encryption_service
        from app.services.llm_service import _call_llm
        api_key = encryption_service.decrypt(model_config.api_key_encrypted) if model_config.api_key_encrypted else ""
        model_name = (model_config.models or ["gpt-3.5-turbo"])[0]
        return _call_llm(
            model_config.provider, api_key, model_config.api_base,
            model_name, messages
        )
    except Exception as e:
        logger.info(f"LLM call failed: {e}")
        return None


class MarkdownToStructuredStep(PipelineStep):
    """
    Markdown 텍스트에서 구조화 필드를 추출합니다.

    spec 옵션:
      target_schema: dict  — 추출할 필드 정의 {field_name: "description"}（없으면 자동 추론）
      model_id: str        — 사용할 LLM 모델 ID
      prompt_template: str — 커스텀 프롬프트

    input:  row에 "markdown_text" 필드 포함
    output: 구조화 필드 + extraction_method 필드 추가
    """

    EXTRACT_PROMPT = """다음 문서에서 아래 필드를 추출하세요. JSON으로만 반환하세요.

필드 목록:
{schema}

문서:
{text}

출력 형식 (JSON만, 설명 없이):
{{"field1": "value1", "field2": "value2"}}"""

    AUTO_SCHEMA_PROMPT = """다음 문서를 분석하고, 이 문서 유형에 가장 유용한 구조화 필드 5~10개를 추출하세요.
필드 이름은 영문 snake_case로, 값은 문서에서 실제로 찾을 수 있는 것만 포함하세요.

문서:
{text}

출력 형식 (JSON만, 설명 없이):
{{"field1": "extracted_value1", "field2": "extracted_value2"}}"""

    def run(self, ctx: PipelineContext, data: list[dict]) -> list[dict]:
        spec = ctx.spec.get("md_to_structured", {})
        target_schema = spec.get("target_schema", {})
        model_id = spec.get("model_id", "")

        model_config = _get_first_model()

        # target_schema 없으면 자동 추론 또는 규칙 기반 추출
        if not target_schema:
            sample_md = next((r.get("markdown_text", "") for r in data if r.get("markdown_text")), "")
            if sample_md and model_config:
                # LLM으로 자동 추출 시도
                result = self._auto_extract_with_llm(data, model_config)
                if result:
                    ctx.meta["md_to_structured"] = {
                        "method": "llm_auto", "processed": len(data), "success": len(result)
                    }
                    return result
            # 규칙 기반 폴백
            return self._rule_based_extract(data, ctx)

        # target_schema 있으면 LLM 필드 추출
        result, success = [], 0
        for row in data:
            md_text = row.get("markdown_text", "")
            if not md_text:
                result.append(row)
                continue
            try:
                extracted = self._extract_fields(md_text, target_schema, model_config)
                row = dict(row)
                row.update(extracted)
                row["extraction_method"] = "llm_schema"
                row["structured_extraction_ok"] = True
                success += 1
            except Exception as e:
                logger.warning(f"MarkdownToStructured failed: {e}")
                row = dict(row)
                row["structured_extraction_ok"] = False
            result.append(row)

        ctx.meta["md_to_structured"] = {
            "method": "llm_schema",
            "processed": len(data),
            "success": success,
            "schema_fields": list(target_schema.keys()),
        }
        return result

    # ── LLM 자동 추출（target_schema 없을 때）───────────────────────────────

    def _auto_extract_with_llm(self, data: list[dict], model_config) -> list[dict] | None:
        """LLM에게 schema 추론 + 추출을 한 번에 요청"""
        result = []
        for row in data:
            md = row.get("markdown_text", "")
            if not md:
                result.append(row)
                continue
            resp = _call_with_model(model_config, [
                {"role": "system", "content": "You are a structured data extraction expert. Return valid JSON only."},
                {"role": "user", "content": self.AUTO_SCHEMA_PROMPT.format(text=md[:4000])},
            ])
            if resp is None:
                return None  # LLM 실패 → 규칙 기반으로 폴백
            try:
                text = resp.strip()
                if "```" in text:
                    text = re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
                    text = text.group(1).strip() if text else resp
                extracted = json.loads(text)
                row = dict(row)
                row.update({str(k): str(v) for k, v in extracted.items()})
                row["extraction_method"] = "llm_auto"
            except Exception:
                row = dict(row)
                row["extraction_method"] = "llm_auto_parse_error"
            result.append(row)
        return result

    # ── LLM 필드 추출（target_schema 있을 때）───────────────────────────────

    def _extract_fields(self, md_text: str, schema: dict, model_config) -> dict:
        """LLM으로 target_schema에 따라 필드 추출"""
        schema_str = "\n".join(f"- {k}: {v}" for k, v in schema.items())
        resp = _call_with_model(model_config, [
            {"role": "system", "content": "You are a structured data extraction assistant. Return valid JSON only."},
            {"role": "user", "content": self.EXTRACT_PROMPT.format(schema=schema_str, text=md_text[:4000])},
        ])
        if resp is None:
            return {k: "" for k in schema}
        try:
            text = resp.strip()
            if "```" in text:
                m = re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
                text = m.group(1).strip() if m else text
            return json.loads(text)
        except Exception:
            return {k: "" for k in schema}

    # ── 규칙 기반 폴백 ──────────────────────────────────────────────────────

    def _rule_based_extract(self, data: list[dict], ctx: PipelineContext) -> list[dict]:
        """LLM 없을 때 정규식으로 구조화 정보 추출 (PRD: 규칙/엔터티/수치 탐지)"""
        result = []
        for row in data:
            md = row.get("markdown_text", "")
            if not md:
                result.append(row)
                continue

            row = dict(row)

            # ① IF-THEN 규칙 추출
            rules = re.findall(
                r'IF\s+(.+?)\s+THEN\s+(.+?)(?=\n|$)',
                md, re.IGNORECASE | re.MULTILINE
            )
            row["rule_count"] = len(rules)
            if rules:
                row["rules_sample"] = "; ".join(
                    f"[{r[0].strip()[:40]}] → [{r[1].strip()[:40]}]" for r in rules[:3]
                )

            # ② Markdown 섹션 추출
            section_titles = re.findall(r'^#{1,3}\s+(.+)$', md, re.MULTILINE)
            row["section_count"] = len(section_titles)
            row["sections"] = ", ".join(section_titles[:6])

            # ③ 테이블에서 숫자 키-값 추출
            numeric_kvs = re.findall(r'\|\s*([^\|]+)\s*\|\s*(\d[\d,\.]*)\s*\|', md)
            if numeric_kvs:
                row["numeric_fields"] = json.dumps(
                    {k.strip(): v for k, v in numeric_kvs[:8]},
                    ensure_ascii=False
                )

            # ④ 중국어 기업/조직명 추출
            org_names = re.findall(
                r'[一-龥]{2,10}(?:公司|集团|科技|物流|铝业|五金|包装|原材料)',
                md
            )
            if org_names:
                row["organizations"] = ", ".join(list(dict.fromkeys(org_names))[:8])

            # ⑤ 숫자 임계값 (안전재고, 납기 등)
            thresholds = re.findall(r'(\d[\d,\.]+)\s*(?:万元?|吨|件|小时|天|%|个月|季度)', md)
            if thresholds:
                row["thresholds"] = ", ".join(thresholds[:6])

            # ⑥ 문서 요약 (첫 200자)
            row["doc_summary"] = md[:200].replace("\n", " ").strip()
            row["extraction_method"] = "rule_based"

            result.append(row)

        ctx.meta["md_to_structured"] = {
            "method": "rule_based",
            "processed": len(data),
            "success": len(result),
        }
        return result
