"""Pipeline 执行 Celery 任务 — 支持 DAG 编译 + 节点状态追踪"""
from __future__ import annotations
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def get_celery_app():
    try:
        from app.tasks.extraction import celery_app
        return celery_app
    except Exception:
        return None


celery_app = get_celery_app()


def _init_node_status(definition: dict | None) -> dict[str, str]:
    """从 definition 中提取所有节点 ID，初始化为 'idle'"""
    if not definition:
        return {}
    nodes = definition.get("nodes", [])
    return {n["id"]: "idle" for n in nodes}


def _compute_quality_score(rows: list[dict], route: str, meta: dict) -> float:
    if not rows:
        return 0.0
    if route == "C":
        meta_fields = {"markdown_text", "filename", "source_file", "source_dataset_id",
                       "extraction_strategy", "extraction_method", "structured_extraction_ok",
                       "structured_extraction_error"}
        meaningful_fields = [k for k in rows[0].keys() if k not in meta_fields]
        total_fields = len(meaningful_fields) or 1
        filled = sum(1 for row in rows for k in meaningful_fields if row.get(k))
        completeness = filled / (len(rows) * total_fields) if total_fields > 0 else 0
        rule_bonus = min(0.2, int(rows[0].get("rule_count", 0)) * 0.02)
        return min(1.0, completeness + rule_bonus)
    rows_before = meta.get("rows_before", len(rows)) or len(rows)
    rows_after = meta.get("rows_after", len(rows)) or len(rows)
    retention = rows_after / rows_before if rows_before > 0 else 1.0
    total_cells = sum(len(r) for r in rows) or 1
    filled_cells = sum(1 for r in rows for v in r.values() if v is not None and str(v).strip() != "")
    fill_rate = filled_cells / total_cells
    return round(retention * 0.4 + fill_rate * 0.6, 3)


def pipeline_run_task(pipeline_id: str, run_id: str):
    """Pipeline 执行任务 — 支持 DAG 编译 + 节点状态追踪"""
    from app.database import SessionLocal
    from app.models.v2.pipeline import Pipeline, PipelineRun
    from app.services.v2.pipeline.base import PipelineContext
    from app.services.v2.pipeline.engine import execute_route_a, execute_route_b, execute_route_c
    from app.services.v2.pipeline.dag_compiler import compile_definition
    from app.services.v2.dataset_service import DatasetService

    db = SessionLocal()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            return
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        pl = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pl:
            run.status = "failed"
            run.error_log = "Pipeline not found"
            db.commit()
            return

        # ── DAG 编译 ──────────────────────────────────────────────
        definition = pl.definition
        plan = compile_definition(definition)
        node_status = _init_node_status(definition)

        def set_node_status(nid: str, status: str):
            if nid in node_status:
                node_status[nid] = status
                # 每步更新持久化到 run 的临时字段
                run.stats = run.stats or {}
                run.stats["node_status"] = dict(node_status)
                db.commit()

        # ── 按 DAG 执行计划分阶段执行 ────────────────────────────
        svc = DatasetService(db)
        data = svc.preview(pl.source_dataset_id, 1, limit=10000)

        # Route C 特殊处理
        if not plan["phases"]:
            # 没有 DAG 计划，走旧逻辑
            from app.models.v2.dataset import Dataset as Ds2
            source_ds = db.query(Ds2).filter(Ds2.id == pl.source_dataset_id).first()
            if pl.route == "C" and source_ds and source_ds.kind == "unstructured":
                if not data or "storage_uri" not in (data[0] if data else {}):
                    if data:
                        lines = []
                        for row in data:
                            v = next(iter(row.values()), "") if row else ""
                            if v:
                                lines.append(str(v))
                        combined = "\n".join(lines)
                    else:
                        try:
                            from app.models.v2.dataset import DatasetVersion
                            ver = db.query(DatasetVersion).filter(
                                DatasetVersion.dataset_id == pl.source_dataset_id,
                                DatasetVersion.version_no == 1,
                            ).first()
                            if ver and ver.storage_uri:
                                storage = svc._storage
                                raw = storage.get_object(ver.storage_uri)
                                combined = raw.decode("utf-8", errors="replace")
                            else:
                                combined = ""
                        except Exception:
                            combined = ""
                    data = [{"markdown_text": combined, "filename": source_ds.name}]

        elif plan["linear"]:
            # 线性执行：按阶段顺序执行
            for phase in plan["phases"]:
                for nid in phase["node_ids"]:
                    set_node_status(nid, "running")
                    node_type = _get_node_type(definition, nid)

                    if node_type == "connector":
                        # Connector: 负责读取数据，目前数据已由 svc.preview 加载
                        set_node_status(nid, "success")

                    elif node_type == "storage":
                        # Storage: 数据已就绪
                        set_node_status(nid, "success")

                    elif node_type == "transform":
                        # Transform: 执行清洗/转换
                        try:
                            ctx = PipelineContext(
                                dataset_id=pl.source_dataset_id,
                                version_no=1,
                                route=pl.route or "A",
                                spec=pl.spec or {},
                            )
                            ctx.rows_in = len(data)

                            if pl.route == "A":
                                data, ctx = execute_route_a(ctx, data)
                            elif pl.route == "B":
                                data, ctx = execute_route_b(ctx, data)
                            elif pl.route == "C":
                                data, ctx = execute_route_c(ctx, data)

                            ctx.rows_out = len(data)
                            set_node_status(nid, "success")
                        except Exception as e:
                            set_node_status(nid, "failed")
                            logger.error(f"Transform 节点 {nid} 执行失败: {e}")
                            raise

                    elif node_type == "output":
                        # Output: 保存为 Curated Dataset
                        set_node_status(nid, "success")
        else:
            # 复杂 DAG：按拓扑顺序执行
            for nid in plan.get("execution_order", []):
                node_type = _get_node_type(definition, nid)
                set_node_status(nid, "running")
                try:
                    # 简化执行：目前只执行 transform 类型的节点
                    if node_type == "transform":
                        ctx = PipelineContext(
                            dataset_id=pl.source_dataset_id,
                            version_no=1,
                            route=pl.route or "A",
                            spec=pl.spec or {},
                        )
                        if pl.route == "A":
                            data, ctx = execute_route_a(ctx, data)
                        elif pl.route == "B":
                            data, ctx = execute_route_b(ctx, data)
                        elif pl.route == "C":
                            data, ctx = execute_route_c(ctx, data)
                    set_node_status(nid, "success")
                except Exception:
                    set_node_status(nid, "failed")
                    raise

        ctx = PipelineContext(
            dataset_id=pl.source_dataset_id,
            version_no=1,
            route=pl.route or "A",
            spec=pl.spec or {},
        )
        ctx.rows_in = len(data)
        ctx.rows_out = len(data)

        # ── 保存 Curated Dataset ──────────────────────────────
        curated_id = None
        try:
            import csv, io, json as _json

            def _safe_str(v) -> str:
                if v is None:
                    return ""
                if isinstance(v, (dict, list)):
                    return _json.dumps(v, ensure_ascii=False)
                return str(v)

            ds_name = f"{pl.name} curated"
            curated_ds = svc.create_dataset(name=ds_name, kind="curated")

            if data:
                all_keys: list[str] = []
                seen_keys: set[str] = set()
                for row in data:
                    for k in row.keys():
                        if k not in seen_keys:
                            all_keys.append(k)
                            seen_keys.add(k)

                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction='ignore', restval="")
                writer.writeheader()
                for row in data:
                    safe_row = {k: _safe_str(row.get(k)) for k in all_keys}
                    writer.writerow(safe_row)
                csv_bytes = buf.getvalue().encode("utf-8")
            else:
                csv_bytes = b""

            svc.create_version(curated_ds.id, csv_bytes, rowcount=len(data))
            curated_id = curated_ds.id

            if data:
                try:
                    quality_score = _compute_quality_score(data, pl.route or "A", ctx.meta)
                    curated_ds.schema_json = curated_ds.schema_json or {}
                    curated_ds.schema_json["quality_score"] = quality_score
                    curated_ds.schema_json["columns"] = list(data[0].keys()) if data else []
                    curated_ds.schema_json["route"] = pl.route
                    db.commit()
                except Exception:
                    pass

        except Exception as ce:
            logger.warning(f"Curated dataset save failed: {ce}")

        run.status = "success"
        run.finished_at = datetime.now(timezone.utc)
        run.stats = {
            "rows_in": ctx.rows_in,
            "rows_out": ctx.rows_out,
            "meta": ctx.meta,
            "node_status": node_status,
            "curated_dataset_id": curated_id,
        }
        db.commit()

    except Exception as e:
        logger.error(f"Pipeline run failed: {e}")
        if run:
            run.status = "failed"
            run.error_log = str(e)
            run.finished_at = datetime.now(timezone.utc)
            if run.stats is None:
                run.stats = {}
            if "node_status" not in run.stats:
                run.stats["node_status"] = {}
            db.commit()
    finally:
        db.close()


def _get_node_type(definition: dict | None, node_id: str) -> str:
    """从 definition 中获取节点类型"""
    if not definition:
        return ""
    for n in definition.get("nodes", []):
        if n.get("id") == node_id:
            return n.get("type", "")
    return ""


if celery_app:
    pipeline_run_task = celery_app.task(pipeline_run_task)
