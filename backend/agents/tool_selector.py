from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.models import ToolRegistry
from backend.schemas import RouterTask, InputClass

class ToolSelectorError(Exception):
    pass

class ToolSelector:
    """
    Deterministic Tool Selector.
    Maps a RouterTask strictly to an allowed sequence of tools.
    Validates against the PostgreSQL tool_registry table to ensure
    tools are enabled, exist, and support the requested task/input class.
    """
    
    # Hardcoded deterministic sequences per architecture
    TASK_TO_TOOLS = {
        RouterTask.SINGLE_VQA: ["preprocess", "geochat_vqa"],
        RouterTask.CAPTIONING: ["preprocess", "geochat_vqa"],
        RouterTask.GROUNDING: ["preprocess", "geochat_vqa", "grounding"],
        RouterTask.CHANGE_DETECTION: ["preprocess", "align", "bit_cd", "vectorize"],
        RouterTask.CHANGE_VQA: ["preprocess", "align", "bit_cd", "vectorize", "geochat_describe"],
        RouterTask.OPTICAL_SAR_ANALYSIS: ["preprocess", "coregister", "fusion_s1s2", "agreement", "geochat_describe"],
    }

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_tool_sequence(self, task: RouterTask) -> list[str]:
        if task not in self.TASK_TO_TOOLS:
            raise ToolSelectorError(f"Unsupported task for deterministic routing: {task}")
        return self.TASK_TO_TOOLS[task]

    def validate_selection(self, task: RouterTask, input_class: InputClass) -> list[str]:
        """
        Gets the deterministic tool sequence and validates it against the DB registry.
        Returns the validated tool sequence or raises ToolSelectorError.
        """
        sequence = self.get_tool_sequence(task)
        
        # Query the database for all tools in the sequence
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
                
        return sequence
