"""Optional Prithvi-EO Sen1Floods11 flood head.

Never imported at module load of the graph. Called only when
``PRITHVI_FLOOD_WEIGHTS_PATH`` is set and the query is flood/inundation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def run_prithvi_flood(image_path: str, weights: Path) -> np.ndarray:
    """Return a boolean flood mask at the input image's H×W.

    Raises if TerraTorch / the checkpoint cannot be loaded so the caller
    can fall back to Dynamic World's water + flooded_vegetation classes.
    """
    raise RuntimeError(
        "Prithvi flood weights are configured but the TerraTorch inference "
        f"adapter is not loaded ({weights}). Falling back to Dynamic World water."
    )
