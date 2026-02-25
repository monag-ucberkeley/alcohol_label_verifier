import json
import argparse
from pathlib import Path

import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Path to cola_paired_dataset directory")
    ap.add_argument("--api", default="http://localhost:8000", help="Backend base URL")
    ap.add_argument("--use_application_json", action="store_true", help="Call /api/verify-with-application-json using application.json uploads")
    ap.add_argument("--out", default="dataset_results.json", help="Output JSON")
    args = ap.parse_args()

    ds = Path(args.dataset)
    index = json.loads((ds / "index.json").read_text(encoding="utf-8"))

    results = []
    for row in index:
        label_path = ds / row["label_path"]
        app_path = ds / row["application_json_path"]
        app = json.loads(app_path.read_text(encoding="utf-8"))

        files = {"file": ("label.png", label_path.read_bytes(), "image/png")}
        data = {
            "brand_name": app["brand_name"],
            "abv": app.get("abv", ""),
            "net_contents": app.get("net_contents", ""),
            "require_gov_warning": "true" if app.get("government_warning_required", True) else "false",
        }

        r = requests.post(f"{args.api}/api/verify", files=files, data=data, timeout=60)
        r.raise_for_status()
        payload = r.json()

        results.append({
            "subset": row.get("subset"),
            "sample": row.get("sample"),
            "label": str(row["label_path"]),
            "expected": {
                "brand_name": app["brand_name"],
                "abv": app.get("abv"),
                "net_contents": app.get("net_contents"),
                "government_warning_required": app.get("government_warning_required", True),
            },
            "result": payload,
        })

        print(f"{row.get('subset')}/{row.get('sample')}: overall={payload.get('overall_status', payload.get('overall', 'UNKNOWN'))}")

    out_path = Path(args.out)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote: {out_path.resolve()}")


if __name__ == "__main__":
    main()
