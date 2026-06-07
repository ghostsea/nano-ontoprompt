"""와이드 테이블 분할 Step — LLM 보조 분석 + 사용자 확인"""
from __future__ import annotations
import json
import logging
from app.services.v2.pipeline.base import PipelineStep, PipelineContext

logger = logging.getLogger(__name__)


class WideTableSplitStep(PipelineStep):
    """
    넓은 테이블(많은 컬럼)을 여러 개의 정규화된 테이블로 분리합니다.

    spec 옵션:
      split_config: dict — 사용자 확인된 분할 설정 {table_name: [col1, col2, ...]}
      suggest_only: bool (기본: False) — True면 제안만 반환, 실제 분할 안함
      wide_threshold: int (기본: 80) — 이 이상의 컬럼이면 wide로 간주 (PRD 기준)

    spec에 split_config가 없으면 LLM에게 제안을 요청하고
    ctx.meta["split_suggestion"]에 저장합니다.
    """

    def run(self, ctx: PipelineContext, data: list[dict]) -> list[dict]:
        if not data:
            return data

        spec = ctx.spec.get("wide_table_split", {})
        split_config = spec.get("split_config", {})
        suggest_only = spec.get("suggest_only", False)
        wide_threshold = spec.get("wide_threshold", 80)

        columns = list(data[0].keys()) if data else []
        col_count = len(columns)

        # 와이드 테이블이 아니면 스킵
        if col_count < wide_threshold and not split_config:
            ctx.meta["wide_table_split"] = {"skipped": True, "col_count": col_count}
            return data

        # split_config 없으면 LLM에게 제안 요청
        if not split_config:
            suggestion = self._suggest_split(columns, data[:3])
            ctx.meta["split_suggestion"] = suggestion
            ctx.meta["wide_table_split"] = {
                "suggested": True,
                "col_count": col_count,
                "suggestion": suggestion,
            }
            if suggest_only:
                return data  # 제안만 하고 실제 분할 안함

            # 자동 실행 (사용자 확인 없이) — 테스트/자동화용
            split_config = suggestion.get("split_config", {})
            if not split_config:
                return data

        # 실제 분할 실행
        from app.services.v2.duckdb_service import DuckDBService
        svc = DuckDBService()
        split_result = svc.split_wide_table(data, split_config)

        # 분할 결과를 ctx.meta에 저장하고 첫 번째 테이블을 주 데이터로 반환
        ctx.meta["wide_table_split"] = {
            "executed": True,
            "tables": {name: len(rows) for name, rows in split_result.items()},
        }
        ctx.meta["split_tables"] = split_result

        # 첫 번째 분할 테이블을 메인 output으로 반환
        first_table = next(iter(split_result.values()), data)
        return first_table

    def _suggest_split(self, columns: list[str], sample_rows: list[dict]) -> dict:
        """LLM에게 분할 제안 요청 (실패 시 기본 2분할 제안)"""
        try:
            prompt = f"""다음 테이블의 컬럼 목록을 분석하여 정규화된 분할 방안을 제안하세요.

컬럼 목록: {json.dumps(columns, ensure_ascii=False)}
샘플 데이터: {json.dumps(sample_rows[:2], ensure_ascii=False)[:500]}

각 컬럼을 논리적으로 연관된 그룹으로 분류하여 JSON으로 반환하세요:
{{"split_config": {{"table1": ["col1", "col2"], "table2": ["col3", "col4"]}}}}"""

            # 사용자 설정 모델 우선 사용
            from app.services.v2.pipeline.steps.md_to_structured import _get_first_model, _call_with_model
            model_cfg = _get_first_model()
            if model_cfg:
                messages = [
                    {"role": "system", "content": "You are a data modeling expert. Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ]
                raw = _call_with_model(model_cfg, messages)
                if raw:
                    import re
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    if match:
                        return json.loads(match.group())
        except Exception as e:
            logger.info(f"LLM split suggestion failed (using fallback): {e}")

        # 폴백: 절반씩 분할
        mid = len(columns) // 2
        return {
            "split_config": {
                "table_a": columns[:mid],
                "table_b": columns[mid:],
            }
        }
