# Technical Condition Detail

## Purpose

Technical Condition Detail is a V1.0 post-release UX improvement for `Swing Research` -> `目前市場`.

It is a presentation and education layer only. It does not change `technical_example_v1`, scanner thresholds, signal semantics, outcome semantics, ranking, replay, walk-forward replay, OOS validation, database schema, or AI analysis logic.

## User-Facing Meaning

After a Current Scan completes, the dashboard shows `技術條件明細` below `掃描結果摘要`.

The selector `查看股票技術狀態` includes stocks that completed current technical evaluation:

- `MATCH`
- `NO_MATCH`

It does not include `NOT_EVALUABLE` or `FAILED` as if they had complete technical details.

For each selectable stock, the dashboard shows:

- `符合 X / 5 項技術條件`
- beginner-friendly categories for trend, volume, momentum, and distance to prior high
- actual values from scan-time technical data
- V1 thresholds
- existing PASS / FAIL status from scanner evaluation
- neutral gap-to-threshold text
- three beginner-friendly visual bars for volume activity, RSI momentum, and distance to prior 60-day high
- beginner explanations
- developer traceability for internal IDs and raw metric names

`X / 5` is only a factual condition count. It is not a stock score, opportunity score, buy score, win rate, future probability, ranking signal, or recommendation.

## Data Source

The detail view uses scan-time `SignalMatch` data stored on `SwingScannerResult.current_signal_details`.

For matched candidates, this is the same current signal trace already stored on `SwingOpportunityCandidate.signal_match`.

For `NO_MATCH` stocks, the scanner stores the evaluated `SignalMatch` before returning the result. The dashboard reads this stored object and does not:

- fetch Yahoo again
- rerun scanner
- rerun backtest
- rerun historical replay
- rerun walk-forward replay
- rerun OOS validation

## V1 Conditions

The current V1 detail table displays the five existing `technical_example_v1` conditions:

| Technical condition | Current value | V1 requirement |
| --- | --- | --- |
| 分析價格 vs 20 日均線 | analysis close and SMA20 | analysis close > SMA20 |
| 20 日均線 vs 60 日均線 | SMA20 and SMA60 | SMA20 > SMA60 |
| 20 日成交量比率 | volume ratio | >= 1.20 |
| RSI 14 | RSI value | 50-70 |
| 距離前 60 日高點 | percent distance | >= -5% |

PASS / FAIL is copied from the evaluated condition status. The UI helper does not promote near-threshold stocks into `MATCH`.

## Neutral Gap Rules

Gap text is factual:

- volume ratio below `1.20`: `尚差 0.xx`
- distance to prior 60-day high below `-5%`: `尚差 x.xx percentage points`
- RSI inside `50-70`: `目前位於 V1 設定區間內。`
- RSI below / above the range: display the numeric difference from the lower / upper bound
- missing metrics: `N/A`

The gap is not converted into probability, expected return, timing, buy point language, or recommendation language.

## Beginner Visual Bars

The visualization uses Streamlit / Altair native rendering and shows three independent visual bars. The dashboard does not put volume ratio, RSI, and distance-to-high on one shared numeric axis because their units and domains are different.

Each visual uses scan-time actual values and existing `SignalMatch.evaluated_conditions` status:

- `成交量活躍度`: current `volume_ratio_20`, V1 threshold `1.20`, neutral gap, and dynamic scale starting at `0`.
- `RSI 動能`: current `RSI 14`, V1 range `50-70`, and fixed RSI domain `0-100`.
- `接近前高程度`: current `distance_to_prior_60d_high`, V1 threshold `-5%`, `0%` prior-high reference, and dynamic range that keeps the current value, threshold, and `0%` visible.

Missing visual metrics display `N/A` and the safe message `目前沒有足夠資料顯示此指標。`

The detailed table remains the source of full numeric context:

- `技術條件`
- `目前實際值`
- `V1 要求`
- `狀態`
- `距離門檻`
- `白話解釋`

The visual bars do not create a score, buy score, opportunity score, win rate, probability, recommendation, buy-point label, predicted price, future return, strategy P&L, or expected outcome.
