#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

PYTHON_CMD="${PYTHON_CMD:-python}"
PNPM_CMD="${PNPM_CMD:-pnpm}"

BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'ERROR: command not found: %s\n' "$1" >&2
    exit 1
  fi
}

activate_backend_venv() {
  if [ -f "$BACKEND_DIR/.venv/Scripts/activate" ]; then
    # Git Bash / MSYS on Windows
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.venv/Scripts/activate"
  elif [ -f "$BACKEND_DIR/.venv/bin/activate" ]; then
    # Linux / macOS / WSL
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.venv/bin/activate"
  else
    printf 'ERROR: backend virtualenv activation script not found.\n' >&2
    exit 1
  fi
}

cleanup() {
  log "Stopping PathFy-Uni services..."
  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

start_backend() {
  (
    cd "$BACKEND_DIR"

    if [ ! -d ".venv" ]; then
      log "Creating backend virtualenv..."
      "$PYTHON_CMD" -m venv .venv
    fi

    activate_backend_venv

    log "Installing backend dependencies..."
    python -m pip install -r requirements.txt

    log "Applying database migrations..."
    python -m alembic upgrade head

    log "Starting Flask backend: http://127.0.0.1:5000"
    exec python run.py
  ) &
  BACKEND_PID=$!
}

start_frontend() {
  (
    cd "$FRONTEND_DIR"

    log "Installing frontend dependencies..."
    "$PNPM_CMD" install

    log "Starting Nuxt frontend: http://127.0.0.1:4321"
    exec "$PNPM_CMD" dev
  ) &
  FRONTEND_PID=$!
}

wait_for_services() {
  while true; do
    if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
      wait "$BACKEND_PID"
      exit $?
    fi

    if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
      wait "$FRONTEND_PID"
      exit $?
    fi

    sleep 1
  done
}

main() {
  require_command "$PYTHON_CMD"
  require_command "$PNPM_CMD"

  trap cleanup INT TERM EXIT

  start_backend
  start_frontend

  log "Both services are starting. Press Ctrl+C to stop."
  wait_for_services
}

main "$@"
