"""Schema 자동 추론 Step — timestamp 감지 + 다중 샘플 투표"""
from __future__ import annotations
import re
from app.services.v2.pipeline.base import PipelineStep, PipelineContext

# 날짜/타임스탬프를 판별하는 정규식 패턴 (PRD: string/int/float/timestamp/bool)
_DATE_RE = re.compile(
    r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}'        # 2024-01-15 | 2024/1/15
    r'|^\d{1,2}[-/]\d{1,2}[-/]\d{4}'        # 15/01/2024
    r'|^\d{4}\d{2}\d{2}$'                   # 20240115
    r'|^\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}'  # ISO datetime
)


class SchemaInferenceStep(PipelineStep):
    """
    열 타입을 추론합니다 (PRD: string / integer / float / timestamp / boolean).
    다중 샘플(최대 10행)에 대해 투표하여 더 정확한 타입을 반환합니다.
    """

    def run(self, ctx: PipelineContext, data: list[dict]) -> list[dict]:
        if not data:
            return data

        # 최대 10행 샘플로 타입 투표
        sample_rows = data[:10]
        columns = list(data[0].keys())
        schema: dict[str, str] = {}

        for col in columns:
            votes: dict[str, int] = {}
            for row in sample_rows:
                val = row.get(col)
                if val is None or str(val).strip() == "":
                    continue
                t = self._infer_type(str(val).strip())
                votes[t] = votes.get(t, 0) + 1
            # 가장 많이 투표된 타입 선택; 동점이면 더 구체적인 타입 우선
            if votes:
                priority = ["timestamp", "integer", "float", "boolean", "string", "null"]
                schema[col] = max(votes, key=lambda t: (votes[t], -priority.index(t) if t in priority else -99))
            else:
                schema[col] = "string"

        ctx.meta["inferred_schema"] = schema
        return data

    @staticmethod
    def _infer_type(value: str) -> str:
        if not value or value.lower() in ("none", "null", "nan", ""):
            return "null"
        # timestamp 우선 확인
        if _DATE_RE.match(value):
            return "timestamp"
        if value.lower() in ("true", "false", "yes", "no", "1", "0"):
            return "boolean"
        try:
            int(value.replace(",", ""))
            return "integer"
        except (ValueError, TypeError):
            pass
        try:
            float(value.replace(",", ""))
            return "float"
        except (ValueError, TypeError):
            pass
        return "string"
