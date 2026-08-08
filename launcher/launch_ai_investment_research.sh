#!/usr/bin/env bash
set -u

DEFAULT_PROJECT_DIR="/Users/hankmacmini/Documents/Projects/AI-Investment-Research"
PROJECT_DIR="${AI_INVESTMENT_RESEARCH_DIR:-$DEFAULT_PROJECT_DIR}"
APP_PATH="$PROJECT_DIR/app.py"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
PORT="8501"
URL="http://localhost:$PORT"
HEALTH_URL="$URL/_stcore/health"
LOG_DIR="$HOME/Library/Logs/AI-Investment-Research"
LOG_FILE="$LOG_DIR/launcher.log"
READY_TIMEOUT_SECONDS=30

mkdir -p "$LOG_DIR" 2>/dev/null || true

log_message() {
  local message="$1"
  if [ -d "$LOG_DIR" ]; then
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$message" >>"$LOG_FILE" 2>/dev/null || true
  fi
}

fail() {
  local message="$1"
  log_message "ERROR: $message"
  printf '%s\n' "$message" >&2
  exit 1
}

health_check() {
  /usr/bin/curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1
}

open_dashboard() {
  /usr/bin/open "$URL" >/dev/null 2>&1 || fail "無法自動開啟瀏覽器。請手動開啟 $URL。"
}

port_listener_pids() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true
  fi
}

command_for_pid() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null || true
}

project_streamlit_is_listening() {
  local pid command
  for pid in $(port_listener_pids); do
    command="$(command_for_pid "$pid")"
    case "$command" in
      *"$APP_PATH"*) return 0 ;;
    esac
  done
  return 1
}

port_has_listener() {
  [ -n "$(port_listener_pids)" ]
}

wait_until_ready() {
  local attempts=$((READY_TIMEOUT_SECONDS * 2))
  local i=0
  while [ "$i" -lt "$attempts" ]; do
    if health_check; then
      return 0
    fi
    sleep 0.5
    i=$((i + 1))
  done
  return 1
}

[ -d "$PROJECT_DIR" ] || fail "專案目錄不存在：$PROJECT_DIR"
[ -d "$PROJECT_DIR/.venv" ] || fail ".venv 不存在，AI Investment Research 無法啟動。"
[ -x "$PYTHON_BIN" ] || fail ".venv Python 不存在或不可執行：$PYTHON_BIN"
[ -f "$APP_PATH" ] || fail "app.py 不存在：$APP_PATH"

"$PYTHON_BIN" -c "import streamlit" >/dev/null 2>&1 || fail "Streamlit import unavailable，請確認專案 .venv 已安裝 requirements。"

if health_check; then
  log_message "Existing Streamlit server detected at $HEALTH_URL"
  open_dashboard
  exit 0
fi

if port_has_listener; then
  if project_streamlit_is_listening; then
    log_message "Project Streamlit process is listening but health is not ready yet."
    if wait_until_ready; then
      open_dashboard
      exit 0
    fi
    fail "Streamlit 已啟動但未在 $READY_TIMEOUT_SECONDS 秒內 ready。請查看 log：$LOG_FILE"
  fi
  fail "Port 8501 已被其他程式使用，AI Investment Research 無法啟動。"
fi

log_message "Starting AI Investment Research Streamlit server."
(
  cd "$PROJECT_DIR" || exit 1
  nohup "$PYTHON_BIN" -m streamlit run "$APP_PATH" \
    --server.port "$PORT" \
    --server.headless true \
    >>"$LOG_FILE" 2>&1 &
)

if wait_until_ready; then
  log_message "Streamlit server is ready at $URL"
  open_dashboard
  exit 0
fi

fail "Streamlit failed to become ready within $READY_TIMEOUT_SECONDS seconds. 請查看 log：$LOG_FILE"
