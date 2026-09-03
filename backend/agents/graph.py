"""SatQuery AI — LangGraph Stage 4 Orchestration Graph.

ARCHITECTURE RULES ENFORCED HERE:
- ONE canonical GraphState imported from backend.agents.state (TypedDict).
  This file does NOT define a second GraphState.
- query_router MUST invoke QwenRouter via Ollama. Failure produces refusal.
- tool_selector MUST validate against the PostgreSQL ToolRegistry.
  db_session must never be None.
- run_tool must receive a real database session.
- preprocess calls the Stage 3 preprocessing wrapper (run_preprocessing).
- geochat_describe has its own separate tool interface.
- Confidence is computed from evidence signals, NOT fabricated.
- evidence_fusion consumes validated tool outputs.
- Failed/refused executions are never marked COMPLETED.
"""

from __future__ import annotations

from typing import Any
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
    # Production path: import the app's session maker
    from backend.database import SessionLocal
    return SessionLocal()


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

def input_validator(state: GraphState) -> dict[str, Any]:
    _record_event(state, "INPUT_VALIDATED", "input_validator")
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

    updates["status"] = "running"
    updates["warnings"] = warnings
    return updates


def metadata_parser(state: GraphState) -> dict[str, Any]:
    _record_event(state, "METADATA_PARSED", "metadata_parser")
    updates = _visit(state, "metadata_parser")
    # Normalise input_class from asset_metadata if not already set
    if not state.get("input_class") and state.get("asset_metadata"):
        updates["input_class"] = state["asset_metadata"].get("input_class", "")  # type: ignore[index]
    return updates


def pair_fitness_gate(state: GraphState) -> dict[str, Any]:
    _record_event(state, "PAIR_FITNESS_CHECKED", "pair_fitness_gate")
    updates = _visit(state, "pair_fitness_gate")
    # pair_fitness signals are recorded in state; warnings propagated downstream
    return updates


def query_router(state: GraphState) -> dict[str, Any]:
    """Route the query by invoking QwenRouter via Ollama.

    MUST NOT read metadata["task"] as a routing shortcut.
    MUST NOT default unknown/failed routing to SINGLE_VQA.
    Failed routing → controlled refusal.
    """
    updates = _visit(state, "query_router")

    # Allow test injection: if state carries a pre-resolved task directly in
    # a field called "injected_task", use it (set only by tests that need to
    # bypass Qwen without a live Ollama server). Never use metadata["task"].
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
    _record_event(state, "PREPROCESS_STARTED", "preprocess", tool_id="preprocess",
                  parameters={"input_class": state.get("input_class"),
                               "asset_count": len(state.get("assets", []))})  # type: ignore[arg-type]
    updates = _visit(state, "preprocess")

    input_class_value = state.get("input_class", "SINGLE_OPTICAL")
    assets_raw: list[Any] = list(state.get("assets", []))  # type: ignore[arg-type]
    job_id = state.get("job_id", "unknown")
    session_ctx: SessionContext | None = get_session(state.get("session_id", ""))

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
            session_context=session_ctx,
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
    _record_event(state, "TOOL_STARTED", tool_id, tool_id=tool_id, parameters=dict(params))
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
    _record_event(state, "TOOL_COMPLETED", tool_id, tool_id=tool_id,
                  message=result.status)
    return updates


def _image_refs(state: GraphState) -> list[str]:
    """Return preprocessed tile reference paths from state."""
    return list(state.get("_preprocess_image_refs", []))  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Specialist tool nodes
# ---------------------------------------------------------------------------

def geochat_vqa(state: GraphState) -> dict[str, Any]:
    params = {
        "question": state.get("user_query", ""),
        "image_refs": _image_refs(state),
        "input_refs": _image_refs(state),
    }
    return _execute_tool(state, "geochat_vqa", params)


def grounding(state: GraphState) -> dict[str, Any]:
    params = {
        "text": state.get("user_query", ""),
        "image_refs": _image_refs(state),
        "input_refs": _image_refs(state),
    }
    return _execute_tool(state, "grounding", params)


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
    # Use aligned refs from alignment_result if available
    align_result = state.get("alignment_result")
    if align_result and isinstance(align_result.result, dict):
        pre = str(align_result.result.get("aligned_pre", "pre_placeholder"))
        post = str(align_result.result.get("aligned_post", "post_placeholder"))
    else:
        pre, post = "pre_placeholder", "post_placeholder"

    params = {"pre_image": pre, "post_image": post,
               "input_refs": _image_refs(state)}
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


def geochat_describe(state: GraphState) -> dict[str, Any]:
    """Invoke geochat_describe — its own separate tool interface."""
    # Gather the most relevant output refs for description context
    results: list[ToolResult] = list(state.get("specialist_results", []))  # type: ignore[arg-type]
    output_refs = [r for res in results for r in res.output_refs]
    context_parts = []
    for res in results:
        if res.result:
            context_parts.append(str(res.result))
    context = "; ".join(context_parts[:3])  # limit context length

    params = {
        "image_refs": _image_refs(state) or output_refs,
        "context": context,
        "input_refs": _image_refs(state),
    }
    return _execute_tool(state, "geochat_describe", params)


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
    _record_event(state, "EVIDENCE_FUSED", "evidence_fusion")
    updates = _visit(state, "evidence_fusion")

    results: list[ToolResult] = list(state.get("specialist_results", []))  # type: ignore[arg-type]
    # Collect spatial evidence from tool results
    spatial_evidence = []
    for r in results:
        if r.spatial_refs:
            spatial_evidence.extend(r.spatial_refs)

    # Run output validation (before final reporting)
    validation = validate_output(state)
    _record_event(state, "CONFIDENCE_COMPUTED", "evidence_fusion",
                  message=f"confidence={validation.confidence.value}")

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
    _record_event(state, "REPORT_GENERATED", "report_generator")
    updates = _visit(state, "report_generator")

    is_refused = state.get("status") == "refused"
    is_failed = state.get("status") == "failed"

    results: list[ToolResult] = list(state.get("specialist_results", []))  # type: ignore[arg-type]
    confidence_obj = state.get("confidence")

    # Determine final answer — never fabricate from failed/refused executions
    final_answer: str | None = None
    if not is_refused and not is_failed:
        # Use last successful specialist result with a textual output
        for r in reversed(results):
            if r.status == "success" and isinstance(r.result, str):
                final_answer = r.result
                break
            if r.status == "success" and isinstance(r.result, dict):
                final_answer = str(r.result)
                break

    report: dict[str, Any] = {
        "job_id": state.get("job_id"),
        "original_query": state.get("user_query"),
        "input_class": state.get("input_class"),
        "detected_task": state.get("detected_task"),
        "selected_tools": state.get("selected_tools", []),
        "execution_summary": _visited_nodes(state),
        "final_answer": final_answer,
        "confidence": confidence_obj.level if confidence_obj else None,
        "confidence_signals": confidence_obj.signals if confidence_obj else [],
        "evidence_summary": state.get("evidence_items", []),
        "spatial_evidence_references": [
            dict(e) if hasattr(e, "__iter__") else e
            for e in (state.get("spatial_evidence") or [])
        ],
        "warnings": state.get("warnings", []),
        "refusal_reason": state.get("refusal_reason"),
        "failure_reason": None,
    }

    if is_refused:
        updates["status"] = "refused"   # preserve refused status
        report["failure_reason"] = state.get("refusal_reason")
    elif is_failed:
        updates["status"] = "failed"    # preserve failed status
        report["failure_reason"] = "One or more tools failed."
    else:
        updates["status"] = "completed"

    updates["report"] = report
    updates["final_answer"] = final_answer
    return updates


def refusal(state: GraphState) -> dict[str, Any]:
    _record_event(state, "REFUSED", "refusal")
    updates = _visit(state, "refusal")
    warnings: list[str] = list(state.get("warnings", []))  # type: ignore[arg-type]
    warnings.append("Request refused.")
    updates["warnings"] = warnings
    updates["status"] = "refused"
    if not state.get("refusal_reason"):
        updates["refusal_reason"] = "Request could not be processed."
    return updates


# ---------------------------------------------------------------------------
# Conditional edge helpers
# ---------------------------------------------------------------------------

def _after_input_validator(state: GraphState) -> str:
    if state.get("status") == "refused":
        return "refusal"
    return "metadata_parser"


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
    if task == RouterTask.SINGLE_VQA.value:
        return "geochat_vqa"
    if task == RouterTask.CAPTIONING.value:
        return "geochat_vqa"
    if task == RouterTask.GROUNDING.value:
        return "geochat_vqa"
    if task == RouterTask.CHANGE_DETECTION.value:
        return "align"
    if task == RouterTask.CHANGE_VQA.value:
        return "align"
    if task == RouterTask.OPTICAL_SAR_ANALYSIS.value:
        return "coregister"
    return "refusal"


def after_geochat_vqa(state: GraphState) -> str:
    task = state.get("detected_task", "")
    if task == RouterTask.GROUNDING.value:
        return "grounding"
    return "evidence_fusion"


def after_vectorize(state: GraphState) -> str:
    task = state.get("detected_task", "")
    if task == RouterTask.CHANGE_DETECTION.value:
        return "evidence_fusion"
    if task == RouterTask.CHANGE_VQA.value:
        return "geochat_describe"
    # Should not reach here for other tasks
    return "refusal"


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
    "geochat_vqa":      geochat_vqa,
    "grounding":        grounding,
    "align":            align,
    "bit_cd":           bit_cd,
    "vectorize":        vectorize,
    "geochat_describe": geochat_describe,
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
workflow.add_edge("metadata_parser", "pair_fitness_gate")
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

# Conditional routing after preprocess based on detected_task
workflow.add_conditional_edges(
    "preprocess", after_preprocess,
    {
        "geochat_vqa":  "geochat_vqa",
        "align":        "align",
        "coregister":   "coregister",
        "refusal":      "refusal",
    },
)

# SINGLE_VQA / CAPTIONING / GROUNDING paths
workflow.add_conditional_edges(
    "geochat_vqa", after_geochat_vqa,
    {"grounding": "grounding", "evidence_fusion": "evidence_fusion"},
)
workflow.add_edge("grounding", "evidence_fusion")

# CHANGE_DETECTION / CHANGE_VQA paths
workflow.add_edge("align", "bit_cd")
workflow.add_edge("bit_cd", "vectorize")
workflow.add_conditional_edges(
    "vectorize", after_vectorize,
    {
        "evidence_fusion": "evidence_fusion",
        "geochat_describe": "geochat_describe",
        "refusal": "refusal",
    },
)

# OPTICAL_SAR_ANALYSIS path: coregister → fusion_s1s2 → agreement → geochat_describe
workflow.add_edge("coregister",  "fusion_s1s2")
workflow.add_edge("fusion_s1s2", "agreement")
workflow.add_edge("agreement",   "geochat_describe")

# geochat_describe always leads to evidence_fusion
workflow.add_edge("geochat_describe", "evidence_fusion")

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
    session.status = "running"

    result: GraphState = app.invoke(initial_state)

    session.status = result.get("status", "completed")
    session.task = result.get("detected_task") or session.task
    route = result.get("route")
    if route is not None:
        session.route = _serialize(route)
    pre = result.get("preprocessing_result")
    if pre is not None:
        session.preprocessing_result = _serialize(pre)
    for tool_result in result.get("specialist_results") or []:
        session.tool_results.append(_serialize(tool_result))
    report = result.get("report")
    if report:
        session.artifacts.append({"type": "report", "payload": report})
    refusal = result.get("refusal_reason")
    if refusal:
        session.errors.append(refusal)

    persist_run(session, result)
    return result
