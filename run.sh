#!/bin/sh

set -o errexit
set -o nounset


export ENVIRONMENT="${ENVIRONMENT:-production}"

if [ "$ENVIRONMENT" = "production" ]; then
  echo ">>> Running production startup tasks"
  uv run python manage.py compilemessages --settings="$DJANGO_SETTINGS_MODULE" --ignore ".*" --ignore "htmlcov" --ignore "media" --ignore "node_modules" --ignore "staticfiles"
  uv run python manage.py migrate --settings="$DJANGO_SETTINGS_MODULE" --noinput
  uv run python manage.py collectstatic --no-input --settings="$DJANGO_SETTINGS_MODULE" --noinput --clear

  # Start Gunicorn
  exec uv run gunicorn ${DJANGO_WSGI_MODULE:-config.wsgi}:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --log-level ${GUNICORN_LOG_LEVEL:-info} \
    --access-logfile - \
    --error-logfile -
elif [ "${START_API:-}" = "False" ] && [ "$ENVIRONMENT" = "devcontainer" ]; then
  echo ">>> Starting in development mode..."
  uv sync --locked --no-install-project --all-groups
  exec tail -f /dev/null
else
  echo ">>> Starting API server..."
  uv sync --locked --no-install-project --all-groups
  uv run python manage.py compilemessages --settings="$DJANGO_SETTINGS_MODULE" --ignore ".*" --ignore "htmlcov" --ignore "media" --ignore "node_modules" --ignore "staticfiles"
  uv run python manage.py migrate --settings="$DJANGO_SETTINGS_MODULE" --noinput
  uv run python manage.py collectstatic --no-input --settings="$DJANGO_SETTINGS_MODULE" --noinput --clear
  uv run python manage.py runserver --settings="$DJANGO_SETTINGS_MODULE" 0.0.0.0:8000
fi
