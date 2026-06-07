"""JSON 중첩 구조 → 평면 테이블 변환 Step"""
from __future__ import annotations
import json
from typing import Any

from app.services.v2.pipeline.base import PipelineStep, PipelineContext


class JsonFlattenStep(PipelineStep):
    """
    중첩 JSON 오브젝트를 평면 row로 변환합니다.

    spec 옵션:
      sep: str (기본 ".") — 중첩 키 구분자
      max_depth: int (기본 10) — 최대 중첩 깊이
      array_explode: bool (기본 True) — 배열 필드를 다수의 row로 분리
      array_fields: list[str] — explode할 배열 필드 명시 (빈 리스트면 자동 감지)
    """

    def run(self, ctx: PipelineContext, data: list[dict]) -> list[dict]:
        spec = ctx.spec.get("json_flatten", {})
        sep = spec.get("sep", ".")
        max_depth = spec.get("max_depth", 10)
        array_explode = spec.get("array_explode", True)
        array_fields = spec.get("array_fields", [])

        result = []
        for row in data:
            flat = self._flatten(row, sep=sep, max_depth=max_depth, prefix="", depth=0)
            if array_explode:
                exploded = self._explode_arrays(flat, array_fields)
                result.extend(exploded)
            else:
                result.append(flat)

        ctx.meta["json_flatten"] = {
            "rows_before": len(data),
            "rows_after": len(result),
        }
        return result

    def _flatten(self, obj: Any, sep: str, max_depth: int, prefix: str, depth: int) -> dict:
        """재귀적으로 중첩 딕셔너리를 평면화. 배열은 JSON 문자열로 임시 보존."""
        if depth > max_depth:
            return {prefix: str(obj)} if prefix else {}

        result = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{prefix}{sep}{k}" if prefix else k
                if isinstance(v, dict):
                    result.update(self._flatten(v, sep, max_depth, new_key, depth + 1))
                elif isinstance(v, list):
                    # 배열은 나중에 explode 처리를 위해 특수 마커로 보존
                    result[f"__array__{new_key}"] = v
                else:
                    result[new_key] = v
        else:
            result[prefix] = obj

        return result

    def _explode_arrays(self, flat_row: dict, explicit_fields: list[str]) -> list[dict]:
        """배열 필드를 기준으로 row를 분리 (cross join 방식)."""
        # 배열 필드 수집
        array_keys = [k for k in flat_row if k.startswith("__array__")]

        # 비배열 필드 기본 row
        base = {k: v for k, v in flat_row.items() if not k.startswith("__array__")}

        if not array_keys:
            return [base]

        # 첫 번째 배열 필드만 explode (다중 배열은 단순화)
        array_key = array_keys[0]
        real_key = array_key[len("__array__"):]
        array_val = flat_row[array_key]

        remaining_arrays = {k: v for k, v in flat_row.items() if k.startswith("__array__") and k != array_key}

        rows = []
        if not isinstance(array_val, list) or len(array_val) == 0:
            row = dict(base)
            row[real_key] = json.dumps(array_val)
            row.update({k[len("__array__"):]: json.dumps(v) for k, v in remaining_arrays.items()})
            return [row]

        for item in array_val:
            row = dict(base)
            if isinstance(item, dict):
                for ik, iv in item.items():
                    row[f"{real_key}.{ik}"] = iv
            else:
                row[real_key] = item
            row.update({k[len("__array__"):]: json.dumps(v) for k, v in remaining_arrays.items()})
            rows.append(row)

        return rows
