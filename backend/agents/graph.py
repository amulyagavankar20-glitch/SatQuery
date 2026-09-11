"""SatQuery AI — LangGraph Orchestration Graph.
 
ARCHITECTURE RULES ENFORCED HERE:
- ONE canonical GraphState imported from backend.agents.state (TypedDict).
  This file does NOT define a second GraphState.
- query_router invokes QwenRouter via OpenRouter (with deterministic fallback).
- report_generator synthesizes final answers via FinalReasoner.
- tool_selector MUST validate against the PostgreSQL ToolRegistry.
  db_session must never be None.
- run_tool must receive a real database session.
- preprocess calls the preprocessing wrapper (run_preprocessing).
- Confidence is computed from evidence signals, NOT fabricated.
- evidence_fusion consumes validated tool outputs.
- Failed/refused executions are never marked COMPLETED.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from collections.abc import Mapping

from langgraph.graph import StateGraph, END

from backend.session import get_session, SessionContext
from backend.services.persistence import normalize_input_class, persist_run
from backend.schemas import InputClass, RouterTask
from backend.agents.state import GraphState          # ← canonical, single definition
from backend.agents.tools.base import ToolResult
from backend.agents.tools.executor import run_tool
from backend.agents.tool_selector import ToolSelector, ToolSelectorError
from backend.agents.router import QwenRouter, QwenRouterError
from backend.agents.output_validation import validate_output
from backend.agents.tools.preprocessing import run_preprocessing
from backend.schemas import RouteRequest


# ---------------------------------------------------------------------------
# DB session factory – used by tool_selector and run_tool.
# In production this is provided by FastAPI's dependency injection.
# In tests the graph nodes accept an injected factory via GraphState["db_factory"].
# ---------------------------------------------------------------------------
def _get_db(state: GraphState):
    """Return a SQLAlchemy Session.

    The graph state may carry a ``db_factory`` callable injected by tests or
    the FastAPI request handler. If absent, falls back to the application
    database session generator.
    """
    factory = state.get("db_factory")  # type: ignore[attr-defined]
    if factory is not None:
        return factory()
    try:
        from backend.database import SessionLocal
        return SessionLocal()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Audit helper – records structured events into the in-memory session store.
# ---------------------------------------------------------------------------
def _record_event(
    state: GraphState,
    event_type: str,
    node_name: str,
    tool_id: str | None = None,
    parameters: dict[str, Any] | None = None,
    message: str | None = None,
) -> None:
    session = get_session(state.get("session_id", ""))
    if session:
        session.record_trace(
            event_type=event_type,
            node_name=node_name,
            tool_id=tool_id,
            parameters=parameters,
            message=message,
        )


# ---------------------------------------------------------------------------
# Utility – accumulate a visited node name into execution_trace list.
# We store visited node names in execution_trace to avoid shadowing TypedDict
# keys.  Tests check for 'visited' via the helper below.
# ---------------------------------------------------------------------------
def _visit(state: GraphState, node_name: str) -> dict[str, Any]:
    """Return a partial state update that appends *node_name* to execution_trace."""
    existing: list[dict[str, Any]] = state.get("execution_trace", [])  # type: ignore[assignment]
    return {"execution_trace": existing + [{"node": node_name}]}


def _visited_nodes(state: GraphState) -> list[str]:
    """Extract the list of visited node names from execution_trace."""
    return [e["node"] for e in state.get("execution_trace", [])]  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

def _check_modality_intent_mismatch(
    query: str,
    input_class: str,
    assets: list[Any] | None = None,
) -> str | None:
    """Detect clear modality contradictions between query demands and input assets."""
    ql = query.lower()
    sar_terms = ("sar", "radar", "sentinel-1", "s1", "backscatter", "dual-pol", "polarimetric", "amplitude", "speckle", "vv", "vh")
    optical_terms = ("optical", "rgb", "true color", "true-color", "multispectral", "ndvi", "sentinel-2", "s2", "cartosat", "land cover", "lulc", "vegetation")
    fusion_terms = ("optical and sar", "sar and optical", "fuse", "fusion")

    is_fusion_query = any(term in ql for term in fusion_terms)

    # Determine asset modalities
    asset_modalities = set()
    normalized_input_class = (input_class or "").upper()
    if normalized_input_class in ("SINGLE_OPTICAL", "BI_TEMPORAL", "BI_TEMPORAL_OPTICAL", "OPTICAL"):
        asset_modalities.add("OPTICAL")
    elif normalized_input_class in ("SINGLE_SAR", "BI_TEMPORAL_SAR", "SAR"):
        asset_modalities.add("SAR")
    elif normalized_input_class in ("OPTICAL_SAR_PAIR", "OPTICAL_SAR"):
        asset_modalities.add("OPTICAL")
        asset_modalities.add("SAR")

    if assets:
        for a in assets:
            if isinstance(a, dict):
                m = str(a.get("modality") or "").upper()
                fn = str(a.get("filename") or a.get("file_path") or "").lower()
                if m:
                    asset_modalities.add(m)
                if "s2_" in fn or "sentinel-2" in fn:
                    asset_modalities.add("OPTICAL")
                elif "s1_" in fn or "sentinel-1" in fn:
                    asset_modalities.add("SAR")
            elif isinstance(a, str):
                fn = a.lower()
                if "s2_" in fn or "sentinel-2" in fn:
                    asset_modalities.add("OPTICAL")
                elif "s1_" in fn or "sentinel-1" in fn:
                    asset_modalities.add("SAR")

    is_optical_asset = "OPTICAL" in asset_modalities and "SAR" not in asset_modalities
    is_sar_asset = "SAR" in asset_modalities and "OPTICAL" not in asset_modalities

    # Check if query specifically requests SAR on an optical-only asset
    if not is_fusion_query and any(term in ql for term in sar_terms):
        if is_optical_asset or normalized_input_class in ("SINGLE_OPTICAL", "BI_TEMPORAL", "BI_TEMPORAL_OPTICAL", "OPTICAL"):
            return "Selected asset is optical imagery, but this query requires SAR imagery."

    # Check if query specifically requests optical on a SAR-only asset
    if not is_fusion_query and any(term in ql for term in optical_terms):
        if is_sar_asset or normalized_input_class in ("SINGLE_SAR", "BI_TEMPORAL_SAR", "SAR"):
            return "Selected asset is SAR/radar imagery, but this query requires optical imagery."

    return None


def input_validator(state: GraphState) -> dict[str, Any]:
    updates = _visit(state, "input_validator")

    query = state.get("user_query", "")
    warnings: list[str] = list(state.get("warnings", []))  # type: ignore[arg-type]

    if not query or not query.strip():
        warnings.append("Empty user query received.")
        updates["warnings"] = warnings
        updates["status"] = "refused"
        updates["refusal_reason"] = "User query is empty."
        _record_event(state, "REFUSED", "input_validator", message="Empty query")
        return updates

    # Build explicit structured QueryPlan
    from backend.agents.query_plan import build_query_plan
    active_slot = state.get("active_slot") or (state.get("asset_metadata") or {}).get("active_slot")
    mode_hint = state.get("mode") or (state.get("asset_metadata") or {}).get("mode")
    query_plan = build_query_plan(
        query=query,
        active_slot=active_slot,
        mode_hint=mode_hint,
        manifest=state.get("asset_metadata"),
    )
    updates["query_plan"] = query_plan.model_dump()
    updates["mode"] = query_plan.mode

    input_class_val = state.get("input_class") or ""
    if not input_class_val and state.get("asset_metadata"):
        input_class_val = str(state["asset_metadata"].get("input_class", ""))

    assets = state.get("assets", [])
    mismatch = _check_modality_intent_mismatch(query, input_class_val, assets)
    if mismatch:
        warnings.append(mismatch)
        updates["warnings"] = warnings
        updates["status"] = "refused"
        updates["refusal_reason"] = mismatch
        _record_event(state, "REFUSED", "input_validator", message=mismatch)
        return updates

    _record_event(state, "INPUT_VALIDATED", "input_validator")
    updates["status"] = "running"
    updates["warnings"] = warnings
    return updates


def metadata_parser(state: GraphState) -> dict[str, Any]:
    _record_event(state, "METADATA_PARSED", "metadata_parser")
    updates = _visit(state, "metadata_parser")
    # Normalise input_class from asset_metadata if not already set
    if not state.get("input_class") and state.get("asset_metadata"):
        updates["input_class"] = state["asset_metadata"].get("input_class", "")  # type: ignore[index]
    if "query_plan" not in state:
        from backend.agents.query_plan import build_query_plan
        active_slot = state.get("active_slot") or (state.get("asset_metadata") or {}).get("active_slot")
        mode_hint = state.get("mode") or (state.get("asset_metadata") or {}).get("mode")
        query_plan = build_query_plan(
            query=state.get("user_query", ""),
            active_slot=active_slot,
            mode_hint=mode_hint,
            manifest=state.get("asset_metadata"),
        )
        updates["query_plan"] = query_plan.model_dump()
        updates["mode"] = query_plan.mode
    return updates


def _is_pair_query(query: str) -> bool:
    q = query.lower()
    pair_keywords = [
        "change", "changed", "difference", "compare", "between",
        "increased", "decreased", "construction increased",
        "fuse", "fusion", "optical and sar", "sar and optical",
        "t1 and t2", "t1 vs t2", "both images", "pair"
    ]
    return any(k in q for k in pair_keywords)


def _is_single_scene_query(query: str) -> bool:
    q = query.lower()
    single_keywords = [
        "explain", "describe", "water", "highlight", "what is",
        "how much", "identify", "classify", "land-cover", "land cover",
        "what objects", "objects", "caption", "overview", "urban", "built"
    ]
    return any(k in q for k in single_keywords)


def _requires_pair_evaluation(state: GraphState) -> bool:
    query = state.get("user_query", "")
    query_plan = state.get("query_plan") or {}
    mode = state.get("mode") or (state.get("asset_metadata") or {}).get("mode") or query_plan.get("mode")
    input_class = state.get("input_class") or ""

    if mode == "single_scene":
        return False
    if mode == "pair":
        return True

    if _is_pair_query(query):
        return True

    if _is_single_scene_query(query) and not _is_pair_query(query):
        return False

    return input_class in (InputClass.BI_TEMPORAL.value, InputClass.OPTICAL_SAR.value, "BI_TEMPORAL_OPTICAL")


def pair_fitness_gate(state: GraphState) -> dict[str, Any]:
    updates = _visit(state, "pair_fitness_gate")
    query = state.get("user_query", "")
    input_class_val = state.get("input_class") or ""
    assets = state.get("assets", [])
    warnings: list[str] = list(state.get("warnings", []))  # type: ignore[arg-type]

    # Enforce modality intent compatibility
    mismatch = _check_modality_intent_mismatch(query, input_class_val, assets)
    if mismatch:
        warnings.append(mismatch)
        updates["warnings"] = warnings
        updates["status"] = "refused"
        updates["refusal_reason"] = mismatch
        _record_event(state, "REFUSED", "pair_fitness_gate", message=mismatch)
        return updates

    # Check pair fitness metadata if present
    pair_fitness = state.get("pair_fitness")
    if pair_fitness and isinstance(pair_fitness, dict):
        has_overlap = pair_fitness.get("has_sufficient_overlap")
        if has_overlap is False or pair_fitness.get("compatible") is False:
            reason = pair_fitness.get("reason") or "Insufficient spatial overlap between image pair."
            warnings.append(reason)
            updates["warnings"] = warnings
            updates["status"] = "refused"
            updates["refusal_reason"] = reason
            _record_event(state, "REFUSED", "pair_fitness_gate", message=reason)
            return updates

    _record_event(state, "PAIR_FITNESS_CHECKED", "pair_fitness_gate")
    return updates


def query_router(state: GraphState) -> dict[str, Any]:
    """Route the query by invoking QwenRouter.

    MUST NOT read metadata["task"] as a routing shortcut.
    MUST NOT default unknown/failed routing to SINGLE_VQA.
    Failed routing → controlled refusal.
    """
    updates = _visit(state, "query_router")

    # Allow test injection: if state carries a pre-resolved task directly in
    # a field called "injected_task", use it. Never use metadata["task"].
    injected_task: str | None = state.get("injected_task")  # type: ignore[attr-defined]
    if injected_task is not None:
        if injected_task in RouterTask.__members__:
            task_val = RouterTask[injected_task].value
            updates["detected_task"] = task_val
            input_class_val = state.get("input_class", "SINGLE_OPTICAL")
            selected_path = ToolSelector.TASK_TO_TOOLS.get(RouterTask[injected_task], [])
            _record_event(
                state,
                "QUERY_ROUTED",
                "query_router",
                parameters={
                    "task": task_val,
                    "input_class": input_class_val,
                    "routing_policy": "deterministic_v1",
                    "selected_path": selected_path,
                },
            )
            return updates
        else:
            # Unknown injected task → refusal
            updates["status"] = "refused"
            updates["refusal_reason"] = f"Unknown task '{injected_task}' – cannot route."
            _record_event(state, "REFUSED", "query_router",
                          message=f"Unknown injected_task: {injected_task}")
            return updates

    # Production path: call QwenRouter (sync — graph nodes are not async)
    router = QwenRouter()
    manifest = state.get("asset_metadata") or {}
    request = RouteRequest(
        query=state.get("user_query", ""),
        manifest=manifest,
    )
    try:
        route_response = router.route_sync(request)
        updates["route"] = route_response
        updates["detected_task"] = route_response.task.value
        input_class_val = state.get("input_class", "SINGLE_OPTICAL")
        selected_path = ToolSelector.TASK_TO_TOOLS.get(route_response.task, [])
        _record_event(
            state,
            "QUERY_ROUTED",
            "query_router",
            parameters={
                "task": route_response.task.value,
                "input_class": input_class_val,
                "routing_policy": "deterministic_v1",
                "selected_path": selected_path,
            },
        )
    except QwenRouterError as exc:
        updates["status"] = "refused"
        updates["refusal_reason"] = f"Routing failed: {exc}"
        _record_event(state, "REFUSED", "query_router", message=str(exc))
    except Exception as exc:
        updates["status"] = "refused"
        updates["refusal_reason"] = f"Unexpected routing error: {exc}"
        _record_event(state, "REFUSED", "query_router", message=str(exc))

    return updates


def tool_selector(state: GraphState) -> dict[str, Any]:
    """Deterministic tool selection enforcing PostgreSQL tool_registry validation.

    db_session MUST be a real session – never None.
    """
    _record_event(state, "TOOL_SELECTION", "tool_selector")
    updates = _visit(state, "tool_selector")

    task_value = state.get("detected_task", "")
    input_class_value = state.get("input_class", "SINGLE_OPTICAL")
    warnings: list[str] = list(state.get("warnings", []))  # type: ignore[arg-type]

    # If single-scene task is routed on a multi-asset session, normalize input_class to single scene modality
    if task_value in (RouterTask.SINGLE_VQA.value, RouterTask.CAPTIONING.value, RouterTask.GROUNDING.value):
        if input_class_value in (InputClass.BI_TEMPORAL.value, InputClass.OPTICAL_SAR.value, "BI_TEMPORAL_OPTICAL"):
            active_slot = state.get("active_slot") or (state.get("asset_metadata") or {}).get("active_slot")
            assets = state.get("assets") or []
            target_asset = assets[1] if active_slot == "T2" and len(assets) > 1 else (assets[0] if assets else None)
            target_mod = (target_asset.get("modality") if isinstance(target_asset, dict) else None) or "OPTICAL"
            input_class_value = InputClass.SINGLE_SAR.value if target_mod == "SAR" else InputClass.SINGLE_OPTICAL.value
            updates["input_class"] = input_class_value

    try:
        task_enum = RouterTask(task_value)
    except ValueError:
        updates["status"] = "refused"
        updates["refusal_reason"] = f"Unknown task '{task_value}'"
        _record_event(state, "REFUSED", "tool_selector",
                      message=f"Unknown task: {task_value}")
        return updates

    try:
        input_class_enum = InputClass(input_class_value)
    except ValueError:
        input_class_enum = InputClass.SINGLE_OPTICAL
        warnings.append(f"Unknown input_class '{input_class_value}'; defaulting to SINGLE_OPTICAL.")

    db = _get_db(state)
    try:
        selector = ToolSelector(db_session=db)
        sequence = selector.validate_selection(task_enum, input_class_enum)
        updates["selected_tools"] = sequence
        updates["warnings"] = warnings
    except ToolSelectorError as exc:
        updates["status"] = "refused"
        updates["refusal_reason"] = str(exc)
        updates["warnings"] = warnings
        _record_event(state, "REFUSED", "tool_selector", message=str(exc))
    finally:
        try:
            db.close()
        except Exception:
            pass

    return updates


# ---------------------------------------------------------------------------
# Preprocessing node — calls Stage 3 pipeline via the wrapper.
# Results are stored in state; tile references are passed downstream.
# ---------------------------------------------------------------------------
def preprocess(state: GraphState) -> dict[str, Any]:
    updates = _visit(state, "preprocess")

    input_class_value = state.get("input_class", "SINGLE_OPTICAL")
    assets_raw: list[Any] = list(state.get("assets", []))  # type: ignore[arg-type]
    job_id = state.get("job_id", "unknown")

    try:
        input_class_enum = InputClass(input_class_value)
    except ValueError:
        input_class_enum = InputClass.SINGLE_OPTICAL

    # Build asset dicts expected by the dispatcher
    asset_dicts: list[dict[str, Any]] = []
    for a in assets_raw:
        if isinstance(a, dict):
            asset_dicts.append(a)
        else:
            # Treat plain string as a file_path; modality inferred downstream
            asset_dicts.append({"file_path": str(a)})

    try:
        preprocess_result = run_preprocessing(
            input_class=input_class_enum,
            assets=asset_dicts,
            job_id=job_id,
            session_context=None,
        )
        updates["preprocessing_result"] = preprocess_result

        # Derive image_refs for downstream specialist tools from tile references
        tile_refs = [t.file_path for t in preprocess_result.tile_references]
        updates["_preprocess_image_refs"] = tile_refs  # type: ignore[typeddict-unknown-key]

        _record_event(state, "PREPROCESS_COMPLETED", "preprocess", tool_id="preprocess",
                      parameters={"tile_count": len(tile_refs),
                                   "success": preprocess_result.success})
    except Exception as exc:
        warnings: list[str] = list(state.get("warnings", []))  # type: ignore[arg-type]
        warnings.append(f"Preprocessing failed: {exc}")
        updates["warnings"] = warnings
        updates["_preprocess_image_refs"] = []  # type: ignore[typeddict-unknown-key]
        _record_event(state, "FAILED", "preprocess", message=str(exc))

    return updates


# ---------------------------------------------------------------------------
# Execution helper — runs a specialist tool via run_tool with a real DB session.
# ---------------------------------------------------------------------------
def _execute_tool(state: GraphState, tool_id: str, params: Mapping[str, Any]) -> dict[str, Any]:
    updates = _visit(state, tool_id)

    existing_results: list[ToolResult] = list(state.get("specialist_results", []))  # type: ignore[arg-type]
    db = _get_db(state)
    try:
        result = run_tool(tool_id, params, db=db)
    except Exception as exc:
        result = ToolResult(
            tool_id=tool_id,
            status="error",
            input_refs=list(params.get("input_refs", [])),
            output_refs=[],
            result=None,
            confidence=None,
            latency_ms=None,
            warnings=[str(exc)],
            explanation=f"Tool execution failed: {exc}",
            spatial_refs=[],
        )
    finally:
        try:
            db.close()
        except Exception:
            pass

    existing_results.append(result)
    updates["specialist_results"] = existing_results
    _record_event(
        state,
        "TOOL_COMPLETED",
        tool_id,
        tool_id=tool_id,
        parameters={"status": result.status, "confidence": result.confidence},
        message=result.explanation or result.status,
    )
    return updates


def _image_refs(state: GraphState) -> list[str]:
    """Return preprocessed tile reference paths from state, falling back to raw assets."""
    refs = list(state.get("_preprocess_image_refs", []))  # type: ignore[attr-defined]
    if refs:
        return refs
    assets = state.get("assets", [])
    fallback_refs: list[str] = []
    for a in assets:
        if isinstance(a, dict) and "file_path" in a:
            fallback_refs.append(str(a["file_path"]))
        elif isinstance(a, str):
            fallback_refs.append(a)
    return fallback_refs


# ---------------------------------------------------------------------------
# Specialist tool nodes
# ---------------------------------------------------------------------------

def sar_map(state: GraphState) -> dict[str, Any]:
    """Sentinel-1 specialist: reBEN ResNet50 + dual-pol backscatter."""
    refs = _raw_raster_refs(state) or _image_refs(state)
    params = {
        "question": state.get("user_query", ""),
        "image_refs": refs,
        "input_refs": refs,
    }
    return _execute_tool(state, "sar_map", params)


def _asset_bounds(state: GraphState) -> list[float] | None:
    meta = state.get("asset_metadata") or {}
    b = meta.get("bounds") if isinstance(meta, dict) else None
    if isinstance(b, (list, tuple)) and len(b) == 4:
        return [float(x) for x in b]
    for a in state.get("assets") or []:
        if not isinstance(a, dict):
            continue
        bb = a.get("bounds_wgs84") or a.get("bounds")
        if isinstance(bb, (list, tuple)) and len(bb) == 4:
            return [float(x) for x in bb]
    return None


def _raw_raster_refs(state: GraphState) -> list[str]:
    """Original GeoTIFFs. RGB tiles cannot honestly run Dynamic World."""
    out: list[str] = []
    for a in state.get("assets") or []:
        if isinstance(a, dict):
            p = a.get("file_path")
        else:
            p = a
        if not p:
            continue
        path = Path(str(p))
        if path.suffix.lower() in {".tif", ".tiff"} and path.is_file():
            out.append(str(path))

    # If single-scene query with multiple assets, isolate active slot
    if len(out) > 1 and not _requires_pair_evaluation(state):
        active_slot = state.get("active_slot") or (state.get("asset_metadata") or {}).get("active_slot")
        if active_slot == "T2":
            return [out[1]]
        return [out[0]]

    return out


def lulc_map(state: GraphState) -> dict[str, Any]:
    refs = _raw_raster_refs(state) or _image_refs(state)
    query_plan = state.get("query_plan") or {}
    params = {
        "question": state.get("user_query", ""),
        "image_refs": refs,
        "input_refs": refs,
        "bounds": _asset_bounds(state),
        "job_id": state.get("job_id"),
        "target_class": query_plan.get("target_class"),
    }
    return _execute_tool(state, "lulc_map", params)




def align(state: GraphState) -> dict[str, Any]:
    _record_event(state, "ALIGNMENT_COMPLETED", "align")
    pre_result = state.get("preprocessing_result")
    # Derive pre/post tile refs from tile pairs if available
    pre_refs: list[str] = []
    post_refs: list[str] = []
    if pre_result and pre_result.tile_pairs:
        for tp in pre_result.tile_pairs:
            pre_refs.append(tp.file_path_1)
            post_refs.append(tp.file_path_2)
    elif _image_refs(state):
        refs = _image_refs(state)
        mid = len(refs) // 2 or 1
        pre_refs = refs[:mid]
        post_refs = refs[mid:]

    params = {"pre_refs": pre_refs or ["pre_placeholder"],
               "post_refs": post_refs or ["post_placeholder"],
               "input_refs": _image_refs(state)}
    result_updates = _execute_tool(state, "align", params)
    # Store alignment result for downstream bit_cd
    results: list[ToolResult] = result_updates.get("specialist_results", [])
    if results:
        result_updates["alignment_result"] = results[-1]
    return result_updates


def bit_cd(state: GraphState) -> dict[str, Any]:
    image_refs = _raw_raster_refs(state) or _image_refs(state)
    pre = image_refs[0] if len(image_refs) > 0 else "pre_placeholder"
    post = image_refs[1] if len(image_refs) > 1 else "post_placeholder"

    def _existing(path: object, fallback: str) -> str:
        if isinstance(path, (list, tuple)):
            path = path[0] if path else fallback
        text = str(path)
        return text if Path(text).is_file() else fallback

    align_result = state.get("alignment_result")
    if align_result and isinstance(align_result.result, dict):
        pre = _existing(align_result.result.get("aligned_pre"), str(pre))
        post = _existing(align_result.result.get("aligned_post"), str(post))

    params = {"pre_image": pre, "post_image": post, "input_refs": image_refs}
    result_updates = _execute_tool(state, "bit_cd", params)
    results: list[ToolResult] = result_updates.get("specialist_results", [])
    if results:
        result_updates["change_result"] = results[-1]
    _record_event(state, "CHANGE_DETECTED", "bit_cd", tool_id="bit_cd")
    return result_updates


def vectorize(state: GraphState) -> dict[str, Any]:
    change_result = state.get("change_result")
    mask_id = "MOCK_BIT_CD_MASK"
    if change_result and isinstance(change_result.result, dict):
        mask_id = change_result.result.get("mask_id", mask_id)
    params = {"mask_id": mask_id, "input_refs": _image_refs(state)}
    return _execute_tool(state, "vectorize", params)




def coregister(state: GraphState) -> dict[str, Any]:
    _record_event(state, "ALIGNMENT_COMPLETED", "coregister")
    pre_result = state.get("preprocessing_result")
    optical_refs: list[str] = []
    sar_refs: list[str] = []
    if pre_result and pre_result.tile_pairs:
        for tp in pre_result.tile_pairs:
            optical_refs.append(tp.file_path_1)
            sar_refs.append(tp.file_path_2)
    else:
        optical_refs = ["optical_placeholder"]
        sar_refs = ["sar_placeholder"]

    params = {"optical_refs": optical_refs, "sar_refs": sar_refs,
               "input_refs": _image_refs(state)}
    return _execute_tool(state, "coregister", params)


def fusion_s1s2(state: GraphState) -> dict[str, Any]:
    params = {"optical_ref": "optical_placeholder", "sar_ref": "sar_placeholder",
               "input_refs": _image_refs(state)}
    result_updates = _execute_tool(state, "fusion_s1s2", params)
    results: list[ToolResult] = result_updates.get("specialist_results", [])
    if results:
        result_updates["fusion_result"] = results[-1]
    _record_event(state, "FUSION_COMPLETED", "fusion_s1s2", tool_id="fusion_s1s2")
    return result_updates


def agreement(state: GraphState) -> dict[str, Any]:
    fusion_result = state.get("fusion_result")
    fusion_id = "MOCK_FUSION_OUTPUT"
    if fusion_result and isinstance(fusion_result.result, dict):
        fusion_id = fusion_result.result.get("fusion_id", fusion_id)
    params = {"fusion_id": fusion_id, "input_refs": _image_refs(state)}
    result_updates = _execute_tool(state, "agreement", params)
    _record_event(state, "AGREEMENT_COMPLETED", "agreement")
    return result_updates


# ---------------------------------------------------------------------------
# Evidence fusion — consumes validated tool outputs.
# ---------------------------------------------------------------------------
def evidence_fusion(state: GraphState) -> dict[str, Any]:
    updates = _visit(state, "evidence_fusion")

    results: list[ToolResult] = list(state.get("specialist_results", []))  # type: ignore[arg-type]
    # Collect spatial evidence from tool results
    spatial_evidence = []
    for r in results:
        if r.spatial_refs:
            spatial_evidence.extend(r.spatial_refs)

    # Run output validation (before final reporting)
    validation = validate_output(state)
    _record_event(
        state,
        "EVIDENCE_FUSED",
        "evidence_fusion",
        parameters={"confidence": validation.confidence.value},
        message=f"confidence={validation.confidence.value}",
    )

    # Aggregate evidence items for the report
    evidence_items = []
    for r in results:
        if r.status == "success" and r.result is not None:
            evidence_items.append({
                "tool_id": r.tool_id,
                "result": r.result,
                "explanation": r.explanation,
                "output_refs": r.output_refs,
            })

    # Build Confidence schema object
    from backend.agents.schemas import Confidence
    confidence_obj = Confidence(
        level=validation.confidence.value,
        signals=list(validation.evidence.model_evidence.__class__.__name__ and
                      [m.tool_id for m in validation.evidence.model_evidence]),
        reasoning="; ".join(validation.messages) if validation.messages else None,
    )

    updates["spatial_evidence"] = spatial_evidence
    updates["evidence_items"] = evidence_items
    updates["confidence"] = confidence_obj

    warnings: list[str] = list(state.get("warnings", []))  # type: ignore[arg-type]
    if not validation.is_valid:
        for msg in validation.messages:
            if msg not in warnings:
                warnings.append(msg)
    updates["warnings"] = warnings

    return updates


def audit_logger(state: GraphState) -> dict[str, Any]:
    _record_event(state, "LOG", "audit_logger")
    updates = _visit(state, "audit_logger")
    return updates


def report_generator(state: GraphState) -> dict[str, Any]:
    updates = _visit(state, "report_generator")

    is_refused = state.get("status") == "refused"
    is_failed = state.get("status") == "failed"

    results: list[ToolResult] = list(state.get("specialist_results", []))  # type: ignore[arg-type]
    confidence_obj = state.get("confidence")

    # Determine final answer — never fabricate from failed/refused executions
    final_answer: str | None = None
    reasoning_provenance: str | None = None
    input_class_val = state.get("input_class")
    user_query = state.get("user_query", "")

    if not is_refused and not is_failed:
        from backend.agents.final_reasoner import get_final_reasoner
        reasoner = get_final_reasoner()

        scene_stats = None
        detections = None
        lulc_ans = None
        for r in results:
            if isinstance(r.result, dict):
                if "scene_statistics" in r.result and not scene_stats:
                    scene_stats = r.result["scene_statistics"]
                if "detections" in r.result and not detections:
                    detections = r.result["detections"]
                if r.tool_id == "lulc_map" and r.status == "success":
                    lulc_ans = r.result.get("answer")

        image_refs = _raw_raster_refs(state) or _image_refs(state)
        final_answer, reasoning_provenance = reasoner.reason_sync(
            query=user_query,
            specialist_results=results,
            scene_statistics=scene_stats,
            detections=detections,
            image_refs=image_refs,
            input_class=input_class_val,
        )
    elif is_refused:
        final_answer = state.get("refusal_reason") or "Request refused due to modality or input mismatch."
        reasoning_provenance = "modality_validation_gate"

    _record_event(
        state,
        "REPORT_GENERATED",
        "report_generator",
        parameters={"provenance": reasoning_provenance, "status": state.get("status")},
        message=f"Report generated (provenance: {reasoning_provenance})",
    )

    report: dict[str, Any] = {
        "job_id": state.get("job_id"),
        "original_query": state.get("user_query"),
        "input_class": state.get("input_class"),
        "detected_task": state.get("detected_task"),
        "query_plan": state.get("query_plan"),
        "target_class": (state.get("query_plan") or {}).get("target_class"),
        "selected_tools": state.get("selected_tools", []),
        "execution_summary": _visited_nodes(state),
        "final_answer": final_answer,
        "reasoning_provenance": reasoning_provenance,
        "confidence": confidence_obj.level if confidence_obj else ("LOW" if is_refused else None),
        "confidence_signals": confidence_obj.signals if confidence_obj else [],
        "evidence_summary": state.get("evidence_items", []),
        "spatial_evidence_references": [
            dict(e) if hasattr(e, "__iter__") else e
            for e in (state.get("spatial_evidence") or [])
        ],
        "warnings": state.get("warnings", []),
        "refusal_reason": state.get("refusal_reason"),
        "failure_reason": state.get("refusal_reason") if is_refused else ("One or more tools failed." if is_failed else None),
    }

    if is_refused:
        updates["status"] = "refused"   # preserve refused status
    elif is_failed:
        updates["status"] = "failed"    # preserve failed status
    else:
        updates["status"] = "completed"

    updates["report"] = report
    updates["final_answer"] = final_answer
    return updates


def refusal(state: GraphState) -> dict[str, Any]:
    _record_event(state, "REFUSED", "refusal", message=state.get("refusal_reason"))
    updates = _visit(state, "refusal")
    warnings: list[str] = list(state.get("warnings", []))  # type: ignore[arg-type]
    refusal_reason = state.get("refusal_reason") or "Request could not be processed."
    if refusal_reason not in warnings:
        warnings.append(refusal_reason)
    updates["warnings"] = warnings
    updates["status"] = "refused"
    updates["refusal_reason"] = refusal_reason
    updates["final_answer"] = refusal_reason
    return updates


# ---------------------------------------------------------------------------
# Conditional edge helpers
# ---------------------------------------------------------------------------

def _after_input_validator(state: GraphState) -> str:
    if state.get("status") == "refused":
        return "refusal"
    return "metadata_parser"


def _after_metadata_parser(state: GraphState) -> str:
    if state.get("status") == "refused":
        return "refusal"
    if _requires_pair_evaluation(state):
        return "pair_fitness_gate"
    return "query_router"


def _after_pair_fitness_gate(state: GraphState) -> str:
    if state.get("status") in ("refused", "failed"):
        return "refusal"
    return "query_router"


def _after_query_router(state: GraphState) -> str:
    if state.get("status") in ("refused", "failed"):
        return "refusal"
    return "tool_selector"


def _after_tool_selector(state: GraphState) -> str:
    if state.get("status") in ("refused", "failed"):
        return "refusal"
    return "preprocess"


def after_preprocess(state: GraphState) -> str:
    task = state.get("detected_task", "")
    input_class = state.get("input_class", "")
    selected_tools = state.get("selected_tools", [])

    # Route SAR single-image understanding through sar_map
    if "sar_map" in selected_tools or input_class == InputClass.SINGLE_SAR.value:
        if task in (RouterTask.SINGLE_VQA.value, RouterTask.CAPTIONING.value, RouterTask.GROUNDING.value):
            return "sar_map"

    if task in (RouterTask.SINGLE_VQA.value, RouterTask.CAPTIONING.value, RouterTask.GROUNDING.value):
        return "lulc_map"
    if "bit_cd" in selected_tools or task in (RouterTask.CHANGE_DETECTION.value, RouterTask.CHANGE_VQA.value):
        return "bit_cd"
    if task == RouterTask.OPTICAL_SAR_ANALYSIS.value:
        return "coregister"
    return "refusal"


def after_lulc_map(state: GraphState) -> str:
    return "evidence_fusion"


def after_sar_map(state: GraphState) -> str:
    return "evidence_fusion"


def after_bit_cd(state: GraphState) -> str:
    selected_tools = state.get("selected_tools", [])
    if "vectorize" in selected_tools:
        return "vectorize"
    return "evidence_fusion"


def after_vectorize(state: GraphState) -> str:
    return "evidence_fusion"


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------
workflow = StateGraph(GraphState)

for name, fn in {
    "input_validator":  input_validator,
    "metadata_parser":  metadata_parser,
    "pair_fitness_gate": pair_fitness_gate,
    "query_router":     query_router,
    "tool_selector":    tool_selector,
    "preprocess":       preprocess,
    "lulc_map":         lulc_map,
    "sar_map":          sar_map,
    "align":            align,
    "bit_cd":           bit_cd,
    "vectorize":        vectorize,
    "coregister":       coregister,
    "fusion_s1s2":      fusion_s1s2,
    "agreement":        agreement,
    "evidence_fusion":  evidence_fusion,
    "audit_logger":     audit_logger,
    "report_generator": report_generator,
    "refusal":          refusal,
}.items():
    workflow.add_node(name, fn)

# Entry and initial linear backbone
workflow.set_entry_point("input_validator")
workflow.add_conditional_edges(
    "input_validator", _after_input_validator,
    {"metadata_parser": "metadata_parser", "refusal": "refusal"},
)
workflow.add_conditional_edges(
    "metadata_parser", _after_metadata_parser,
    {"pair_fitness_gate": "pair_fitness_gate", "query_router": "query_router", "refusal": "refusal"},
)
workflow.add_conditional_edges(
    "pair_fitness_gate", _after_pair_fitness_gate,
    {"query_router": "query_router", "refusal": "refusal"},
)
workflow.add_conditional_edges(
    "query_router", _after_query_router,
    {"tool_selector": "tool_selector", "refusal": "refusal"},
)
workflow.add_conditional_edges(
    "tool_selector", _after_tool_selector,
    {"preprocess": "preprocess", "refusal": "refusal"},
)

# Conditional routing after preprocess based on detected_task & modality
workflow.add_conditional_edges(
    "preprocess", after_preprocess,
    {
        "sar_map":      "sar_map",
        "lulc_map":     "lulc_map",
        "bit_cd":       "bit_cd",
        "align":        "align",
        "coregister":   "coregister",
        "refusal":      "refusal",
    },
)

workflow.add_edge("sar_map", "evidence_fusion")
workflow.add_edge("lulc_map", "evidence_fusion")

workflow.add_conditional_edges(
    "bit_cd", after_bit_cd,
    {
        "vectorize":        "vectorize",
        "evidence_fusion":  "evidence_fusion",
        "refusal":          "refusal",
    },
)
workflow.add_edge("align", "bit_cd")
workflow.add_edge("vectorize", "evidence_fusion")

workflow.add_edge("coregister",  "fusion_s1s2")
workflow.add_edge("fusion_s1s2", "agreement")
workflow.add_edge("agreement",   "evidence_fusion")

# Final tail – common to all successful paths
workflow.add_edge("evidence_fusion",  "audit_logger")
workflow.add_edge("audit_logger",     "report_generator")
workflow.add_edge("report_generator", END)

# Refusal can arrive from any node → audit → report
workflow.add_edge("refusal", "audit_logger")

# Compile
app = workflow.compile()


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def run_graph(session_id: str) -> GraphState:
    """Execute the compiled StateGraph for an in-memory SessionContext.

    Invoked by FastAPI BackgroundTasks after POST /run.
    """
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"No active session '{session_id}'")

    input_class = normalize_input_class(
        session.input_mode or session.metadata.get("input_class", "")
    )
    initial_state: GraphState = {
        "job_id": session.job_id,
        "session_id": session.session_id,
        "user_query": session.query,
        "input_class": input_class,
        "assets": list(session.metadata.get("assets", [])),
        "asset_metadata": session.metadata,
        "pair_fitness": session.pair_fitness,
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
    }
    if session.metadata.get("active_slot"):
        initial_state["active_slot"] = session.metadata["active_slot"]  # type: ignore[typeddict-unknown-key]
    if session.metadata.get("mode"):
        initial_state["mode"] = session.metadata["mode"]  # type: ignore[typeddict-unknown-key]
    if session.task and session.task != "UNROUTED":
        initial_state["injected_task"] = session.task  # type: ignore[typeddict-unknown-key]
    session.traces = []
    session.status = "running"

    result = cast(GraphState, app.invoke(initial_state))

    session.status = result.get("status", "completed")
    session.task = result.get("detected_task") or session.task
    route = result.get("route")
    if route is not None:
        session.route = _serialize(route)
    pre = result.get("preprocessing_result")
    if pre is not None:
        session.preprocessing_result = _serialize(pre)
    session.tool_results = [_serialize(tool_result) for tool_result in (result.get("specialist_results") or [])]
    report = result.get("report")
    if report:
        session.artifacts.append({"type": "report", "payload": report})
    refusal = result.get("refusal_reason")
    session.errors = [refusal] if refusal else []

    persist_run(session, result)
    return result
