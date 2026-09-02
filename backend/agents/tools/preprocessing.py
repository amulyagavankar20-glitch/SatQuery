"""Preprocessing Agent Tool Wrapper

This module provides an agent-friendly interface to the existing Stage 3 preprocessing
pipeline (backend.services.preprocessing). It is deliberately lightweight and does
not alter the underlying preprocessing implementation.

The wrapper is intended to be used as a deterministic tool identified by the
tool ID "preprocess" in the `ToolSelector`. It accepts the same parameters that
the dispatcher requires and returns a `PreprocessResult` instance.
"""

from typing import List, Dict, Any, Optional

from backend.schemas import InputClass, PreprocessResult
from backend.services.preprocessing.dispatcher import PreprocessingDispatcher
from backend.session import SessionContext


def run_preprocessing(
    input_class: InputClass,
    assets: List[Dict[str, Any]],
    job_id: str,
    session_context: Optional[SessionContext] = None,
) -> PreprocessResult:
    """Execute the preprocessing pipeline for a given job.

    Parameters
    ----------
    input_class: InputClass
        The classified input configuration (SINGLE_OPTICAL, SINGLE_SAR, etc.).
    assets: List[Dict[str, Any]]
        A list of asset dictionaries describing image paths and metadata.
    job_id: str
        The unique identifier for the current job/session.
    session_context: Optional[SessionContext]
        The current session used for trace recording. If provided, audit events
        are recorded via ``session_context.record_trace``.

    Returns
    -------
    PreprocessResult
        The result object produced by the underlying dispatcher.
    """
    # Instantiate the dispatcher with default parameters; these can be
    # customized later via environment variables or configuration if needed.
    dispatcher = PreprocessingDispatcher()

    # Delegate to the dispatcher. It handles all validation and trace
    # recording internally.
    return dispatcher.preprocess(
        input_class=input_class,
        assets=assets,
        job_id=job_id,
        session_context=session_context,
    )
