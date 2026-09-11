"""
SatQuery AI — Legacy Qwen-VL service alias (re-exports from generic VLM service)
"""
from backend.services.vlm import (  # noqa: F401
    VLMClient as QwenVLClient,
    get_vlm_client as get_qwen_vl_client,
    VLMError as QwenVLError,
    VLMConfigError as QwenVLConfigError,
    VLMCostSafetyError as QwenVLCostSafetyError,
    VLMAuthError as QwenVLAuthError,
    VLMRateLimitError as QwenVLRateLimitError,
    VLMModelUnavailableError as QwenVLModelUnavailableError,
    VLMTimeoutError as QwenVLTimeoutError,
    _sanitize_error_message,
    _encode_image_to_data_uri,
)
