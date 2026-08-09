# V1 ETF Constituent Universe

## Purpose

Batch 4B creates infrastructure for a broader Taiwan stock research universe derived from a frozen list of current ETF constituents.

Universe version: `2026-08-current-etf-constituent-v1`

This is a breadth-validation input layer only. It does not change V1 signals, the formal `volume_ratio_20 >= 1.20` threshold, scanner behavior, outcome semantics, backtest logic, Historical Replay, Walk-Forward, Replay Analytics, OOS, dashboard defaults, database schema, database content, OpenAI logic, AI logic, or recommendations.

## Predefined ETF List

The ETF list is frozen before any coverage or threshold result:

| Order | ETF | Name | Issuer | Role |
| ---: | --- | --- | --- | --- |
| 1 | `0050` | 元大台灣50 | 元大投信 | 大型權值 |
| 2 | `0051` | 元大中型100 | 元大投信 | 中型股 breadth |
| 3 | `0052` | 富邦科技 | 富邦投信 | 科技 |
| 4 | `0056` | 元大高股息 | 元大投信 | 高股息 |
| 5 | `00733` | 富邦臺灣中小 | 富邦投信 | 中小型 / 動能 |
| 6 | `00878` | 國泰永續高股息 | 國泰投信 | ESG + 高股息 |
| 7 | `00919` | 群益台灣精選高息 | 群益投信 | 另一套高股息 selection methodology |
| 8 | `00936` | 台新永續高息中小 | 台新投信 | 上市 + 上櫃中小型 / ESG / 高息 |

ETF sources must remain exactly this list and this order. The universe builder rejects reordering, missing ETFs, added ETFs, or outcome-selected ETF lists.

Canonical official source URLs:

| ETF | Canonical official URL |
| --- | --- |
| `0050` | `https://www.yuantaetfs.com/product/detail/0050/ratio` |
| `0051` | `https://www.yuantaetfs.com/product/detail/0051/ratio` |
| `0052` | `https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=0052` |
| `0056` | `https://www.yuantaetfs.com/product/detail/0056/ratio` |
| `00733` | `https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=00733` |
| `00878` | `https://www.cathaysite.com.tw/ETF/purchase?code=CN&name=Cathay+MSCI+Taiwan+ESG+Sustainability+High+Dividend+Yield+ETF` |
| `00919` | `https://www.capitalfund.com.tw/etf/product/detail/195/portfolio` |
| `00936` | `https://www.tsit.com.tw/ETF/Home/ETFSeriesDetail/00936` |

## Official-Source Policy

Source priority:

1. ETF issuer official holdings or fund asset page
2. TWSE / TPEx official ETF information
3. Official index or fund factsheet
4. Secondary source only if official source is unavailable and explicitly approved later

If an official source cannot be retrieved in the execution environment, the source must be marked `SOURCE_UNAVAILABLE`. The implementation must not silently switch to a secondary source.

Source access status and parser status are separate. A reachable official page can still be `PARSER_FAILED`, and a parser failure must not be reported as `SOURCE_UNAVAILABLE`.

TLS verification must stay enabled. Do not use `verify=False`, unverified HTTPS contexts, or certificate verification bypasses. If Python cannot validate a site that system tools can validate, record the exact Python TLS / CA bundle error and fix the runtime or CA chain safely before using that source.

For Yuanta official pages, Python strict TLS can fail on the local Python/OpenSSL stack while system `curl` validates the same canonical `yuantaetfs.com` pages. The service may use system `curl` as `TRANSPORT_CURL_VERIFIED` only with normal certificate verification enabled. It must not pass `-k`, `--insecure`, or any equivalent TLS bypass.

Each ETF keeps independent source and parser status. Partial parser recovery can be audited, but the formal `2026-08-current-etf-constituent-v1` universe remains `NOT_FINALIZED` until all 8 predefined ETF sources are `PARSED`.

## Source Metadata

Each ETF source stores:

- `etf_code`
- `etf_name`
- `issuer`
- `category`
- `official_source_url`
- `source_type`
- `holdings_date`
- `retrieved_date`
- `raw_constituent_count`
- `source_status`
- `unavailable_reason`

The final stock list alone is not sufficient research metadata.

## Snapshot Semantics

本研究股票池使用 2026 年目前 ETF 成分股快照，不是 2018～2025 各歷史日期當時的 ETF 成分股。因此存在存活者偏誤與成分股回溯偏誤。本股票池只能用於擴大股票廣度的研究驗證，不能視為無偏誤的歷史 point-in-time universe。

The snapshot is frozen before outcome research. ETF weight may be preserved as source metadata, but ETF weight must not be used as outcome weighting.

## Normalization

Raw constituent records preserve:

- `etf_code`
- `stock_code`
- `stock_name`
- `raw_market_info`
- `raw_weight`
- `holdings_date`
- `source_url`

Normalized stock identity requires:

- `symbol`
- `stock_code`
- `stock_name`
- `exchange`

上市 stocks use `XXXX.TW`. 上櫃 stocks use `XXXX.TWO`. The service must not guess market suffixes without official market metadata or an explicit project normalization rule.

## Deduplication

The final research universe contains one row per unique normalized Taiwan stock symbol.

If the same stock appears in multiple ETFs, the universe keeps:

- one unique `symbol`
- all `source_etfs`
- `etf_membership_count`

`etf_membership_count` is lineage metadata only. It is not a research weight, ranking input, score, recommendation, or probability.

## Non-Stock Exclusions

Non-stock assets are not silently dropped. Exclusions preserve:

- raw identifier
- source ETF
- reason
- detail

Examples include cash, futures, ETF, foreign asset, bond, depositary receipt, invalid symbol, and unknown exchange.

## Coverage Audit

Coverage audit uses `data/stocks.db` with SQLite `mode=ro` and `PRAGMA query_only=ON`.

It classifies normalized universe symbols as:

- `AVAILABLE_LOCAL`
- `MISSING_LOCAL`
- `INSUFFICIENT_COVERAGE`
- `INVALID_SYMBOL`

Coverage window:

- Observation window: `2018-01-01` through `2025-12-31`
- Technical warm-up: `60` trading bars before the observation window
- Outcome extension: `20` trading bars after the observation window

The audit checks pre-window history, observation-window OHLCV rows, post-window outcome bars, duplicate trading dates, and invalid OHLCV rows. It does not initialize, migrate, insert, update, delete, or backfill `stocks.db`.

The DB file audit records before and after:

- path
- size
- mtime
- SHA-256

## Future Point-In-Time Upgrade

A future phase may add historical ETF constituent snapshots, for example:

- 2018 universe
- 2019 universe
- 2020 universe
- 2021 universe
- 2022 universe
- 2023 universe
- 2024 universe
- 2025 universe

That future path would reduce constituent look-back bias, but it is not implemented in Batch 4B.

## No V1 Change

This service intentionally excludes:

- V1 evaluation
- HHR comparison
- threshold comparison
- scanner ranking
- future probability
- recommendation
- dashboard integration
- historical price backfill

Seeing `MISSING_LOCAL` in a coverage report is a stop point. It does not authorize Yahoo fetches, bulk price downloads, or writes to `data/stocks.db`.
