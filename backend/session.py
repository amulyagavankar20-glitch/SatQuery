"""
SatQuery AI — In-Memory Working Session Store
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any



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
    metadata: dict[str, Any] = field(default_factory=dict)
    pair_fitness: dict[str, Any] = field(default_factory=dict)
    classification: dict[str, Any] | None = None
    route: dict[str, Any] = field(default_factory=dict)
    preprocessing_result: dict[str, Any] | None = None
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    traces: list[dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    errors: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def record_trace(
        self,
        event_type: str,
        node_name: str | None = None,
        tool_id: str | None = None,
        message: str | None = None,
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
_ACTIVE_SESSIONS: dict[str, SessionContext] = {}


def create_session(
    session_id: str | uuid.UUID | None = None,
    job_id: str | uuid.UUID | None = None,
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


def get_session(session_id: str | uuid.UUID) -> SessionContext | None:
    """Retrieve an active SessionContext by session_id."""
    return _ACTIVE_SESSIONS.get(str(session_id))


def get_session_by_job_id(job_id: str | uuid.UUID) -> SessionContext | None:
    """Retrieve an active SessionContext by job_id, falling back to session_id."""
    jid = str(job_id)
    for session in _ACTIVE_SESSIONS.values():
        if session.job_id == jid:
            return session
    return get_session(jid)


def remove_session(session_id: str | uuid.UUID) -> SessionContext | None:
    """Remove a finished SessionContext from memory."""
    return _ACTIVE_SESSIONS.pop(str(session_id), None)


def list_active_sessions() -> list[str]:
    """Return all active session IDs."""
    return list(_ACTIVE_SESSIONS.keys())
