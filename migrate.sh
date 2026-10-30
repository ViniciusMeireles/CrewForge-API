#!/bin/sh

set -o errexit
set -o nounset

echo ">>> Applying migrations"
exec uv run --no-sync python manage.py migrate --noinput
