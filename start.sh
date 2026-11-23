#!/usr/bin/env bash
set -e

export USE_OFFLINE_EMBED="${USE_OFFLINE_EMBED:-1}"
PUBLIC_PORT="${PORT:-7860}"

if [ "${DEPLOY_MODE:-fullstack}" = "api" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PUBLIC_PORT}"
fi

# Start FastAPI backend internally on port 8000 (exposing /health, /ask, /agent, /feedback)
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

for i in $(seq 1 30); do
  if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

export GSTSARAL_API_URL="http://127.0.0.1:8000"
exec streamlit run ui/app.py --server.address 0.0.0.0 --server.port "${PUBLIC_PORT}" --server.headless true
