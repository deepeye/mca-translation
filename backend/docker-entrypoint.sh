#!/bin/sh
set -e

# 仅当以默认 backend 方式启动（无额外命令参数）时才执行迁移
# Only run migrations when starting backend in default mode (no command override)
if [ "$#" -eq 0 ] && [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
else
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
