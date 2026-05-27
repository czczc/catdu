#!/usr/bin/env bash
# Manage the local dev servers: the tools backend (FastAPI) and the web
# frontend (Vite). Each subcommand acts on both by default, or on a single
# service if you pass `tools` or `web`.
#
# Usage:
#   scripts/servers.sh start [tools|web]
#   scripts/servers.sh stop  [tools|web]
#   scripts/servers.sh restart [tools|web]
#   scripts/servers.sh status [tools|web]
#   scripts/servers.sh logs <tools|web> [-f]
#
# PID + log files live under tools/.run/ (gitignored).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/tools/.run"
mkdir -p "$RUN_DIR"

TOOLS_PORT="${TOOLS_PORT:-5180}"
WEB_PORT="${WEB_PORT:-5173}"

# Service registry: name → (port, health-path, start-cwd, start-cmd)
svc_port()        { case "$1" in tools) echo "$TOOLS_PORT" ;; web) echo "$WEB_PORT" ;; esac; }
svc_health_path() { case "$1" in tools) echo "/api/visibility" ;; web) echo "/catdu/" ;; esac; }
svc_health_host() { case "$1" in tools) echo "127.0.0.1" ;; web) echo "localhost" ;; esac; }
svc_health_url()  { echo "http://$(svc_health_host "$1"):$(svc_port "$1")$(svc_health_path "$1")"; }
svc_cwd()         { case "$1" in tools) echo "$ROOT" ;; web) echo "$ROOT/web" ;; esac; }
svc_cmd()         {
  case "$1" in
    tools) echo "uv run python tools/server.py" ;;
    web)   echo "npm run dev -- --port $WEB_PORT --strictPort" ;;
  esac
}
svc_pid_file()    { echo "$RUN_DIR/$1.pid"; }
svc_log_file()    { echo "$RUN_DIR/$1.log"; }
svc_url()         { echo "http://127.0.0.1:$(svc_port "$1")"; }

is_running() {
  local svc="$1" pid_file pid
  pid_file="$(svc_pid_file "$svc")"
  [[ -f "$pid_file" ]] || return 1
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

port_holder_pid() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -n 1
}

start_one() {
  local svc="$1"
  local pid_file log_file url port external
  pid_file="$(svc_pid_file "$svc")"
  log_file="$(svc_log_file "$svc")"
  url="$(svc_url "$svc")"
  port="$(svc_port "$svc")"

  if is_running "$svc"; then
    echo "[$svc] already running (pid $(cat "$pid_file")) at $url"
    return 0
  fi
  rm -f "$pid_file"

  external="$(port_holder_pid "$port")"
  if [[ -n "$external" ]]; then
    echo "[$svc] port $port already in use by pid $external (not started by this script)." >&2
    echo "       Stop that process first, or set ${svc^^}_PORT to a free port." >&2
    return 1
  fi
  echo "[$svc] starting on $url …"
  ( cd "$(svc_cwd "$svc")" && nohup $(svc_cmd "$svc") >>"$log_file" 2>&1 & echo $! >"$pid_file" )
  local pid
  pid="$(cat "$pid_file")"
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if kill -0 "$pid" 2>/dev/null && curl -sf "$(svc_health_url "$svc")" >/dev/null 2>&1; then
      echo "[$svc] started (pid $pid). Logs: $log_file"
      return 0
    fi
    sleep 0.5
  done
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file"
    echo "[$svc] failed to start. Tail of log:" >&2
    tail -n 30 "$log_file" >&2 || true
    return 1
  fi
  echo "[$svc] started (pid $pid) but readiness probe didn't succeed. Check logs: $log_file"
}

stop_one() {
  local svc="$1"
  local pid_file pid
  pid_file="$(svc_pid_file "$svc")"
  if ! is_running "$svc"; then
    echo "[$svc] not running."
    rm -f "$pid_file"
    return 0
  fi
  pid="$(cat "$pid_file")"
  echo "[$svc] stopping pid $pid …"
  # Kill the whole process group so vite's child node process dies too.
  local pgid
  pgid="$(ps -o pgid= "$pid" 2>/dev/null | tr -d ' ' || true)"
  if [[ -n "$pgid" ]]; then
    kill -- "-$pgid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  else
    kill "$pid" 2>/dev/null || true
  fi
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$pid" 2>/dev/null || { rm -f "$pid_file"; echo "[$svc] stopped."; return 0; }
    sleep 0.3
  done
  echo "[$svc] still alive; sending SIGKILL."
  if [[ -n "$pgid" ]]; then
    kill -9 -- "-$pgid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
  else
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
  echo "[$svc] killed."
}

status_one() {
  local svc="$1"
  local url
  url="$(svc_url "$svc")"
  if is_running "$svc"; then
    local pid
    pid="$(cat "$(svc_pid_file "$svc")")"
    if curl -sf "$(svc_health_url "$svc")" >/dev/null 2>&1; then
      echo "[$svc] running (pid $pid) at $url  · health: OK"
    else
      echo "[$svc] running (pid $pid) at $url  · health: NOT RESPONDING"
    fi
  else
    echo "[$svc] not running."
  fi
}

logs_one() {
  local svc="$1" follow="${2:-}"
  local log_file
  log_file="$(svc_log_file "$svc")"
  if [[ ! -f "$log_file" ]]; then
    echo "[$svc] no log file yet at $log_file"
    return 0
  fi
  if [[ "$follow" == "-f" ]]; then
    tail -n 50 -f "$log_file"
  else
    tail -n 200 "$log_file"
  fi
}

services_for() {
  case "${1:-all}" in
    all|"") echo "tools web" ;;
    tools)  echo "tools" ;;
    web)    echo "web" ;;
    *)
      echo "unknown service: $1 (use tools|web|all)" >&2
      exit 2
      ;;
  esac
}

case "${1:-}" in
  start)
    for svc in $(services_for "${2:-all}"); do start_one "$svc"; done
    ;;
  stop)
    for svc in $(services_for "${2:-all}"); do stop_one "$svc"; done
    ;;
  restart)
    for svc in $(services_for "${2:-all}"); do stop_one "$svc"; done
    for svc in $(services_for "${2:-all}"); do start_one "$svc"; done
    ;;
  status)
    for svc in $(services_for "${2:-all}"); do status_one "$svc"; done
    ;;
  logs)
    svc="${2:-}"
    if [[ -z "$svc" || "$svc" == "all" ]]; then
      echo "logs needs a service: tools or web" >&2
      exit 2
    fi
    services_for "$svc" >/dev/null
    logs_one "$svc" "${3:-}"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status} [tools|web]" >&2
    echo "       $0 logs <tools|web> [-f]" >&2
    exit 2
    ;;
esac
