"""
SatQuery AI — In-Memory Working Session Store
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from backend.exceptions import SatQueryBaseException


@dataclass
class SessionContext:
    """
    Live working memory for an active analysis run in the FastAPI backend process.
    
    Holds in-flight intermediate representations, metadata, pair-fitness validations,
    classifier output, routing, and tool results during execution before final
    persistence to PostgreSQL / PostGIS.
    """
    session_id: str
    job_id: str
    query: str = ""
    input_mode: str = ""
    task: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    pair_fitness: Dict[str, Any] = field(default_factory=dict)
    classification: Optional[Dict[str, Any]] = None
    route: Dict[str, Any] = field(default_factory=dict)
    preprocessing_result: Optional[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    traces: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    errors: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def record_trace(
        self,
        event_type: str,
        node_name: Optional[str] = None,
        tool_id: Optional[str] = None,
        message: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an in-flight trace event into working memory."""
        event = {
            "event_type": event_type,
            "node_name": node_name,
            "tool_id": tool_id,
            "message": message,
            "parameters": parameters or {},
            "trace_metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.traces.append(event)
        self.updated_at = datetime.now(timezone.utc)
        return event

    def add_error(self, error_message: str) -> None:
        """Add an error message and update session status."""
        self.errors.append(error_message)
        self.status = "failed"
        self.updated_at = datetime.now(timezone.utc)


# In-memory dictionary holding active runs keyed by session_id (string UUID)
_ACTIVE_SESSIONS: Dict[str, SessionContext] = {}


def create_session(
    session_id: Optional[Union[str, uuid.UUID]] = None,
    job_id: Optional[Union[str, uuid.UUID]] = None,
    query: str = "",
    input_mode: str = "",
    task: str = "",
) -> SessionContext:
    """Create and register a new SessionContext in memory."""
    s_id = str(session_id or uuid.uuid4())
    j_id = str(job_id or uuid.uuid4())
    session = SessionContext(
        session_id=s_id,
        job_id=j_id,
        query=query,
        input_mode=input_mode,
        task=task,
    )
    _ACTIVE_SESSIONS[s_id] = session
    return session


def get_session(session_id: Union[str, uuid.UUID]) -> Optional[SessionContext]:
    """Retrieve an active SessionContext by session_id."""
    return _ACTIVE_SESSIONS.get(str(session_id))


def remove_session(session_id: Union[str, uuid.UUID]) -> Optional[SessionContext]:
    """Remove a finished SessionContext from memory."""
    return _ACTIVE_SESSIONS.pop(str(session_id), None)


def list_active_sessions() -> List[str]:
    """Return all active session IDs."""
    return list(_ACTIVE_SESSIONS.keys())
