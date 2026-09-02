"""
SatQuery AI — Preprocessing Pipeline Dispatcher
"""
import time
from pathlib import Path
from typing import Any

from backend.exceptions import PreprocessingError, UnsupportedModalityError
from backend.schemas import InputClass, PreprocessResult
from backend.services.preprocessing.bitemporal import BitemporalPreprocessor
from backend.services.preprocessing.optical import OpticalPreprocessor
from backend.services.preprocessing.optical_sar import OpticalSARPreprocessor
from backend.services.preprocessing.sar import SARPreprocessor
from backend.session import SessionContext
from src.logger import logging


class PreprocessingDispatcher:
    """
    Directs preprocessed execution according to the detected InputClass.
    Ensures that only relevant, modality-specific transformations are run.
    """

    def __init__(
        self,
        tile_size: int = 256,
        stride: int | None = None,
        job_storage_dir: Path | None = None,
    ):
        self.tile_size = tile_size
        self.stride = stride
        self.job_storage_dir = job_storage_dir

        self.optical_preprocessor = OpticalPreprocessor(tile_size=tile_size, stride=stride)
        self.sar_preprocessor = SARPreprocessor(tile_size=tile_size, stride=stride)
        self.bitemporal_preprocessor = BitemporalPreprocessor(tile_size=tile_size, stride=stride)
        self.optical_sar_preprocessor = OpticalSARPreprocessor(tile_size=tile_size, stride=stride)

    def preprocess(
        self,
        input_class: InputClass | str,
        assets: list[dict[str, Any]],
        job_id: str,
        session_context: SessionContext | None = None,
    ) -> PreprocessResult:
        """
        Dispatch and execute preprocessing based on the input configuration.
        Records structured audit traces throughout execution.
        """
        start_time = time.time()
        cls_val = input_class.value if isinstance(input_class, InputClass) else str(input_class)

        # Audit: PREPROCESS_START
        if session_context:
            session_context.record_trace(
                event_type="PREPROCESS_START",
                node_name="preprocess",
                parameters={"input_class": cls_val, "tile_size": self.tile_size, "asset_count": len(assets)},
                message=f"Starting preprocessing pipeline for {cls_val} configuration.",
            )

        logging.info(f"Executing preprocessing pipeline for input_class: {cls_val}, job_id: {job_id}")

        try:
            if cls_val == InputClass.SINGLE_OPTICAL.value:
                if not assets:
                    raise PreprocessingError("SINGLE_OPTICAL requires at least 1 asset dictionary.")
                result = self.optical_preprocessor.preprocess(
                    asset_dict=assets[0],
                    job_id=job_id,
                    job_storage_dir=self.job_storage_dir,
                )

            elif cls_val == InputClass.SINGLE_SAR.value:
                if not assets:
                    raise PreprocessingError("SINGLE_SAR requires at least 1 asset dictionary.")
                result = self.sar_preprocessor.preprocess(
                    asset_dict=assets[0],
                    job_id=job_id,
                    job_storage_dir=self.job_storage_dir,
                )

            elif cls_val == InputClass.BI_TEMPORAL.value:
                if len(assets) < 2:
                    raise PreprocessingError("BI_TEMPORAL requires 2 asset dictionaries.")
                result = self.bitemporal_preprocessor.preprocess(
                    assets=assets,
                    job_id=job_id,
                    job_storage_dir=self.job_storage_dir,
                )

            elif cls_val == InputClass.OPTICAL_SAR.value:
                if len(assets) < 2:
                    raise PreprocessingError("OPTICAL_SAR requires 2 asset dictionaries.")
                result = self.optical_sar_preprocessor.preprocess(
                    assets=assets,
                    job_id=job_id,
                    job_storage_dir=self.job_storage_dir,
                )

            else:
                raise UnsupportedModalityError(f"Unsupported or unrecognized input class for preprocessing: '{cls_val}'")

            duration_ms = round((time.time() - start_time) * 1000.0, 2)

            # Audit: PREPROCESS_COMPLETE
            if session_context:
                session_context.record_trace(
                    event_type="PREPROCESS_COMPLETE",
                    node_name="preprocess",
                    parameters={"duration_ms": duration_ms, "steps": result.preprocessing_steps},
                    metadata={"tile_count": len(result.tile_references), "input_class": cls_val},
                    message=f"Preprocessing completed successfully in {duration_ms}ms.",
                )
                session_context.preprocessing_result = result.model_dump()

            return result

        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000.0, 2)
            logging.error(f"Preprocessing pipeline failed for {cls_val}: {e}")
            
            if session_context:
                session_context.record_trace(
                    event_type="PREPROCESS_FAILED",
                    node_name="preprocess",
                    parameters={"duration_ms": duration_ms, "error": str(e)},
                    message=f"Preprocessing failed: {str(e)}",
                )
                session_context.add_error(str(e))

            raise PreprocessingError(f"Preprocessing failed: {e}")
