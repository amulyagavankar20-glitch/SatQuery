from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from PIL import Image

BASE = "http://127.0.0.1:8000"
TIF = Path("web/public/presentation/s2_water.tif")
OUT = Path("data/fixtures/s2_water_map_check.json")
COMP = Path("data/fixtures/s2_water_composite.png")


def get(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


def get_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def post_json(url: str, payload: dict):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def post_ingest(path: Path, sensor: str, query: str):
    boundary = "----SatQueryBoundary"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="sensor"\r\n\r\n{sensor}\r\n'.encode())
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="query"\r\n\r\n{query}\r\n'.encode())
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="files"; filename="{path.name}"\r\n'.encode())
    body.extend(b"Content-Type: image/tiff\r\n\r\n")
    body.extend(path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"{BASE}/ingest",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def main() -> None:
    query = "Highlight the water body"
    ingest = post_ingest(TIF, "Sentinel-2", query)
    post_json(f"{BASE}/run", {"job_id": ingest["job_id"], "query": query})
    view = {}
    for _ in range(90):
        time.sleep(1)
        view = get(f"{BASE}/jobs/{ingest['job_id']}")
        if view.get("status") in {"completed", "failed", "refused"}:
            break

    job_id = ingest["job_id"]
    answer = ((view.get("answer") or {}).get("text") or "")
    tools = [t.get("tool_id") or t.get("node_name") for t in (view.get("traces") or [])]
    lulc = view.get("lulc") or {}

    composite_ok = False
    composite_size = None
    try:
        raw = get_bytes(f"{BASE}/jobs/{job_id}/artifacts/composite")
        COMP.parent.mkdir(parents=True, exist_ok=True)
        COMP.write_bytes(raw)
        img = Image.open(COMP)
        composite_ok = img.format == "PNG" and img.size[0] >= 64
        composite_size = list(img.size)
    except Exception as exc:
        composite_ok = False
        composite_size = str(exc)

    overlays = {"n": 0, "labels": []}
    try:
        gj = json.loads(get_bytes(f"{BASE}/jobs/{job_id}/export.geojson").decode())
        feats = gj.get("features") or []
        overlays = {
            "n": len(feats),
            "labels": [f.get("properties", {}).get("label") or f.get("properties", {}).get("class") for f in feats],
            "kinds": [f.get("properties", {}).get("kind") for f in feats],
        }
    except Exception as exc:
        overlays = {"error": str(exc)}

    report = {
        "job_id": job_id,
        "status": view.get("status"),
        "task": view.get("task"),
        "has_mock": "MOCK_" in answer or "GEOCHAT" in answer.upper(),
        "has_geochat_tool": any("geochat" in str(t).lower() for t in tools),
        "tools": tools,
        "lulc_backend": lulc.get("backend"),
        "water_frac": (lulc.get("fractions") or {}).get("water"),
        "answer_preview": answer[:500],
        "composite_ok": composite_ok,
        "composite_size": composite_size,
        "overlays": overlays,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if view.get("status") != "completed":
        raise SystemExit("job not completed")
    if report["has_mock"] or report["has_geochat_tool"]:
        raise SystemExit("mock geochat still in output")
    if not composite_ok:
        raise SystemExit("composite png missing")


if __name__ == "__main__":
    main()
