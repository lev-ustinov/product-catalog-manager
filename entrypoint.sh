#!/bin/sh
# entrypoint.sh — runs inside the app container before uvicorn starts.
#
# Works for both local Docker and Render:
#   - locally: PORT defaults to 8000
#   - on Render: PORT is set to 10000 by the platform automatically

set -e

echo "==> Running Alembic migrations..."
alembic -c /alembic.ini upgrade head

echo "==> Seeding demo data (skipped if data already exists)..."
python seed_demo_data.py

echo "==> Starting application on port ${PORT:-8000}..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
