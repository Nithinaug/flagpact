#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

(cd ui && npm ci && npm run build)
rm -rf src/flagpact/webui build dist
mkdir -p src/flagpact/webui
cp -r ui/dist/. src/flagpact/webui/

PY="${PYTHON:-python3}"
"$PY" -m pip install --quiet build twine
"$PY" -m build
"$PY" -m twine check dist/*
ls -la dist
