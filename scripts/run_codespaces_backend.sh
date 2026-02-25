#!/usr/bin/env bash
set -euo pipefail
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
