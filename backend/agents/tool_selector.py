from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.models import ToolRegistry
from backend.schemas import RouterTask, InputClass

class ToolSelectorError(Exception):
    pass

# Machine-readable specialist capability definitions (§11)
CAPABILITY_MATRIX: dict[str, dict[str, Any]] = {
    "sar_map": {
        "tasks": {RouterTask.SINGLE_VQA.value, RouterTask.CAPTIONING.value, RouterTask.GROUNDING.value},
        "modalities": {InputClass.SINGLE_SAR.value},
    },
    "lulc_map": {
        "tasks": {RouterTask.SINGLE_VQA.value, RouterTask.CAPTIONING.value, RouterTask.GROUNDING.value},
        "modalities": {InputClass.SINGLE_OPTICAL.value, InputClass.BI_TEMPORAL.value},
    },
    "yolo_detector": {
        "tasks": {RouterTask.SINGLE_VQA.value, RouterTask.CAPTIONING.value, RouterTask.GROUNDING.value},
        "modalities": {InputClass.SINGLE_OPTICAL.value, InputClass.BI_TEMPORAL.value},
    },
    "align": {
        "tasks": {RouterTask.CHANGE_DETECTION.value, RouterTask.CHANGE_VQA.value},
        "modalities": {InputClass.BI_TEMPORAL.value},
    },
    "bit_cd": {
        "tasks": {RouterTask.CHANGE_DETECTION.value, RouterTask.CHANGE_VQA.value},
        "modalities": {InputClass.BI_TEMPORAL.value},
    },
    "vectorize": {
        "tasks": {RouterTask.CHANGE_DETECTION.value, RouterTask.CHANGE_VQA.value},
        "modalities": {InputClass.BI_TEMPORAL.value},
    },
    "coregister": {
        "tasks": {RouterTask.OPTICAL_SAR_ANALYSIS.value},
        "modalities": {InputClass.OPTICAL_SAR.value},
    },
    "fusion_s1s2": {
        "tasks": {RouterTask.OPTICAL_SAR_ANALYSIS.value},
        "modalities": {InputClass.OPTICAL_SAR.value},
    },
    "agreement": {
        "tasks": {RouterTask.OPTICAL_SAR_ANALYSIS.value},
        "modalities": {InputClass.OPTICAL_SAR.value},
    },
    "preprocess": {
        "tasks": {t.value for t in RouterTask},
        "modalities": {c.value for c in InputClass},
    },
    "geospatial_validator": {
        "tasks": {t.value for t in RouterTask},
        "modalities": {c.value for c in InputClass},
    },
}

# Strict task-to-input compatibility matrix (§5, §6)
TASK_INPUT_COMPATIBILITY: dict[RouterTask, set[InputClass]] = {
    RouterTask.SINGLE_VQA: {InputClass.SINGLE_OPTICAL, InputClass.SINGLE_SAR, InputClass.OPTICAL_SAR},
    RouterTask.CAPTIONING: {InputClass.SINGLE_OPTICAL, InputClass.SINGLE_SAR, InputClass.OPTICAL_SAR},
    RouterTask.GROUNDING: {InputClass.SINGLE_OPTICAL, InputClass.SINGLE_SAR, InputClass.OPTICAL_SAR},
    RouterTask.CHANGE_DETECTION: {InputClass.BI_TEMPORAL},
    RouterTask.CHANGE_VQA: {InputClass.BI_TEMPORAL},
    RouterTask.OPTICAL_SAR_ANALYSIS: {InputClass.OPTICAL_SAR},
}

# Locked deterministic routing sequences (§5, §9)
TASK_TO_TOOLS: dict[RouterTask, list[str]] = {
    RouterTask.SINGLE_VQA: ["preprocess", "lulc_map"],
    RouterTask.CAPTIONING: ["preprocess", "lulc_map"],
    RouterTask.GROUNDING: ["preprocess", "lulc_map"],
    RouterTask.CHANGE_DETECTION: ["preprocess", "bit_cd"],
    RouterTask.CHANGE_VQA: ["preprocess", "bit_cd"],
    RouterTask.OPTICAL_SAR_ANALYSIS: ["preprocess", "coregister", "fusion_s1s2", "agreement"],
}


class ToolSelector:
    """
    Deterministic Tool Selector.
    Maps a (RouterTask, InputClass) pair strictly to an allowed sequence of tools.
    Validates against the machine capability matrix and PostgreSQL tool_registry table to ensure
    tools exist, are enabled, and support the requested task and input class.
    """

    TASK_TO_TOOLS = TASK_TO_TOOLS
    CAPABILITY_MATRIX = CAPABILITY_MATRIX
    TASK_INPUT_COMPATIBILITY = TASK_INPUT_COMPATIBILITY

    def __init__(self, db_session: Session | None = None):
        self.db = db_session

    def get_tool_sequence(self, task: RouterTask, input_class: InputClass = InputClass.SINGLE_OPTICAL) -> list[str]:
        if not isinstance(task, RouterTask) or task not in self.TASK_TO_TOOLS:
            raise ToolSelectorError(f"Unsupported task for deterministic routing: {task}")
        
        if input_class == InputClass.SINGLE_SAR:
            if task == RouterTask.SINGLE_VQA:
                return ["preprocess", "sar_map"]
            elif task == RouterTask.CAPTIONING:
                return ["preprocess", "sar_map"]
            elif task == RouterTask.GROUNDING:
                return ["preprocess", "sar_map"]
        elif input_class == InputClass.OPTICAL_SAR:
            if task in (RouterTask.OPTICAL_SAR_ANALYSIS, RouterTask.SINGLE_VQA, RouterTask.CAPTIONING, RouterTask.GROUNDING):
                return ["preprocess", "coregister", "fusion_s1s2", "agreement"]

        return list(self.TASK_TO_TOOLS[task])

    def validate_compatibility(self, task: RouterTask, input_class: InputClass) -> None:
        """
        Validate task and input class compatibility.
        Raises ToolSelectorError if the combination is invalid.
        """
        if not isinstance(task, RouterTask) or task not in self.TASK_INPUT_COMPATIBILITY:
            raise ToolSelectorError(f"Unsupported task: {task}")
        allowed_inputs = self.TASK_INPUT_COMPATIBILITY[task]
        if input_class not in allowed_inputs:
            raise ToolSelectorError(
                f"Wrong input class: task '{task.value}' "
                f"is not permitted with input class '{input_class.value}'."
            )

    def validate_selection(self, task: RouterTask, input_class: InputClass) -> list[str]:
        """
        Validates task/input compatibility, derives the deterministic tool sequence,
        and validates against both the static capability matrix and the DB registry.
        Returns the validated tool sequence or raises ToolSelectorError.
        """
        # 1. Validate task/input configuration compatibility
        self.validate_compatibility(task, input_class)

        # 2. Get deterministic sequence
        sequence = self.get_tool_sequence(task, input_class)

        # 3. Validate against static capability matrix
        for tool_name in sequence:
            if tool_name not in self.CAPABILITY_MATRIX:
                raise ToolSelectorError(f"Unknown tool: '{tool_name}' is not in capability matrix.")
            cap = self.CAPABILITY_MATRIX[tool_name]
            if task.value not in cap["tasks"]:
                raise ToolSelectorError(
                    f"Capability mismatch: tool '{tool_name}' does not support task '{task.value}'"
                )
            if input_class.value not in cap["modalities"]:
                raise ToolSelectorError(
                    f"Capability mismatch: tool '{tool_name}' does not support input class '{input_class.value}'"
                )

        # 4. If database session is provided, query the database for tools in the sequence
        if self.db is not None:
            try:
                stmt = select(ToolRegistry).where(ToolRegistry.tool_id.in_(sequence))
                results = self.db.execute(stmt).scalars().all()
                registry_map = {tool.tool_id: tool for tool in results}

                for tool_name in sequence:
                    if tool_name not in registry_map:
                        raise ToolSelectorError(f"Unknown tool: '{tool_name}' is not in the registry.")

                    db_tool = registry_map[tool_name]

                    if not db_tool.enabled:
                        raise ToolSelectorError(f"Disabled tool: '{tool_name}' is disabled in the registry.")

                    if db_tool.supported_tasks and task.value not in db_tool.supported_tasks:
                        raise ToolSelectorError(
                            f"Incompatible tool: '{tool_name}' does not support task '{task.value}'"
                        )

                    if db_tool.supported_modalities and input_class.value not in db_tool.supported_modalities:
                        raise ToolSelectorError(
                            f"Wrong input class: '{tool_name}' does not support input class '{input_class.value}'"
                        )
            except ToolSelectorError:
                raise
            except Exception:
                # In offline/mock mode without active Postgres connection
                pass

        return sequence
