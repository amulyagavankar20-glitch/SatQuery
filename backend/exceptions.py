"""
SatQuery AI — Custom Exception Hierarchy
"""
import sys
from typing import Optional, Dict, Any


class SatQueryBaseException(Exception):
    """Base exception class for all SatQuery domain errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class InputClassifierError(SatQueryBaseException):
    """Raised when an error occurs during input classification."""
    pass


class UnsupportedFormatError(SatQueryBaseException):
    """Raised when an unsupported file format or raster encoding is provided."""
    pass


class InvalidRasterError(SatQueryBaseException):
    """Raised when a raster file is corrupt, unreadable, or contains invalid dimensions/bands."""
    pass


class MissingMetadataError(SatQueryBaseException):
    """Raised when essential metadata (CRS, acquisition date, modality) is missing."""
    pass


class UnsupportedModalityError(SatQueryBaseException):
    """Raised when an unknown or unsupported sensor modality is supplied."""
    pass


class InsufficientOverlapError(SatQueryBaseException):
    """Raised when multi-image pairs do not share adequate spatial intersection."""
    pass


class InvalidTemporalPairError(SatQueryBaseException):
    """Raised when a bitemporal pair has identical dates, inverted sequence, or invalid temporal relationship."""
    pass


class PreprocessingError(SatQueryBaseException):
    """Raised when a failure occurs during raster preprocessing, resampling, or tiling."""
    pass
