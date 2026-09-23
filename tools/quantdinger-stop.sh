#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

cd "$ROOT_DIR"

COMPOSE=(
  docker compose
  --project-name quantdinger
  --file "$ROOT_DIR/docker-compose.yml"
  --file "$ROOT_DIR/docker-compose.build.yml"
)

SERVICES=(
  frontend
  backend
  celery-worker
  celery-beat
  scheduler-worker
  trading-worker
  migration
  postgres
  redis
  redis-jobs
)

if ! docker info >/dev/null 2>&1; then
  echo "Docker motoru çalışmıyor; durdurulacak QuantDinger container'ı yok."
  exit 0
fi

"${COMPOSE[@]}" stop "${SERVICES[@]}"

BRIDGE_LABEL="com.quantdinger.codex-copilot-bridge"
BRIDGE_UID="$(id -u)"
launchctl bootout "gui/$BRIDGE_UID/$BRIDGE_LABEL" >/dev/null 2>&1 || true

echo "QuantDinger kapatıldı. Veritabanı volume'ları korundu."
