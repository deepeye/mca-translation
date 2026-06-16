#!/bin/bash
set -e

echo "Starting infrastructure (PostgreSQL + Redis)..."
docker compose -f docker-compose.dev.yml up -d

echo "Waiting for PostgreSQL..."
sleep 3

echo "Running database migrations..."
cd backend && alembic upgrade head && cd ..

echo ""
echo "Development environment ready!"
echo "  Backend:  cd backend && uvicorn app.main:app --reload"
echo "  Celery:   cd backend && celery -A app.celery_app worker -l info"
echo "  Frontend: cd frontend && pnpm dev"
