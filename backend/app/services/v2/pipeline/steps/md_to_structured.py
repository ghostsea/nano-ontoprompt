"""Markdown → 结构化 JSON 提取 Step"""
from __future__ import annotations
import json
import re
import logging
from app.services.v2.pipeline.base import PipelineStep, PipelineContext

logger = logging.getLogger(__name__)


def _get_first_model(model_id: str | None = None):
    """返回 DB 中可用的 LLM 模型配置"""
    try:
        from app.services.model_config_selector import select_llm_model_config
        return select_llm_model_config(
            model_id=model_id,
            purpose_tags=("结构化抽取", "LLM结构化", "llm_structurize"),
            allow_vlm=False,
        )
    except Exception:
        return None


def _call_with_model(model_config, messages: list[dict]) -> str | None:
    """使用用户配置的模型调用 LLM"""
    if not model_config:
        return None
    try:
        from app.services.llm_service import _call_llm
        from app.services.model_config_selector import llm_call_kwargs
        call_kwargs = llm_call_kwargs(model_config)
        if not call_kwargs:
            return None
        return _call_llm(
            **call_kwargs,
            messages=messages,
        )
    except Exception as e:
        logger.info(f"LLM call failed: {e}")
        return None


class MarkdownToStructuredStep(PipelineStep):
    """
    从 Markdown 文本提取结构化字段。

    spec 选项:
      target_schema: dict  — 提取字段定义 {field_name: "description"}（缺省则自动推断）
      model_id: str        — 使用的 LLM 模型 ID
      prompt_template: str — 自定义提示词

    input:  row 含 "markdown_text" 字段
    output: 增加结构化字段 + extraction_method 字段
    """

    EXTRACT_PROMPT = """请从以下文档中提取下列字段。只返回 JSON。

字段列表:
{schema}

文档:
{text}

输出格式 (仅 JSON, 不要解释):
{{"field1": "value1", "field2": "value2"}}"""

    AUTO_SCHEMA_PROMPT = """请分析以下文档, 提取对该文档类型最有用的结构化记录。
每条记录应对应文档中的一行、一条规则、一个章节、一个条目或一个事件。
字段名用英文 snake_case, 值只包含文档中实际存在的内容。

文档:
{text}

输出格式 (仅 JSON, 不要解释):
{{"records": [{{"record_id": "stable_id", "row_type": "table_row|rule|section|item", "field1": "extracted_value1"}}]}}"""

    def run(self, ctx: PipelineContext, data: list[dict]) -> list[dict]:
        spec = ctx.spec.get("md_to_structured", {})
        target_schema = spec.get("target_schema", {})
        model_id = spec.get("model_id", "")

        model_config = _get_first_model(model_id)

        # 无 target_schema 时自动推断或规则提取
        if not target_schema:
            if not spec.get("auto_extract") and not spec.get("rule_based"):
                ctx.meta["md_to_structured"] = {
                    "method": "passthrough", "processed": len(data), "success": len(data)
                }
                return data
            sample_md = next((r.get("markdown_text", "") for r in data if r.get("markdown_text")), "")
            if sample_md and model_config and spec.get("auto_extract"):
                # 尝试 LLM 自动提取
                result = self._auto_extract_with_llm(data, model_config)
                if result:
                    ctx.meta["md_to_structured"] = {
                        "method": "llm_auto", "processed": len(data), "success": len(result)
                    }
                    return result
            # 规则回退
            return self._rule_based_extract(data, ctx)

        # 有 target_schema 时 LLM 按字段提取
        result, success = [], 0
        for row in data:
            md_text = row.get("markdown_text", "")
            if not md_text:
                result.append(row)
                continue
            try:
                extracted = self._extract(md_text, target_schema, model_config)
                row = dict(row)
                row.update(extracted)
                row["extraction_method"] = "llm_schema"
                row["structured_extraction_ok"] = True
                success += 1
            except Exception as e:
                logger.warning(f"MarkdownToStructured failed: {e}")
                row = dict(row)
                row["structured_extraction_ok"] = False
                row["structured_extraction_error"] = str(e)
            result.append(row)

        ctx.meta["md_to_structured"] = {
            "method": "llm_schema",
            "processed": len(data),
            "success": success,
            "schema_fields": list(target_schema.keys()),
        }
        return result

    # ── LLM 自动提取（无 target_schema 时）─────────────────────────────────

    def _auto_extract_with_llm(self, data: list[dict], model_config) -> list[dict] | None:
        """一次性请求 LLM 完成 schema 推断 + 提取"""
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
                return None  # LLM 失败 → 回退规则提取
            try:
                text = resp.strip()
                if "```" in text:
                    text = re.search(r'```(?:json)?\s*([\s\S]+?)```', text)
                    text = text.group(1).strip() if text else resp
                extracted = json.loads(text)
                if isinstance(extracted, dict) and isinstance(extracted.get("records"), list):
                    records = extracted["records"]
                else:
                    records = extracted if isinstance(extracted, list) else [extracted]
                for idx, item in enumerate(records):
                    if not isinstance(item, dict):
                        continue
                    out = dict(row)
                    out.update({str(k): str(v) for k, v in item.items()})
                    out.setdefault("record_id", f"{row.get('filename') or row.get('source_file') or 'doc'}:llm:{idx + 1}")
                    out["extraction_method"] = "llm_auto"
                    result.append(out)
                continue
            except Exception:
                row = dict(row)
                row["extraction_method"] = "llm_auto_parse_error"
            result.append(row)
        return result

    # ── LLM 字段提取（有 target_schema 时）─────────────────────────────────

    def _extract(self, md_text: str, schema: dict, model_config) -> dict:
        return self._extract_fields(md_text, schema, model_config)

    def _extract_fields(self, md_text: str, schema: dict, model_config) -> dict:
        """LLM 按 target_schema 提取字段"""
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

    # ── 规则回退 ────────────────────────────────────────────────────────────

    def _rule_based_extract(self, data: list[dict], ctx: PipelineContext) -> list[dict]:
        """无 LLM 时用正则提取结构化信息 (PRD: 规则/实体/数值检测)"""
        result = []
        for row in data:
            md = row.get("markdown_text", "")
            if not md:
                result.append(row)
                continue

            base = dict(row)
            base.pop("content", None)
            source_file = base.get("source_file") or base.get("filename") or "document"
            doc_summary = md[:200].replace("\n", " ").strip()
            section_titles = re.findall(r'^#{1,6}\s+(.+)$', md, re.MULTILINE)
            common = {
                "source_file": source_file,
                "section_count": len(section_titles),
                "sections": ", ".join(section_titles[:6]),
                "doc_summary": doc_summary,
                "extraction_method": "rule_based",
            }
            start_index = len(result)

            # ① IF-THEN 规则提取
            rules = re.findall(
                r'IF\s+(.+?)\s+THEN\s+(.+?)(?=\n|$)',
                md, re.IGNORECASE | re.MULTILINE
            )
            for idx, (condition, action) in enumerate(rules, start=1):
                out = dict(base)
                out.update(common)
                out.update({
                    "record_id": f"{source_file}:rule:{idx}",
                    "row_type": "rule",
                    "rule_index": idx,
                    "rule_count": len(rules),
                    "condition": condition.strip(),
                    "action": action.strip(),
                })
                result.append(out)

            # ② Markdown 表格拆成结构化行
            table_rows = self._extract_table_records(md, str(source_file))
            for item in table_rows:
                out = dict(base)
                out.update(common)
                out.update(item)
                result.append(out)

            # ③ Markdown/PPTX/DOCX 章节拆行。表格/规则之外仍保留章节语义。
            section_rows = self._extract_section_records(md, str(source_file), limit=max(10, 30 - len(table_rows) - len(rules)))
            for item in section_rows:
                out = dict(base)
                out.update(common)
                out.update(item)
                result.append(out)

            # ④ 中文企业/组织名提取
            org_names = re.findall(
                r'[一-龥]{2,10}(?:公司|集团|科技|物流|铝业|五金|包装|原材料)',
                md
            )
            thresholds = re.findall(r'(\d[\d,\.]+)\s*(?:万元?|吨|件|小时|天|%|个月|季度)', md)
            numeric_kvs = re.findall(r'\|\s*([^\|]+)\s*\|\s*(\d[\d,\.]*)\s*\|', md)
            enrich = {
                "organizations": ", ".join(list(dict.fromkeys(org_names))[:8]) if org_names else "",
                "thresholds": ", ".join(thresholds[:6]) if thresholds else "",
                "numeric_fields": json.dumps({k.strip(): v for k, v in numeric_kvs[:8]}, ensure_ascii=False) if numeric_kvs else "",
            }
            for out in result[start_index:]:
                out.update({k: v for k, v in enrich.items() if v})

            if not rules and not table_rows and not section_rows:
                out = dict(base)
                out.update(common)
                out.update({
                    "record_id": f"{source_file}:document:1",
                    "row_type": "document",
                    "rule_count": 0,
                })
                out.update({k: v for k, v in enrich.items() if v})
                result.append(out)

        ctx.meta["md_to_structured"] = {
            "method": "rule_based",
            "processed": len(data),
            "success": len(result),
            "emitted_records": len(result),
        }
        return result

    def _split_table_cells(self, line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    def _is_table_separator(self, cells: list[str]) -> bool:
        return bool(cells) and all(re.match(r"^:?-{3,}:?$", cell.strip()) for cell in cells)

    def _extract_table_records(self, md: str, source_file: str) -> list[dict]:
        records: list[dict] = []
        lines = md.splitlines()
        current_section = ""
        table_idx = 0
        i = 0
        while i < len(lines):
            heading = re.match(r"^(#{1,6})\s+(.+)$", lines[i])
            if heading:
                current_section = heading.group(2).strip()
                i += 1
                continue
            if lines[i].lstrip().startswith("|") and i + 1 < len(lines):
                header = self._split_table_cells(lines[i])
                separator = self._split_table_cells(lines[i + 1])
                if self._is_table_separator(separator):
                    table_idx += 1
                    i += 2
                    row_idx = 0
                    while i < len(lines) and lines[i].lstrip().startswith("|"):
                        cells = self._split_table_cells(lines[i])
                        if len(cells) == len(header):
                            row_idx += 1
                            out = {
                                "record_id": f"{source_file}:table:{table_idx}:row:{row_idx}",
                                "row_type": "table_row",
                                "table_index": table_idx,
                                "table_row_index": row_idx,
                                "section_title": current_section,
                            }
                            for col_idx, col in enumerate(header):
                                key = col or f"col_{col_idx + 1}"
                                out[key] = cells[col_idx]
                            records.append(out)
                        i += 1
                    continue
            i += 1
        return records

    def _extract_section_records(self, md: str, source_file: str, limit: int = 30) -> list[dict]:
        records: list[dict] = []
        matches = list(re.finditer(r"^(#{1,6})\s+(.+)$", md, flags=re.MULTILINE))
        if not matches:
            text = md.strip()
            return [{
                "record_id": f"{source_file}:section:1",
                "row_type": "section",
                "section_index": 1,
                "section_title": PathLikeTitle(source_file),
                "section_text": text[:2000],
            }] if text else []
        for idx, match in enumerate(matches[:limit], start=1):
            start = match.end()
            end = matches[idx].start() if idx < len(matches) else len(md)
            text = md[start:end].strip()
            if not text:
                continue
            records.append({
                "record_id": f"{source_file}:section:{idx}",
                "row_type": "section",
                "section_index": idx,
                "section_title": match.group(2).strip(),
                "section_text": text[:2000],
            })
        return records


def PathLikeTitle(value: str) -> str:
    return str(value).rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
