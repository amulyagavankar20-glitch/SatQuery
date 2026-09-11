"""Fetch the tiny Dynamic World weights (~1 MB). Does not fetch Prithvi.

  python -m backend.scripts.fetch_lulc_weights

Prithvi Sen1Floods11 is optional and large. Set PRITHVI_FLOOD_WEIGHTS_PATH
to a local snapshot if you want the flood head; otherwise flood queries use
Dynamic World's water + flooded_vegetation classes.
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve

from backend.config import settings

# Apache-2.0 PyTorch port of Google Dynamic World (Brown et al. 2022).
DW_URL = "https://github.com/calebrob6/dynamic_world_pytorch/raw/main/weights/dynamic_world.pt"


def main() -> None:
    dest_dir = Path(settings.BASE_DIR) / settings.WEIGHTS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "dynamic_world.pt"
    if dest.is_file() and dest.stat().st_size > 10_000:
        print(f"already present: {dest}")
        return
    print(f"downloading {DW_URL} -> {dest}")
    urlretrieve(DW_URL, dest)
    print(f"ok {dest.stat().st_size} bytes")


if __name__ == "__main__":
    main()
