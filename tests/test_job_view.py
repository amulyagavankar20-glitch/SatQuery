"""JobView contract tests (docs/api-spec.md)."""

from backend.schemas import JobView


def test_job_view_accepts_spec_payload():
    view = JobView.model_validate({
        "job_id": "e42b5666-8a75-4285-b07f-864450b4b558",
        "session_id": "55363795-2153-4cdc-a654-65a7690ce877",
        "status": "completed",
        "query": "What land-cover classes are visible?",
        "input_class": "SINGLE_OPTICAL",
        "task": "CAPTIONING",
        "route": {
            "task": "CAPTIONING",
            "input_mode": "SINGLE_OPTICAL",
            "tools": ["geochat_describe"],
            "need_overlay": False,
            "params": {},
        },
        "answer": {
            "text": "MOCK_VQA_ANSWER",
            "model": "OpenGVLab/InternVL3-1B",
            "backend": "mock",
            "confidence": "MEDIUM",
        },
        "assets": [{
            "filename": "cartosat2s_demo.tif",
            "modality": "OPTICAL",
            "sensor": "Cartosat-2S",
            "bounds_wgs84": [72.5, 23.0, 72.7, 23.2],
            "preview_url": "/jobs/e42b5666-8a75-4285-b07f-864450b4b558/artifacts/composite",
        }],
        "overlays": [{
            "type": "FOOTPRINT",
            "geojson_url": "/jobs/e42b5666-8a75-4285-b07f-864450b4b558/export.geojson",
            "confidence": None,
        }],
        "traces": [],
        "warnings": [],
        "errors": [],
        "refusal_reason": None,
        "tile_count": 4,
    })
    dumped = view.model_dump()
    assert "file_path" not in dumped["assets"][0]
    assert dumped["assets"][0]["preview_url"].startswith("/jobs/")
    assert dumped["answer"]["backend"] == "mock"


def test_safe_job_file_rejects_path_escape(tmp_path, monkeypatch):
    from backend.services import job_view as jv

    job_id = "11111111-1111-1111-1111-111111111111"
    job_root = tmp_path / job_id
    (job_root / "processed").mkdir(parents=True)
    inside = job_root / "processed" / "ok.png"
    inside.write_bytes(b"x")
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"no")

    monkeypatch.setattr(jv, "_job_dir", lambda jid: tmp_path / str(jid))

    assert jv.safe_job_file(job_id, inside) == inside.resolve()
    assert jv.safe_job_file(job_id, outside) is None
