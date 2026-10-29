#!/bin/sh

set -o errexit
set -o nounset

echo ">>> Running deploy steps: compilemessages, migrate, collectstatic"
uv run --no-sync python manage.py compilemessages --ignore ".*" --ignore "htmlcov" --ignore "media" --ignore "node_modules" --ignore "staticfiles"
uv run --no-sync python manage.py migrate --noinput
uv run --no-sync python manage.py collectstatic --noinput --clear
