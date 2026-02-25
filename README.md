
# AI Alcohol Label Verification Prototype

## Fastest Way (Recommended)
### Run in GitHub Codespaces

1. Open the GitHub repo
2. Click **Code**
3. Click **Codespaces**
4. Click **Create Codespace**

The system will automatically start.

Frontend:
http://localhost:5173

Backend:
http://localhost:8000/docs


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

