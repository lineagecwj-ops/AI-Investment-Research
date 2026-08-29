#!/bin/zsh
set -u

SCRIPT_PATH="${0:A}"
SCRIPT_DIR="${SCRIPT_PATH:h}"
PROJECT_ROOT="${SCRIPT_DIR:h}"
VENV_DIR="$PROJECT_ROOT/.venv"
APP_PATH="$PROJECT_ROOT/app.py"
DASHBOARD_URL="http://localhost:8501"

echo "AI Investment Research Dashboard"
echo "Project: $PROJECT_ROOT"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "找不到專案虛擬環境 .venv，請先確認專案環境。"
  echo "按 Enter 關閉。"
  read -r
  exit 1
fi

if [[ ! -f "$APP_PATH" ]]; then
  echo "找不到 Streamlit 入口 app.py，請先確認專案檔案。"
  echo "按 Enter 關閉。"
  read -r
  exit 1
fi

if [[ -x /usr/sbin/lsof ]]; then
  EXISTING_PIDS="$(/usr/sbin/lsof -tiTCP:8501 -sTCP:LISTEN 2>/dev/null || true)"
  for PID in ${(f)EXISTING_PIDS}; do
    COMMAND_LINE="$(/bin/ps -p "$PID" -o command= 2>/dev/null || true)"
    if [[ "$COMMAND_LINE" == *"$APP_PATH"* ]]; then
      echo "Dashboard 已在執行，開啟瀏覽器：$DASHBOARD_URL"
      /usr/bin/open "$DASHBOARD_URL"
      exit 0
    fi
  done
fi

cd "$PROJECT_ROOT" || {
  echo "無法切換到專案目錄：$PROJECT_ROOT"
  echo "按 Enter 關閉。"
  read -r
  exit 1
}

source "$VENV_DIR/bin/activate"

if [[ "${AIIR_LAUNCHER_DRY_RUN:-0}" == "1" ]]; then
  echo "DRY_RUN_STREAMLIT_COMMAND: python -m streamlit run $APP_PATH --server.port 8501 --server.headless false"
  exit 0
fi

echo "啟動 Dashboard：$DASHBOARD_URL"
exec python -m streamlit run "$APP_PATH" --server.port 8501 --server.headless false
