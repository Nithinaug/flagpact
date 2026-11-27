#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
source .flagpact-keys.env
set +a

ROOT="${FLAGSMITH_API_URL%/api/v1}"
HOST_VAR="$(printf '%s' "${ROOT#*://}" | sed 's/-/--/g; s/[.:]/_/g')"
export "FLAGSMITH_API_KEY_${HOST_VAR}=${FLAGSMITH_MASTER_API_KEY}"
unset FLAGSMITH_API_KEY FLAGSMITH_ENVIRONMENT_KEY
export FLAGSMITH_ORGANISATION="$FLAGSMITH_ORG_ID" FLAGSMITH_PROJECT="$FLAGSMITH_PROJECT_ID" FLAGSMITH_ENVIRONMENT="$FLAGSMITH_ENV_CLIENT_KEY"

FLAG="${FLAG:-home_banner}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
fs() { flagsmith --api-url "$ROOT" --no-input --yes "$@"; }
step() { printf '\n== %s\n' "$1"; }

SEGMENT="flagpact/${FLAG}/3.0.0"

step "0. clean up leftovers and reset the demo value"
fs flag delete "$FLAG" --segment "$SEGMENT" >/dev/null 2>&1 || true
fs segment delete "$SEGMENT" >/dev/null 2>&1 || true
.venv/bin/python scripts/seed.py .flagpact-keys.env >/dev/null

step "1. read the live value"
fs flag get "$FLAG" --jq .value > "$WORK/previous.txt"
.venv/bin/python - "$WORK/previous.txt" <<'PY'
import json, sys
text = open(sys.argv[1]).read().strip()
if text.startswith('"'):
    text = json.loads(text)
open(sys.argv[1], "w").write(text)
PY
cat "$WORK/previous.txt"

step "2. propose a breaking value"
cat > "$WORK/new.json" <<'JSON'
{"heading": "Sale on now", "subheading": "Up to 40% off", "cta": {"label": "Shop the sale"}}
JSON
cat "$WORK/new.json"

step "3. flagpact check (exit 1 is expected)"
set +e
.venv/bin/python -m flagpact check --value "$WORK/new.json" --config flagpact.json --json > "$WORK/report.json"
code=$?
set -e
echo "exit code: $code"
.venv/bin/python - "$WORK/report.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
print("breaks:", r["breaks"], "at_risk:", r["at_risk"])
print("fix segment:", r["fix"]["segment"], "keep below", r["fix"]["keep_below"])
PY
[ "$code" = "1" ] || { echo "expected the check to find a break"; exit 1; }

step "4. apply the fix with the Flagsmith CLI"
.venv/bin/python - "$WORK/report.json" "$WORK" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
work = sys.argv[2]
json.dump(r["fix"]["rule"], open(work + "/rules.json", "w"))
open(work + "/keep.txt", "w").write(json.dumps(r["fix"]["keep_value"]))
open(work + "/segment.txt", "w").write(r["fix"]["segment"])
PY
SEG="$(cat "$WORK/segment.txt")"
fs segment create "$SEG" --rules "@$WORK/rules.json"
fs flag update "$FLAG" --segment "$SEG" --type string --value "$(cat "$WORK/keep.txt")" --enable --priority 0

test "$(fs flag get "$FLAG" --jq .segment_overrides)" = "1" || { echo "the fix was not applied, stopping before publish"; exit 1; }

step "5. publish the new value"
fs flag update "$FLAG" --type string --value "$(cat "$WORK/new.json")"

step "6. verify"
set +e
.venv/bin/python -m flagpact check --value "$WORK/new.json" --config flagpact.json --json > "$WORK/after.json"
echo "flagpact check exit code after the fix: $?"
set -e
fs flag get "$FLAG" --jq '{enabled, segment_overrides, value}'
fs evaluate "$FLAG" --trait app_version=1.0.0 --jq . || echo "(evaluate needs the SDK API, skipped)"

step "7. roll back"
fs flag update "$FLAG" --type string --value "$(cat "$WORK/previous.txt")"
fs flag delete "$FLAG" --segment "$SEG"
fs segment delete "$SEG"

step "8. restore the demo value"
.venv/bin/python scripts/seed.py .flagpact-keys.env >/dev/null
fs flag get "$FLAG" --jq '{segment_overrides, value}'
echo
echo "done"
