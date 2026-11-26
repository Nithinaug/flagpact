#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -e .env ]; then
  echo "stack/.env already exists, leaving it alone."
  exit 0
fi
umask 077
rand() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
cat > .env <<ENVEOF
POSTGRES_PASSWORD=$(rand 24)
DJANGO_SECRET_KEY=$(rand 48)
FLAGPACT_ADMIN_EMAIL=admin@example.com
FLAGPACT_ADMIN_PASSWORD=$(rand 18)
PREVENT_SIGNUP=false
FLAGSMITH_PORT=${FLAGSMITH_PORT:-8000}
ENVEOF
chmod 600 .env
echo "Wrote stack/.env with random secrets. Do not commit it."
