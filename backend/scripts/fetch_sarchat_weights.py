"""Download SARChat-InternVL2.5 weights into weights/specialists/sarchat.

Tries ModelScope first (upstream), then Hugging Face. Safe to re-run.
"""
from __future__ import annotations

from pathlib import Path

REPO = "JimmyMa99/SARChat-InternVL2.5-2B"
DEST = Path(__file__).resolve().parents[2] / "weights" / "specialists" / "sarchat"


def _looks_ready(path: Path) -> bool:
    return path.is_dir() and (
        (path / "config.json").is_file() or any(path.glob("*.safetensors"))
    )


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    if _looks_ready(DEST):
        print(f"already present: {DEST}")
        return

    try:
        from modelscope.hub.snapshot_download import snapshot_download

        print(f"modelscope snapshot {REPO} -> {DEST}")
        snapshot_download(REPO, local_dir=str(DEST))
        print("ok modelscope")
        return
    except Exception as exc:
        print(f"modelscope failed: {exc}")

    try:
        from huggingface_hub import snapshot_download as hf_download

        print(f"huggingface snapshot {REPO} -> {DEST}")
        hf_download(repo_id=REPO, local_dir=str(DEST))
        print("ok huggingface")
        return
    except Exception as exc:
        print(f"huggingface failed: {exc}")
        raise SystemExit(
            "Could not download SARChat weights. Pipeline will talk over SAR "
            "composites via OpenRouter Gemma until weights are placed at "
            f"{DEST}"
        )


if __name__ == "__main__":
    main()
