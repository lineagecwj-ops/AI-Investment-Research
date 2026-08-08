# macOS Quick Launch

## 這是什麼

`AI Investment Research.app` 是本機 macOS 雙擊啟動器，用來開啟 V1.0 Daily Swing Research Dashboard。

它只負責啟動本機 Streamlit dashboard，不修改 production research logic、signal、outcome、ranking、replay、OOS validation、watchlist、universe 或 database schema。

## 使用體驗

雙擊 `dist/AI Investment Research.app` 後，Launcher 會：

1. 確認專案目錄存在。
2. 確認 `.venv` 與 `.venv/bin/python` 存在。
3. 確認 `app.py` 存在。
4. 檢查 `http://localhost:8501/_stcore/health`。
5. 如果 Streamlit 已經在 `localhost:8501` ready，直接開啟瀏覽器。
6. 如果尚未啟動，使用專案內 `.venv/bin/python -m streamlit run app.py` 背景啟動。
7. 等待最多 30 秒，ready 後自動開啟 `http://localhost:8501`。

不需要手動開 Terminal，也不需要輸入 `cd`、`source .venv/bin/activate` 或 `streamlit run app.py`。

## Build .app

在 repo root 執行：

```bash
launcher/build_mac_app.sh
```

輸出位置：

```text
dist/AI Investment Research.app
```

`dist/` 是 generated artifact，不進 Git。未來如果 AppleScript 或 shell launcher 有調整，重新執行 build script 即可重建 `.app`。

如果 Launcher 重新 build 後 Dock 點擊行為異常，請從 Dock 移除舊圖示，再將最新 `dist/AI Investment Research.app` 拖回 Dock。

## 第二次雙擊行為

如果 `localhost:8501` 已經是 ready 的 Streamlit server，Launcher 不會啟動第二個 Streamlit process，只會直接開啟瀏覽器到：

```text
http://localhost:8501
```

## 背景執行

Launcher App 本身執行完會退出；Streamlit server 會繼續在背景執行。

MVP 不提供「退出 app 時自動停止 Streamlit」功能，避免誤殺其他 Python 或 Streamlit process。

## Port 與 health check

- 固定 port：`8501`
- Dashboard URL：`http://localhost:8501`
- Health endpoint：`http://localhost:8501/_stcore/health`

Launcher 不會自動改用 `8502` 或其他 port。若 `8501` 被其他非本專案程式占用，會顯示安全錯誤，不會 kill process。

## Log 位置

Launcher log 寫入：

```text
~/Library/Logs/AI-Investment-Research/launcher.log
```

Log 不會放進 Git。Launcher 不會寫入或顯示 `OPENAI_API_KEY`，也不會把 secrets 寫進 log。

## 錯誤訊息

常見錯誤包含：

- 專案目錄不存在
- `.venv` 不存在
- `.venv/bin/python` 不存在或不可執行
- `app.py` 不存在
- Streamlit import unavailable
- Port 8501 已被其他程式使用
- Streamlit 未在 30 秒內 ready

雙擊 `.app` 時，錯誤會以 macOS dialog 顯示。

## 如何手動停止

本次沒有提供 stop script，避免誤殺其他 Streamlit 或 Python process。

如需手動停止，請先確認 process command 明確包含：

```text
/Users/hankmacmini/Documents/Projects/AI-Investment-Research/app.py
```

可以用：

```bash
ps aux | grep "AI-Investment-Research/app.py"
```

確認後再只停止該明確 process。

## macOS Gatekeeper

因為這是本機自建 `.app`，第一次雙擊時 macOS 可能顯示 unidentified developer / Gatekeeper 提示。

本專案不會自動執行 `xattr`、codesign bypass，也不會關閉 Gatekeeper。請依 macOS 正常安全流程開啟自建 app。

## Project path override

正式預設專案路徑固定為：

```text
/Users/hankmacmini/Documents/Projects/AI-Investment-Research
```

為了手動測試錯誤處理，shell launcher 支援暫時 override：

```bash
AI_INVESTMENT_RESEARCH_DIR=/missing/path launcher/launch_ai_investment_research.sh
```

AppleScript `.app` 使用正式預設路徑。
