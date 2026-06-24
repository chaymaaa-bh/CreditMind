#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.pids"
LOG_DIR="$ROOT/logs"

mkdir -p "$LOG_DIR"

# ── Helpers ────────────────────────────────────────────────────────────────────
kill_port() {
  local port=$1
  local pid
  pid=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "  Port $port occupé (PID $pid) — arrêt..."
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi
}

wait_ready() {
  local url=$1 label=$2 timeout=${3:-30}
  local i=0
  printf "  Attente %s" "$label"
  while ! curl -sf --max-time 2 "$url" >/dev/null 2>&1; do
    printf "."
    sleep 1
    i=$((i+1))
    if [ $i -ge $timeout ]; then
      echo " TIMEOUT"
      return 1
    fi
  done
  echo " OK"
}

# ── Nettoyage des anciens process ─────────────────────────────────────────────
echo "==> Nettoyage..."
kill_port 8000
kill_port 3000

# ── Backend FastAPI ────────────────────────────────────────────────────────────
echo "==> Démarrage backend (port 8000)..."
cd "$ROOT"
nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$PID_FILE.backend"

wait_ready "http://localhost:8000/health" "backend" 30 || {
  echo "ERREUR: Backend n'a pas démarré. Voir $LOG_DIR/backend.log"
  exit 1
}

# ── Frontend Next.js (production) ─────────────────────────────────────────────
echo "==> Build frontend (production)..."
cd "$ROOT/frontend"
npm run build > "$LOG_DIR/frontend-build.log" 2>&1 || {
  echo "ERREUR: Build échoué. Voir $LOG_DIR/frontend-build.log"
  exit 1
}
echo "  Build OK"

echo "==> Démarrage frontend (port 3000)..."
nohup npm run start -- --port 3000 \
  > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$PID_FILE.frontend"
cd "$ROOT"

wait_ready "http://localhost:3000" "frontend" 30 || {
  echo "ERREUR: Frontend n'a pas démarré. Voir $LOG_DIR/frontend.log"
  exit 1
}

# ── Résumé ─────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         CreditMind — Serveurs actifs         ║"
echo "╠══════════════════════════════════════════════╣"
printf "║  Backend  PID %-6s  http://localhost:8000  ║\n" "$BACKEND_PID"
printf "║  Frontend PID %-6s  http://localhost:3000  ║\n" "$FRONTEND_PID"
echo "╠══════════════════════════════════════════════╣"
echo "║  Logs : ./logs/backend.log                   ║"
echo "║         ./logs/frontend.log                  ║"
echo "║  Arrêt : ./stop.sh                           ║"
echo "╚══════════════════════════════════════════════╝"
