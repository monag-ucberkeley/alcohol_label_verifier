#!/usr/bin/env bash
set -euo pipefail
export VITE_PROXY_TARGET=http://localhost:8000
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
