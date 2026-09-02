"""
SatQuery AI — Backend Package
"""

import os
from pathlib import Path


def _use_rasterio_proj_data() -> None:
    """Avoid PostGIS's older PROJ database on Windows (PROJ_LIB from PostgreSQL)."""
    current = os.environ.get("PROJ_LIB", "")
    if current and "postgis" not in current.lower() and (Path(current) / "proj.db").exists():
        os.environ.setdefault("PROJ_DATA", current)
        return
    try:
        import importlib.util
        spec = importlib.util.find_spec("rasterio")
    except ModuleNotFoundError:
        return
    if spec is None or not spec.origin:
        return
    proj_dir = Path(spec.origin).resolve().parent / "proj_data"
    if (proj_dir / "proj.db").exists():
        os.environ["PROJ_LIB"] = str(proj_dir)
        os.environ["PROJ_DATA"] = str(proj_dir)


_use_rasterio_proj_data()
