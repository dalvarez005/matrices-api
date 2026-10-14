#!/usr/bin/env bash
# Copia el código a la Orange Pi, construye la imagen allí (ARM nativo, sin
# emulación) y reinicia la API.
#
#   deploy/deploy.sh [usuario@servidor]
#
# En el servidor usa ~/matrices-api (con .env, que no se toca).
set -euo pipefail

TARGET="${1:-orangepi@192.168.1.77}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Copiando código a $TARGET:~/matrices-api"
rsync -az --delete \
  --exclude .git --exclude .venv --exclude .env --exclude '*.db' \
  --exclude __pycache__ --exclude .pytest_cache --exclude data \
  "$ROOT/" "$TARGET:matrices-api/"

echo "==> Construyendo y reiniciando"
ssh "$TARGET" 'cd ~/matrices-api && test -f .env || { echo "Falta ~/matrices-api/.env (copia .env.example)"; exit 1; }
  docker compose up -d --build && docker image prune -f >/dev/null && docker compose ps'
