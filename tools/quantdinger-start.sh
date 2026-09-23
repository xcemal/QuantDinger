#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

cd "$ROOT_DIR"

if ! docker info >/dev/null 2>&1; then
  if command -v colima >/dev/null 2>&1; then
    echo "Docker motoru çalışmıyor; Colima başlatılıyor..."
    colima start
  fi
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker motoruna bağlanılamadı. Docker Desktop veya Colima'yı başlatıp tekrar deneyin." >&2
  exit 1
fi

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
)

FRONTEND_IMAGE="$("${COMPOSE[@]}" config --images | awk '/quantdinger-frontend/{print; exit}')"
NEEDS_BUILD=0

if ! docker image inspect quantdinger-backend:local >/dev/null 2>&1; then
  NEEDS_BUILD=1
fi

if [[ -z "$FRONTEND_IMAGE" ]] || ! docker image inspect "$FRONTEND_IMAGE" >/dev/null 2>&1; then
  NEEDS_BUILD=1
fi

if [[ "$NEEDS_BUILD" -eq 1 ]]; then
  echo "Yerel image eksik; ilk kurulum build'i başlatılıyor..."
  "${COMPOSE[@]}" up -d --build "${SERVICES[@]}"
else
  echo "Yerel image'lar bulundu; registry'ye bağlanmadan açılıyor..."
  "${COMPOSE[@]}" up -d "${SERVICES[@]}"
fi

wait_for_url() {
  local name="$1"
  local url="$2"
  local attempt

  for attempt in $(seq 1 60); do
    if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
      echo "$name hazır: $url"
      return 0
    fi
    sleep 2
  done

  echo "$name sağlık kontrolünden geçemedi: $url" >&2
  "${COMPOSE[@]}" ps
  return 1
}

wait_for_url "Backend" "http://127.0.0.1:15000/api/health"
wait_for_url "Frontend" "http://127.0.0.1:18080/health"

BRIDGE_LABEL="com.quantdinger.codex-copilot-bridge"
BRIDGE_PLIST="$ROOT_DIR/tools/com.quantdinger.codex-copilot-bridge.plist"
BRIDGE_UID="$(id -u)"

launchctl bootout "gui/$BRIDGE_UID/$BRIDGE_LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$BRIDGE_UID" "$BRIDGE_PLIST"

for attempt in $(seq 1 30); do
  if curl --noproxy '*' --fail --silent --show-error "http://127.0.0.1:18765/healthz" >/dev/null 2>&1; then
    echo "Codex Copilot bridge hazır: http://127.0.0.1:18765"
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "Codex Copilot bridge sağlık kontrolünden geçemedi." >&2
    launchctl print "gui/$BRIDGE_UID/$BRIDGE_LABEL" >&2 || true
    exit 1
  fi
  sleep 1
done

echo "QuantDinger çalışıyor: http://127.0.0.1:18080"
