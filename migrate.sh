#!/bin/sh

set -o errexit
set -o nounset

# One-shot deploy step: static files and translation catalogs are built into the image.
echo ">>> Applying migrations"
exec uv run --no-sync python manage.py migrate --noinput
