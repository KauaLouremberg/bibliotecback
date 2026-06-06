#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERRO: DATABASE_URL não está definida no Render."
  echo "Dashboard → acervo-api → Environment → adicione a URI do Supabase."
  exit 1
fi

# Erro comum: usuário postgres.PROJECT_REF só funciona na porta 6543 (Transaction pooler).
if [[ "${DATABASE_URL}" == *"postgres.lcwqriuenyubloalczsu"* ]] && [[ "${DATABASE_URL}" == *":5432"* ]]; then
  echo "ERRO: DATABASE_URL inválida para Session pooler (5432)."
  echo "Use usuário 'postgres' (não 'postgres.lcwqriuenyubloalczsu') na porta 5432."
  echo "Correto: postgresql://postgres:[SENHA]@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require"
  echo "Ou Transaction pooler: porta 6543 com usuário postgres.lcwqriuenyubloalczsu"
  exit 1
fi

python manage.py migrate --noinput
exec uvicorn config.asgi:application --host 0.0.0.0 --port "${PORT:-8000}"
