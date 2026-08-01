# AI-Investment-Research

## 專案簡介

AI-Investment-Research 是一個結合 AI 與投資研究的個人專案。

本專案的目標不是建立自動交易系統，而是建立一套能協助整理、分析與理解投資資訊的 AI 研究平台。

---

## 專案目標

- 建立每日投資研究流程
- 整合公開市場資料
- 利用 AI 協助分析資訊
- 建立可持續擴充的投資研究工具

---

## 開發理念

本專案採用 Incremental Development（漸進式開發）。

每次只完成一小部分功能，經過驗證後再持續擴充。

---

## 目前進度

- ✅ 建立 Git Repository
- ✅ 建立 GitHub Repository
- ✅ 建立 VS Code 開發環境
- ✅ 建立 Project Prompt
- ✅ 建立 README

---

## 專案狀態

目前版本：v0.1

---

## MVP 使用方式

使用專案虛擬環境執行主程式：

```bash
.venv/bin/python src/main.py
```

主選單目前提供：

```text
1. 查詢股票
2. Watchlist
3. 離開
```

選擇 `1. 查詢股票` 後，可輸入單一股票代號：

```text
2330
NVDA
```

也可用逗號一次查詢多支股票：

```text
2330,NVDA,AAPL
2330, NVDA, AAPL
```

純數字股票代號會自動加上 `.TW`，英文股票代號會自動轉為大寫。

股票查詢會先檢查本機 SQLite cache。若 24 小時內已有 fresh cache，會直接使用本機資料；若沒有資料或 cache 已過期，才查詢 Yahoo Finance 並更新 cache。

Watchlist 可新增、移除、列出股票，資料儲存在 `data/watchlist.json`。SQLite cache 儲存在 `data/stocks.db`。這兩個檔案屬於 runtime / personal data，不提交到 Git。
