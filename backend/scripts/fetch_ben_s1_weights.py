"""Download reBEN ResNet50 trained on Sentinel-1 BigEarthNet v2 (~95 MB)."""
from __future__ import annotations

from pathlib import Path

REPO = "BIFOLD-BigEarthNetv2-0/resnet50-s1-v0.2.0"
DEST = Path(__file__).resolve().parents[2] / "weights" / "specialists" / "ben_s1"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    if (DEST / "model.safetensors").is_file() or (DEST / "pytorch_model.bin").is_file():
        print(f"already present: {DEST}")
        return
    from huggingface_hub import snapshot_download

    print(f"huggingface snapshot {REPO} -> {DEST}")
    snapshot_download(repo_id=REPO, local_dir=str(DEST))
    print(f"ok {DEST}")


if __name__ == "__main__":
    main()
