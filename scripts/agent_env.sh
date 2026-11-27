#!/usr/bin/env bash
# Source this, do not run it: source scripts/agent_env.sh
# Sets up the Flagsmith CLI and flagpact for an agent session against the local demo.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
source "$ROOT_DIR/.flagpact-keys.env"
set +a
FS_ROOT="${FLAGSMITH_API_URL%/api/v1}"
FS_HOST="$(printf '%s' "${FS_ROOT#*://}" | sed 's/-/--/g; s/[.:]/_/g')"
export "FLAGSMITH_API_KEY_${FS_HOST}=${FLAGSMITH_MASTER_API_KEY}"
unset FLAGSMITH_API_KEY FLAGSMITH_ENVIRONMENT_KEY FLAGSMITH_MASTER_API_KEY
export FLAGSMITH_ORGANISATION="$FLAGSMITH_ORG_ID" FLAGSMITH_PROJECT="$FLAGSMITH_PROJECT_ID" FLAGSMITH_ENVIRONMENT="$FLAGSMITH_ENV_CLIENT_KEY"
export FLAGSMITH_CLI_API_URL="$FS_ROOT"
export PATH="$ROOT_DIR/.venv/bin:$PATH"
