"""데이터 정제 Step — NULL 처리, 중복 제거, 날짜 정규화, jagged row 필터링"""
from __future__ import annotations
import re
from app.services.v2.pipeline.base import PipelineStep, PipelineContext

# ISO 8601 으로 정규화할 날짜 패턴들
_DATE_PATTERNS = [
    (re.compile(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$'), '{}-{:02d}-{:02d}'),
    (re.compile(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$'), '{2}-{0:02d}-{1:02d}'),
    (re.compile(r'^(\d{4})(\d{2})(\d{2})$'), '{}-{}-{}'),
]


def _normalize_date(val: str) -> str:
    """날짜 문자열을 YYYY-MM-DD 형식으로 표준화"""
    val = val.strip()
    for pat, fmt in _DATE_PATTERNS:
        m = pat.match(val)
        if m:
            parts = [int(g) for g in m.groups()]
            try:
                if '{2}' in fmt:
                    return fmt.format(*parts)
                return fmt.format(*parts)
            except (ValueError, IndexError):
                pass
    return val  # 매칭 안되면 그대로


class CleansingStep(PipelineStep):
    """
    spec 옵션:
      null_strategy:   "drop" | "fill_empty" | "mark" (기본: "fill_empty")
                       mark = 원래 값을 빈 문자열로 채우고 __null_<col>__ = "1" 마커 열 추가
      deduplicate:     bool (기본: True)
      trim_strings:    bool (기본: True)
      normalize_dates: bool (기본: True) — timestamp 열 날짜 형식 표준화
      filter_jagged:   bool (기본: True) — 열 수 불일치 행 제거
    """

    def run(self, ctx: PipelineContext, data: list[dict]) -> list[dict]:
        if not data:
            return data

        spec = ctx.spec.get("cleansing", {})
        null_strategy   = spec.get("null_strategy",   "fill_empty")
        deduplicate     = spec.get("deduplicate",     True)
        trim_strings    = spec.get("trim_strings",    True)
        normalize_dates = spec.get("normalize_dates", True)
        filter_jagged   = spec.get("filter_jagged",   True)

        # 기준 열 집합 (첫 행 기준)
        expected_cols = set(data[0].keys())

        # timestamp 열 감지 (schema_inference 결과 참조)
        inferred_schema: dict[str, str] = ctx.meta.get("inferred_schema", {})
        timestamp_cols = {col for col, t in inferred_schema.items() if t == "timestamp"}

        result = []
        seen: set[str] = set()
        jagged_count = 0
        null_count = 0
        date_normalized = 0

        for row in data:
            # ① jagged row 필터링 (열 수 불일치)
            if filter_jagged and set(row.keys()) != expected_cols:
                jagged_count += 1
                continue

            # ② NULL 처리
            cleaned: dict = {}
            null_markers: dict = {}   # mark 전략용
            skip = False
            for k, v in row.items():
                is_null = v is None or (isinstance(v, str) and v.strip() == "")
                if is_null:
                    null_count += 1
                    if null_strategy == "drop":
                        skip = True
                        break
                    elif null_strategy == "mark":
                        cleaned[k] = ""
                        null_markers[f"__null_{k}__"] = "1"
                    else:  # fill_empty
                        cleaned[k] = ""
                elif trim_strings and isinstance(v, str):
                    cleaned[k] = v.strip()
                else:
                    cleaned[k] = v

            if skip:
                continue

            # mark 전략: 마커 열 추가
            cleaned.update(null_markers)

            # ③ 날짜 형식 표준화
            if normalize_dates and timestamp_cols:
                for col in timestamp_cols:
                    if col in cleaned and cleaned[col]:
                        normalized = _normalize_date(str(cleaned[col]))
                        if normalized != cleaned[col]:
                            cleaned[col] = normalized
                            date_normalized += 1

            # ④ 중복 제거
            if deduplicate:
                key = str(sorted(cleaned.items()))
                if key in seen:
                    continue
                seen.add(key)

            result.append(cleaned)

        ctx.meta.update({
            "rows_before": len(data),
            "rows_after": len(result),
            "dropped": len(data) - len(result),
            "jagged_removed": jagged_count,
            "null_cells_handled": null_count,
            "dates_normalized": date_normalized,
        })
        return result
