#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.pids"

stop_pid() {
  local label=$1 file="$PID_FILE.$2"
  if [ -f "$file" ]; then
    local pid
    pid=$(cat "$file")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" && echo "  $label (PID $pid) arrêté"
    else
      echo "  $label (PID $pid) déjà arrêté"
    fi
    rm -f "$file"
  else
    echo "  $label — pas de PID enregistré"
  fi
}

echo "==> Arrêt CreditMind..."
stop_pid "Backend " backend
stop_pid "Frontend" frontend

# Filet de sécurité sur les ports
sleep 1
for port in 8000 3000; do
  pid=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  [ -n "$pid" ] && kill "$pid" 2>/dev/null && echo "  Port $port libéré (PID $pid)"
done

echo "==> Arrêt terminé."
