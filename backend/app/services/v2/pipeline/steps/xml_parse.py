"""XML → 평면 테이블 변환 Step"""
from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import Any

from app.services.v2.pipeline.base import PipelineStep, PipelineContext


class XmlParseStep(PipelineStep):
    """
    XML 문자열 데이터를 평면 row 목록으로 변환합니다.

    spec 옵션:
      record_path: str — 반복 레코드 XPath (예: ".//record", ".//item")
      fields: list[str] — 추출할 서브 요소/속성 목록 (빈 리스트면 전체)
      include_attributes: bool (기본 True)
    """

    def run(self, ctx: PipelineContext, data: list[dict]) -> list[dict]:
        """data의 각 row에서 'xml_content' 키를 XML로 파싱."""
        spec = ctx.spec.get("xml_parse", {})
        record_path = spec.get("record_path", ".//record")
        fields = spec.get("fields", [])
        include_attrs = spec.get("include_attributes", True)

        result = []
        for row in data:
            xml_str = row.get("xml_content", "")
            if not xml_str:
                result.append(row)
                continue
            try:
                records = self._parse_xml(xml_str, record_path, fields, include_attrs)
                for rec in records:
                    merged = {k: v for k, v in row.items() if k != "xml_content"}
                    merged.update(rec)
                    result.append(merged)
            except ET.ParseError:
                result.append(row)  # 파싱 실패 시 원본 유지

        ctx.meta["xml_parse"] = {"rows_before": len(data), "rows_after": len(result)}
        return result

    def _parse_xml(self, xml_str: str, record_path: str, fields: list[str], include_attrs: bool) -> list[dict]:
        root = ET.fromstring(xml_str)
        records = root.findall(record_path)

        if not records:
            # record_path에 해당 없으면 root 자체를 단일 레코드로 처리
            records = [root]

        result = []
        for elem in records:
            row: dict[str, Any] = {}

            if include_attrs:
                row.update(elem.attrib)

            for child in elem:
                tag = child.tag
                if fields and tag not in fields:
                    continue
                row[tag] = child.text or ""

            result.append(row)

        return result
