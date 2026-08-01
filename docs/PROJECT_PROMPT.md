# AI-Investment-Research
## Project Prompt v0.1

### 1. Project Mission｜專案使命

本專案旨在建立一套 Personal Investment Intelligence Platform
（個人投資智慧研究平台）。

系統的目的不是準確預測未來股價，也不是取代使用者做投資決策，
而是透過自動化資料蒐集、資料整理、量化分析與 AI 輔助分析，
降低投資研究所需的時間與資訊整理成本。

核心流程：

資料取得
→ 資料清理與標準化
→ 建立歷史資料
→ 趨勢與異常分析
→ AI 整合與解釋
→ Dashboard 呈現
→ 使用者判斷


### 2. Investment Philosophy｜投資研究原則

系統應協助使用者理解：

- 發生了什麼？
- 為什麼值得注意？
- 有哪些支持證據？
- 有哪些反向證據？
- 目前有哪些風險？
- 接下來應該觀察哪些指標？

AI 不應將單一指標直接解讀為買進或賣出訊號。

避免使用：

「一定會漲」
「一定會跌」
「保證獲利」

等無法被資料支持的結論。

系統主要提供 Research Support（研究支援），
最終投資決策由使用者自行判斷。


### 3. Market Scope｜市場範圍

Version 1 以台灣股票市場為核心。

V1 優先處理：

- 台股個股
- 台灣 ETF
- 台灣市場指數
- 基本面資料
- 市場交易資料
- 法人／資金面資料

系統 Architecture（架構）應保留未來擴充能力，
不得將核心資料模型完全綁定台灣市場。

未來可逐步加入：

- 美國市場
- 日本市場
- 韓國市場
- 全球主要指數
- 匯率
- 利率
- 半導體與 AI 相關國際市場指標


### 4. Analysis Framework｜分析架構

系統分析至少逐步涵蓋以下維度：

#### A. Fundamental｜基本面
- EPS
- ROE
- Revenue
- Profit
- Growth Rate
- PE Ratio
- Dividend Yield
- 其他後續確認的重要財務指標

#### B. Market｜市場面
- Price
- Volume
- Market Index
- Industry Trend
- Historical Trend

#### C. Institutional / Capital Flow｜法人與資金面
- 外資
- 投信
- 自營商
- 法人買賣超
- 其他可取得且具研究價值的資金流向資料

#### D. ETF Analysis｜ETF 分析
- ETF 成分股
- 成分股權重
- 成分調整
- 權重增加／降低
- 多檔 ETF 重複持股
- ETF 資金與個股之關聯

ETF 成分與權重變化應視為市場研究訊號之一，
不得假設 ETF 管理人具有內線資訊。


### 5. External Market Factors｜外部市場因素

台灣市場分析未來應能逐步整合：

- NASDAQ
- Philadelphia Semiconductor Index / SOX
- 美國主要市場
- Nikkei
- KOSPI
- Exchange Rates
- Interest Rates
- Semiconductor / AI Industry Indicators

V1 不要求一次完成所有外部市場資料。

採 Incremental Development（漸進式開發），逐版本增加。


### 6. AI Analysis Principles｜AI 分析原則

AI 產生重要研究結論時，應盡可能同時提供：

1. Observation — 觀察到什麼
2. Evidence — 支持這個觀察的資料
3. Counter Evidence — 是否存在相反訊號
4. Risk — 目前主要風險
5. Watch Items — 接下來值得觀察的項目
6. Data Timestamp — 使用資料的時間範圍或最後更新時間

AI 應區分：

- Fact（事實）
- Interpretation（解讀）
- Inference（推論）

不得把推論描述成已確認的事實。


### 7. Data Traceability｜資料可追溯性

所有重要數據應盡可能記錄：

- Source
- Original Value
- Date / Period
- Last Updated Time
- Processing Method

資料流程原則：

Raw Data
→ Processed Data
→ Derived Metrics
→ AI Analysis
→ Dashboard

Raw Data（原始資料）原則上不直接被 AI 修改。

資料清理、計算與轉換應具有可重現性。


### 8. Data Acquisition｜資料取得

長期目標為：

系統自動取得公開且合法使用的市場資料，
而不是要求使用者每天手動下載 Excel。

資料來源選擇應考慮：

- Reliability
- Legality / Terms of Use
- Update Frequency
- Data Quality
- API Availability
- Cost
- Long-term Maintainability

若免費來源不穩定，
應保留更換 Data Provider 的能力。


### 9. User Experience｜使用體驗

系統最終應能透過 Web-based Dashboard 使用，
並考慮：

- Mac
- PC
- Tablet
- Smartphone

V1 優先確保 Desktop Browser 體驗良好，
再逐步優化 Mobile Experience。

Dashboard 的目的不是堆積所有數據，
而是協助使用者快速回答：

「今天有什麼值得我注意？」


### 10. Development Principles｜開發原則

開發流程原則：

Requirement
→ Design
→ Implementation
→ Test
→ Documentation
→ User Feedback
→ Improvement

重要功能開始 Coding 前，
應先確認需求與影響範圍。

優先考慮：

- Maintainability
- Modularity
- Readability
- Testability
- Data Integrity
- Security
- Extensibility

避免為了快速完成單一功能，
破壞整體 Architecture。


### 11. AI-assisted Development｜AI 協作開發

角色原則：

#### User
- 決定產品方向
- 提供實際需求
- 測試功能
- 提供使用回饋
- 做最終決策

#### ChatGPT
- 協助需求分析
- 系統架構規劃
- 技術選型
- 文件整理
- 開發任務拆解
- Review 設計與結果
- 協助解釋技術概念

#### Codex
- 讀取專案
- 實作已確認需求
- 修改程式碼
- 建立測試
- 執行測試
- Debug
- Refactor
- 更新相關技術文件

若需求存在重大歧義，
應先釐清需求，而不是自行假設後大幅修改系統。


### 12. Open-source Policy｜開源專案使用原則

開發新功能前，可以研究 GitHub 上成熟的 Open Source Projects。

評估項目包括：

- License
- Maintenance Activity
- Security
- Code Quality
- Documentation
- Architecture
- Project Fit

Open Source 的用途可以是：

- Architecture Reference
- UI Inspiration
- Library Selection
- Implementation Reference

不應在不了解 License、Security 與 Architecture 的情況下，
直接大量複製第三方程式碼。


### 13. Version Strategy｜版本策略

本專案採 Incremental Development。

V1 的目標不是建立完整投資平台。

V1 的目標是：

「建立一個可以開始每天使用的最小可行版本。」

實際使用後：

使用
→ 發現需求
→ 評估
→ 改善
→ 新版本

Project Prompt 本身亦為 Living Document，
可隨著專案演進持續更新。


### 14. Core Principle｜最高原則

當「功能數量」與「資料可信度」發生衝突時：

優先資料可信度。

當「AI 結論」與「可驗證資料」發生衝突時：

優先可驗證資料。

當「快速開發」與「長期可維護性」發生衝突時：

在合理範圍內優先長期可維護性。

本系統的價值不在於產生更多投資結論，

而在於：

讓使用者能以更少的時間，
取得更完整、可追溯、可理解的資訊，
做出更有依據的投資判斷。