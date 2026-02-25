# AI Alcohol Label Verification Prototype

## Key features aligned to stakeholder notes

- **Checklist-style UI** (large text/buttons) designed for low-tech users.
- **Batch ZIP uploads** for peak-season importer dumps.
- **Strict government warning validation** (header format + required clauses).
- **Image quality rating** (GOOD/FAIR/POOR) with guidance to request a clearer photo.
- **No cloud calls** (runs offline; firewall-friendly).

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
