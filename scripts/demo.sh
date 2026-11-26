#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

bash stack/gen-env.sh
COMPOSE="docker compose -f stack/docker-compose.yml --env-file stack/.env"
$COMPOSE up -d
python3 stack/bootstrap.py

if grep -q "^PREVENT_SIGNUP=false" stack/.env; then
  sed -i 's/^PREVENT_SIGNUP=false/PREVENT_SIGNUP=true/' stack/.env
  $COMPOSE up -d
fi

if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv .venv
    uv pip install -e . --python .venv/bin/python
  else
    python3 -m venv .venv
    .venv/bin/pip install -e .
  fi
fi

if [ ! -d ui/dist ]; then
  (cd ui && npm install && npm run build)
fi

PORT="${FLAGPACT_PORT:-8765}"
echo "flagpact is starting on http://127.0.0.1:${PORT} (add /demo for the demo controls)"
FLAGPACT_PORT="$PORT" exec .venv/bin/python -m flagpact.server .flagpact-keys.env flagpact.json
