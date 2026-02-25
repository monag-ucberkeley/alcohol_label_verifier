import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

DATASET_DIR = Path(__file__).resolve().parents[2] / "sample_data" / "cola_paired_dataset"


@pytest.mark.skipif(not DATASET_DIR.exists(), reason="cola_paired_dataset not present in sample_data/")
def test_cola_paired_dataset_runs_end_to_end():
    index_path = DATASET_DIR / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(index) > 0, "index.json is empty"

    for row in index:
        label_path = DATASET_DIR / row["label_path"]
        app_path = DATASET_DIR / row["application_json_path"]

        app_json = json.loads(app_path.read_text(encoding="utf-8"))
        files = {"file": ("label.png", label_path.read_bytes(), "image/png")}
        data = {
            "brand_name": app_json["brand_name"],
            "abv": app_json.get("abv", ""),
            "net_contents": app_json.get("net_contents", ""),
            "require_gov_warning": "true" if app_json.get("government_warning_required", True) else "false",
        }

        resp = client.post("/api/verify-with-application-json", files=files, data=data)
        assert resp.status_code == 200, (row, resp.text)
        payload = resp.json()

        # ensure response shape supports UI
        assert "checks" in payload or "results" in payload, f"Missing checks/results in payload for {row}"

        checks = payload.get("checks") or payload.get("results") or []
        names = {c.get("name") for c in checks if isinstance(c, dict)}
        # soft requirements: if your schema uses different names, adjust here
        for required in {"brand_name", "abv", "net_contents", "government_warning"}:
            assert required in names, f"Missing check '{required}' in {row}"
