# User Interface Terminology

## 中文 UI 原則

V1.0 日常研究介面以繁體中文為主。主要操作、表格欄位、摘要、提示、caption 與 helper text 優先使用一般使用者容易理解的中文。

必要專有名詞第一次出現時可保留英文括號，例如：歷史命中率（Historical Hit Rate）、樣本外驗證（Out-of-Sample Validation）、最大有利變動（MFE）、最大不利變動（MAE）。

## Internal IDs 保持英文

UI 中文化只發生在 presentation layer。Internal IDs、enum values、service contracts 與資料模型不得因顯示名稱而改名。

Examples:

- `technical_example_v1`
- `raw_high_breakout_60d_within_20d_v1`
- `MATCH`
- `NO_MATCH`
- `NOT_EVALUABLE`
- `FAILED`
- `volume_ratio_20`
- `distance_to_prior_60d_high`

## Domain Semantics 不變

中文 terminology 不改變 signal、outcome、scanner、ranking、backtest、historical replay、walk-forward replay、replay analytics 或 OOS validation semantics。

「符合條件」只表示目前符合指定研究條件，不是買進訊號、推薦清單、未來上漲機率或投資建議。

## 主要術語中英對照

| Internal / English | UI label |
| --- | --- |
| Scan Setup | 掃描設定 |
| Scan Mode | 掃描模式 |
| Current | 目前市場 |
| Historical Replay | 歷史回放 |
| Walk-Forward Replay | 多日期歷史回放 |
| Out-of-Sample Validation | 樣本外驗證 |
| Symbol Source | 股票來源 |
| Manual Input | 手動輸入 |
| Watchlist | 觀察清單 |
| Saved Universe | 已儲存股票池 |
| Research Priority | 研究優先順序 |
| Historical Hit Rate | 歷史命中率 |
| Resolved Samples | 已解析歷史樣本數 |
| Candidate Period Share | 候選出現期間比例 |

## 技術指標翻譯

| Internal metric | UI label |
| --- | --- |
| `analysis_close` | 分析價格 |
| `sma_20` | 20 日均線 |
| `sma_60` | 60 日均線 |
| `sma_120` | 120 日均線 |
| `sma_200` | 200 日均線 |
| `ema_12` | 12 日指數移動平均線 |
| `ema_26` | 26 日指數移動平均線 |
| `rsi_14` | RSI 14 日相對強弱指標 |
| `macd` | MACD |
| `macd_signal` | MACD 訊號線 |
| `macd_histogram` | MACD 柱狀差值 |
| `atr_14` | ATR 14 日平均真實波幅 |
| `atr_14_pct` | ATR 波動幅度比例 |
| `volume_sma_20` | 20 日平均成交量 |
| `volume_ratio_20` | 20 日成交量比率 |
| `prior_high_20d` | 前 20 日高點 |
| `prior_high_60d` | 前 60 日高點 |
| `prior_high_252d` | 前 52 週高點 |
| `distance_to_prior_20d_high` | 距離前 20 日高點 |
| `distance_to_prior_60d_high` | 距離前 60 日高點 |
| `distance_to_prior_52_week_high` | 距離前 52 週高點 |
| `return_5d` | 5 日價格變化 |
| `return_20d` | 20 日價格變化 |
| `return_60d` | 60 日價格變化 |
| `return_volatility_20d` | 20 日價格變化波動度 |

## Signal / Outcome 顯示名稱

| Internal ID | UI label |
| --- | --- |
| `technical_example_v1` | 波段技術篩選 V1 |
| `raw_high_breakout_60d_within_20d_v1` | 20 個交易日內突破前 60 日高點 |

## Status 顯示名稱

| Internal value | UI label |
| --- | --- |
| `MATCH` | 符合條件 |
| `NO_MATCH` | 不符合條件 |
| `NOT_EVALUABLE` | 資料不足 |
| `FAILED` | 掃描失敗 |
| `HIT` | 達成研究目標（HIT） |
| `MISS` | 未達研究目標（MISS） |
| `INCOMPLETE` | 觀察期間尚未完整 |

## Beginner-Friendly Copy 原則

Helper text 應簡短回答「這是什麼」與「我要怎麼理解」。優先使用 `help=`、`caption`、`expander`，避免在主畫面堆疊長段說明。

Examples:

- 歷史命中率：過去符合相同條件且已解析的歷史事件中，達成指定研究目標的比例。不是未來上漲機率。
- 已解析歷史樣本數：已能判定 HIT 或 MISS 的歷史案例數。
- MFE：訊號後指定觀察期間內，分析價格曾出現的最大有利變動。
- MAE：訊號後指定觀察期間內，分析價格曾出現的最大不利變動。

## 禁止投資推薦語言

UI terminology 不得引入推薦買進、買進訊號、值得買、必漲、強勢股、看多、看空、勝率、成功機率、目標價等投資推薦或預測語言。

允許出現在否定說明中，例如：「不是未來上漲機率」。

## Developer Traceability

Primary UI 顯示中文 label。若需要追溯 internal IDs，可放在「開發者資訊」或「技術詳細資料」expander，例如：

- 顯示名稱：20 日成交量比率
- Internal Metric ID：`volume_ratio_20`

## Future V2 Terminology Extension

未來若新增 V2 signal、outcome、scanner mode 或 validation mode，應先更新 `src/ui_terminology.py` 與對應 localization tests，再接入 UI。新增顯示名稱不得改動既有 internal IDs 或 service semantics。
