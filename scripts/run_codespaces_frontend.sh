#!/usr/bin/env bash
set -euo pipefail
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
