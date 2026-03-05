#!/usr/bin/env bash

# Exit on error
set -o errexit

echo "Running database migrations..."
alembic upgrade head

echo "Starting Celery worker in the background..."
celery -A app.celery_app.celery_app worker --loglevel=info --concurrency=1 &

echo "Starting FastAPI web server..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
