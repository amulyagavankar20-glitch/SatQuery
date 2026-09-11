"""Download SARChat-InternVL2.5 weights into weights/specialists/sarchat.

Auth: MODELSCOPE_TOKEN env, or a local model_scope.md (gitignored).
Never prints the token.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO = "JimmyMa99/SARChat-InternVL2.5-2B"
ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "weights" / "specialists" / "sarchat"


def _looks_ready(path: Path) -> bool:
    return path.is_dir() and (
        (path / "config.json").is_file() or any(path.glob("*.safetensors"))
    )


def _token() -> str | None:
    env = (os.environ.get("MODELSCOPE_TOKEN") or "").strip()
    if env:
        return env
    md = ROOT / "model_scope.md"
    if md.is_file():
        text = md.read_text(encoding="utf-8")
        match = re.search(r"ms-[0-9a-fA-F-]{8,}", text)
        if match:
            return match.group(0)
    return None


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    if _looks_ready(DEST):
        print(f"already present: {DEST}")
        return

    token = _token()
    if token:
        from modelscope.hub.api import HubApi

        HubApi().login(token)
        print("modelscope login ok")
    else:
        print("no MODELSCOPE_TOKEN; trying anonymous download")

    from modelscope import snapshot_download

    print(f"modelscope snapshot {REPO} -> {DEST}")
    snapshot_download(REPO, local_dir=str(DEST))
    if not _looks_ready(DEST):
        raise SystemExit(f"download finished but {DEST} is not a loadable checkpoint")
    print(f"ok {DEST}")


if __name__ == "__main__":
    main()
