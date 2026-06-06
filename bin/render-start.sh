#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERRO: DATABASE_URL não está definida no Render."
  echo "Dashboard → acervo-api → Environment → adicione a URI do Supabase (Session pooler, sslmode=require)."
  exit 1
fi

python manage.py migrate --noinput
exec uvicorn config.asgi:application --host 0.0.0.0 --port "${PORT:-8000}"
