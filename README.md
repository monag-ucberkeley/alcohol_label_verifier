# AI Alcohol Label Verification Prototype

## Run in GitHub Codespaces (Recommended for interviewers)

Codespaces environments can have Docker client/daemon version mismatches.  
This repo is configured to run **without Docker in Codespaces** for reliability.

1. Open the GitHub repo
2. Click **Code → Codespaces → Create codespace**
3. Open two terminals:

**Terminal A (backend)**
```bash
./scripts/run_codespaces_backend.sh
```

**Terminal B (frontend)**
```bash
./scripts/run_codespaces_frontend.sh
```

Then open:
- Frontend: forwarded port **5173**
- Backend: forwarded port **8000** (API docs at `/docs`)

---

---

## Run Locally

Prerequisite:
Docker Desktop installed

Run:

```
docker compose up --build
```

Open:

Frontend:
http://localhost:5173

Backend:
http://localhost:8000/docs


---

## Example Test Data

Located in:

```
sample_data/nutrition_style_labels.zip
```

Example values:

Brand:
STONE'S THROW

ABV:
12.5%

Net contents:
750 mL

Government Warning:
Checked


---

## Run Tests

```
cd backend
pytest
```

---

## Features

- OCR label extraction
- Brand matching
- ABV verification
- Net contents verification
- Government warning detection
- Batch processing
- <5 second processing target
- Docker deployment
- Codespaces support
---

## Codespaces troubleshooting

If Codespaces doesn’t auto-start services, run:

```bash
docker compose up --build
```

If you previously created a Codespace before adding/updating the devcontainer, choose:
**Command Palette → Codespaces: Rebuild Container**.

## If you see HTTP 502 on the forwarded port (Codespaces)
502 usually means nothing is listening on that port yet, or the container crashed.

Run:
```bash
docker compose ps
docker compose logs --tail=200 frontend
docker compose logs --tail=200 backend
```

To restart:
```bash
docker compose down
docker compose up --build
```

## Dataset evaluation (paired COLA apps + labels)

This repo includes zipped datasets under `sample_data/`:
- `sample_data/cola_paired_dataset.zip` (paired label.png + application.json + application.png)
- `sample_data/label_dataset.zip` (regular + distorted labels only)

To evaluate the paired dataset:

1) Unzip it somewhere (example):
```bash
unzip -q sample_data/cola_paired_dataset.zip -d sample_data/
```

2) Start the backend and frontend (Codespaces) or Docker locally.

3) Run the evaluator script:
```bash
python scripts/eval_cola_dataset.py --dataset sample_data/cola_paired_dataset --api http://localhost:8000 --out dataset_results.json
```

4) (Optional) Run tests (will auto-skip if dataset isn't present):
```bash
cd backend
pytest -q
```


## Uploading a COLA application separately (JSON)

In **Single** mode, you can optionally upload a `application.json` file (e.g., from `sample_data/cola_paired_dataset.zip`).
When provided, the UI will:
- Auto-fill the application fields
- Verify the label against the uploaded application JSON via `/api/verify-with-application-json`


## Batch verification (paired ZIP)

Batch mode expects a ZIP where each folder contains `label.png` (or .jpg/.jpeg) and `application.json`.

Example:
```
regular/sample_01/label.png
regular/sample_01/application.json
```

API: `POST /api/verify-batch-pairs` with form field `zip_file`.
