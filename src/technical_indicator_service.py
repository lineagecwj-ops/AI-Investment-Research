from dataclasses import dataclass
from datetime import date
import math
from statistics import stdev

import pandas as pd

from database import utc_now
from historical_price_service import get_analysis_close
from historical_price_service import slice_price_series_as_of
from models import HistoricalPriceSeries
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot


SMA_WINDOWS = (5, 10, 20, 60, 120, 200)
EMA_SHORT_WINDOW = 12
EMA_LONG_WINDOW = 26
RSI_WINDOW = 14
MACD_SIGNAL_WINDOW = 9
ATR_WINDOW = 14
VOLUME_WINDOW = 20
RETURN_WINDOWS = (5, 20, 60)
ROLLING_HIGH_WINDOWS = (20, 60, 252)
ROLLING_LOW_WINDOWS = (20, 60)
FIFTY_TWO_WEEK_TRADING_BARS = 252


@dataclass(frozen=True)
class TechnicalIndicatorDefinition:

    metric: str

    label: str

    category: str

    lookback: str

    unit: str

    description: str


TECHNICAL_INDICATOR_DEFINITIONS = {
    "sma_20": TechnicalIndicatorDefinition(
        metric="sma_20",
        label="SMA20（20日簡單移動平均）",
        category="Trend",
        lookback="20 trading bars including current bar",
        unit="price",
        description="Arithmetic mean of the latest 20 analysis-close values.",
    ),
    "ema_12": TechnicalIndicatorDefinition(
        metric="ema_12",
        label="EMA12（12日指數移動平均）",
        category="Trend",
        lookback="12 trading bars minimum warm-up",
        unit="price",
        description="Exponential moving average with span=12, adjust=False.",
    ),
    "rsi_14": TechnicalIndicatorDefinition(
        metric="rsi_14",
        label="RSI 14（14日相對強弱指標）",
        category="Momentum",
        lookback="14 price changes, requiring 15 trading bars",
        unit="index",
        description="Wilder RSI from analysis-close changes.",
    ),
    "macd": TechnicalIndicatorDefinition(
        metric="macd",
        label="MACD",
        category="Momentum",
        lookback="EMA12, EMA26, then 9 MACD values for signal",
        unit="price",
        description="EMA12 minus EMA26; signal is EMA9 of MACD.",
    ),
    "atr_14": TechnicalIndicatorDefinition(
        metric="atr_14",
        label="ATR 14（14日平均真實波幅）",
        category="Volatility",
        lookback="14 raw true-range values",
        unit="price",
        description="Wilder average true range using raw high, raw low, and prior raw close.",
    ),
    "volume_ratio_20": TechnicalIndicatorDefinition(
        metric="volume_ratio_20",
        label="Volume Ratio 20（20日量比）",
        category="Volume",
        lookback="current volume divided by previous 20 trading bars average volume",
        unit="ratio",
        description="Current volume divided by the previous 20-volume baseline; current day is excluded from the denominator.",
    ),
    "prior_high_60d": TechnicalIndicatorDefinition(
        metric="prior_high_60d",
        label="Prior 60D High（前 60 個交易日高點）",
        category="Price Position",
        lookback="previous 60 trading bars excluding current bar",
        unit="price",
        description="Highest raw high among the prior 60 trading bars.",
    ),
    "return_volatility_20d": TechnicalIndicatorDefinition(
        metric="return_volatility_20d",
        label="20D Return Volatility（20日報酬波動）",
        category="Volatility",
        lookback="20 one-bar returns",
        unit="daily return standard deviation",
        description="Sample standard deviation of the latest 20 daily analysis-close returns; not annualized.",
    ),
}


def build_technical_indicator_snapshot(
    series: HistoricalPriceSeries,
    as_of_date: date,
) -> TechnicalIndicatorSnapshot | None:
    sliced_series = slice_price_series_as_of(series, as_of_date)
    if not sliced_series.bars:
        return None
    technical_series = build_technical_indicator_series(sliced_series)
    if not technical_series.snapshots:
        return None
    return technical_series.snapshots[-1]


def build_technical_indicator_series(
    series: HistoricalPriceSeries,
) -> TechnicalIndicatorSeries:
    snapshots = tuple(_build_snapshots(series))
    return TechnicalIndicatorSeries(
        symbol=series.symbol,
        snapshots=snapshots,
        generated_at=utc_now(),
        source_price_fetched_at=series.fetched_at,
        source_price_is_stale=series.is_stale,
    )


def _build_snapshots(series: HistoricalPriceSeries) -> list[TechnicalIndicatorSnapshot]:
    bars = tuple(series.bars)
    if not bars:
        return []

    dates = [bar.trading_date for bar in bars]
    closes = [get_analysis_close(bar) for bar in bars]
    raw_closes = [bar.close for bar in bars]
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    volumes = [bar.volume for bar in bars]

    close_series = pd.Series(closes, dtype="float64")
    raw_close_series = pd.Series(raw_closes, dtype="float64")
    high_series = pd.Series(highs, dtype="float64")
    low_series = pd.Series(lows, dtype="float64")
    volume_series = pd.Series(volumes, dtype="float64")

    sma_values = {
        window: _series_to_clean_list(
            close_series.rolling(window=window, min_periods=window).mean()
        )
        for window in SMA_WINDOWS
    }
    ema_12 = _ema(close_series, EMA_SHORT_WINDOW)
    ema_26 = _ema(close_series, EMA_LONG_WINDOW)
    rsi_14 = _wilder_rsi(closes, RSI_WINDOW)
    macd, macd_signal, macd_histogram = _macd(close_series)
    true_ranges = _true_ranges(high_series, low_series, raw_close_series)
    atr_14 = _wilder_average(true_ranges, ATR_WINDOW)

    volume_sma_20 = _rolling_volume_mean(volumes, include_current=True)
    prior_volume_sma_20 = _rolling_volume_mean(volumes, include_current=False)

    return_values = {
        window: _pct_change(close_series, window)
        for window in RETURN_WINDOWS
    }
    daily_returns = _daily_returns(closes)
    return_volatility_20d = _rolling_stdev(daily_returns, 20)

    high_values = {
        window: _series_to_clean_list(
            high_series.rolling(window=window, min_periods=window).max()
        )
        for window in ROLLING_HIGH_WINDOWS
    }
    low_values = {
        window: _series_to_clean_list(
            low_series.rolling(window=window, min_periods=window).min()
        )
        for window in ROLLING_LOW_WINDOWS
    }
    prior_high_values = {
        window: _series_to_clean_list(
            high_series.shift(1).rolling(window=window, min_periods=window).max()
        )
        for window in ROLLING_HIGH_WINDOWS
    }
    prior_low_values = {
        window: _series_to_clean_list(
            low_series.shift(1).rolling(window=window, min_periods=window).min()
        )
        for window in ROLLING_LOW_WINDOWS
    }

    snapshots = []
    for index, trading_date in enumerate(dates):
        analysis_close = _finite_or_none(closes[index])
        if analysis_close is None:
            continue

        atr = atr_14[index]
        atr_pct = _safe_divide(atr, analysis_close)
        prior_high_20d = prior_high_values[20][index]
        prior_high_60d = prior_high_values[60][index]
        prior_high_252d = prior_high_values[252][index]
        prior_low_60d = prior_low_values[60][index]
        sma_20 = sma_values[20][index]
        sma_60 = sma_values[60][index]
        sma_120 = sma_values[120][index]

        snapshots.append(
            TechnicalIndicatorSnapshot(
                symbol=series.symbol,
                trading_date=trading_date,
                analysis_close=analysis_close,
                sma_5=sma_values[5][index],
                sma_10=sma_values[10][index],
                sma_20=sma_20,
                sma_60=sma_60,
                sma_120=sma_120,
                sma_200=sma_values[200][index],
                ema_12=ema_12[index],
                ema_26=ema_26[index],
                rsi_14=rsi_14[index],
                macd=macd[index],
                macd_signal=macd_signal[index],
                macd_histogram=macd_histogram[index],
                atr_14=atr,
                atr_14_pct=atr_pct,
                volume_sma_20=volume_sma_20[index],
                volume_ratio_20=_safe_divide(volumes[index], prior_volume_sma_20[index]),
                return_5d=return_values[5][index],
                return_20d=return_values[20][index],
                return_60d=return_values[60][index],
                return_volatility_20d=return_volatility_20d[index],
                high_20d=high_values[20][index],
                high_60d=high_values[60][index],
                high_252d=high_values[252][index],
                low_20d=low_values[20][index],
                low_60d=low_values[60][index],
                prior_high_20d=prior_high_20d,
                prior_high_60d=prior_high_60d,
                prior_high_252d=prior_high_252d,
                prior_low_20d=prior_low_values[20][index],
                prior_low_60d=prior_low_60d,
                distance_to_prior_20d_high=_pct_distance(analysis_close, prior_high_20d),
                distance_to_prior_60d_high=_pct_distance(analysis_close, prior_high_60d),
                distance_to_prior_52_week_high=_pct_distance(analysis_close, prior_high_252d),
                is_above_prior_20d_high=_is_above(analysis_close, prior_high_20d),
                is_above_prior_60d_high=_is_above(analysis_close, prior_high_60d),
                is_above_prior_52_week_high=_is_above(analysis_close, prior_high_252d),
                close_above_sma20=_is_above(analysis_close, sma_20),
                close_above_sma60=_is_above(analysis_close, sma_60),
                sma20_above_sma60=_is_above(sma_20, sma_60),
                sma60_above_sma120=_is_above(sma_60, sma_120),
                sma20_change_5d=_past_value_change(sma_values[20], index, 5),
                sma60_change_5d=_past_value_change(sma_values[60], index, 5),
                position_in_prior_60d_range=_range_position(
                    analysis_close,
                    prior_low_60d,
                    prior_high_60d,
                ),
            )
        )

    return snapshots


def _ema(values: pd.Series, span: int) -> list[float | None]:
    ema = values.ewm(span=span, adjust=False, min_periods=1).mean()
    output = _series_to_clean_list(ema)
    for index in range(min(span - 1, len(output))):
        output[index] = None
    return output


def _wilder_rsi(closes: list[float], window: int) -> list[float | None]:
    output: list[float | None] = [None] * len(closes)
    if len(closes) <= window:
        return output

    changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]

    average_gain = sum(gains[:window]) / window
    average_loss = sum(losses[:window]) / window
    output[window] = _rsi_from_averages(average_gain, average_loss)

    for close_index in range(window + 1, len(closes)):
        change_index = close_index - 1
        average_gain = ((average_gain * (window - 1)) + gains[change_index]) / window
        average_loss = ((average_loss * (window - 1)) + losses[change_index]) / window
        output[close_index] = _rsi_from_averages(average_gain, average_loss)

    return [_finite_or_none(value) for value in output]


def _rsi_from_averages(average_gain: float, average_loss: float) -> float:
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    if average_gain == 0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def _macd(values: pd.Series) -> tuple[list[float | None], list[float | None], list[float | None]]:
    ema_12 = _ema(values, EMA_SHORT_WINDOW)
    ema_26 = _ema(values, EMA_LONG_WINDOW)
    macd = [
        _subtract(short_value, long_value)
        for short_value, long_value in zip(ema_12, ema_26, strict=True)
    ]

    macd_signal = _ema_sparse(macd, MACD_SIGNAL_WINDOW)
    histogram = [
        _subtract(macd_value, signal_value)
        for macd_value, signal_value in zip(macd, macd_signal, strict=True)
    ]
    return macd, macd_signal, histogram


def _ema_sparse(values: list[float | None], span: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    valid_pairs = [
        (index, value)
        for index, value in enumerate(values)
        if value is not None
    ]
    if not valid_pairs:
        return output

    valid_values = pd.Series([value for _, value in valid_pairs], dtype="float64")
    ema_values = _series_to_clean_list(
        valid_values.ewm(span=span, adjust=False, min_periods=1).mean()
    )
    for valid_index, (source_index, _) in enumerate(valid_pairs):
        if valid_index < span - 1:
            continue
        output[source_index] = ema_values[valid_index]
    return output


def _true_ranges(
    highs: pd.Series,
    lows: pd.Series,
    raw_closes: pd.Series,
) -> list[float | None]:
    output: list[float | None] = []
    for index in range(len(highs)):
        high = _finite_or_none(highs.iloc[index])
        low = _finite_or_none(lows.iloc[index])
        if high is None or low is None:
            output.append(None)
            continue
        if index == 0:
            output.append(high - low)
            continue
        previous_close = _finite_or_none(raw_closes.iloc[index - 1])
        if previous_close is None:
            output.append(None)
            continue
        output.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return output


def _wilder_average(values: list[float | None], window: int) -> list[float | None]:
    output: list[float | None] = [None] * len(values)
    running_average: float | None = None
    valid_count = 0

    for index, value in enumerate(values):
        value = _finite_or_none(value)
        if value is None:
            running_average = None
            valid_count = 0
            continue

        valid_count += 1
        if running_average is None:
            if valid_count < window:
                continue
            window_values = values[index - window + 1:index + 1]
            if any(_finite_or_none(window_value) is None for window_value in window_values):
                valid_count = 0
                continue
            running_average = sum(window_values) / window
            output[index] = _finite_or_none(running_average)
            continue

        running_average = ((running_average * (window - 1)) + value) / window
        output[index] = _finite_or_none(running_average)

    return output


def _rolling_volume_mean(volumes: list[int | None], *, include_current: bool) -> list[float | None]:
    source_values = volumes if include_current else [None, *volumes[:-1]]
    output: list[float | None] = []
    for index in range(len(source_values)):
        if index + 1 < VOLUME_WINDOW:
            output.append(None)
            continue
        window_values = source_values[index - VOLUME_WINDOW + 1:index + 1]
        if any(value is None for value in window_values):
            output.append(None)
            continue
        output.append(_finite_or_none(sum(window_values) / VOLUME_WINDOW))
    return output


def _pct_change(values: pd.Series, periods: int) -> list[float | None]:
    return _series_to_clean_list((values / values.shift(periods)) - 1.0)


def _daily_returns(closes: list[float]) -> list[float | None]:
    output: list[float | None] = [None]
    for index in range(1, len(closes)):
        previous = closes[index - 1]
        current = closes[index]
        output.append(_pct_distance(current, previous))
    return output


def _rolling_stdev(values: list[float | None], window: int) -> list[float | None]:
    output: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window + 1:
            output.append(None)
            continue
        window_values = values[index - window + 1:index + 1]
        if any(value is None for value in window_values):
            output.append(None)
            continue
        output.append(_finite_or_none(stdev(window_values)))
    return output


def _series_to_clean_list(values: pd.Series) -> list[float | None]:
    return [_finite_or_none(value) for value in values.tolist()]


def _finite_or_none(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def _safe_divide(numerator, denominator) -> float | None:
    numerator = _finite_or_none(numerator)
    denominator = _finite_or_none(denominator)
    if numerator is None or denominator is None or denominator == 0:
        return None
    return _finite_or_none(numerator / denominator)


def _pct_distance(current, baseline) -> float | None:
    baseline = _finite_or_none(baseline)
    if baseline is None or baseline == 0:
        return None
    ratio = _safe_divide(current, baseline)
    if ratio is None:
        return None
    return ratio - 1.0


def _subtract(left, right) -> float | None:
    left = _finite_or_none(left)
    right = _finite_or_none(right)
    if left is None or right is None:
        return None
    return _finite_or_none(left - right)


def _is_above(left, right) -> bool | None:
    left = _finite_or_none(left)
    right = _finite_or_none(right)
    if left is None or right is None:
        return None
    return left > right


def _past_value_change(values: list[float | None], index: int, periods: int) -> float | None:
    if index < periods:
        return None
    return _pct_distance(values[index], values[index - periods])


def _range_position(close, low, high) -> float | None:
    close = _finite_or_none(close)
    low = _finite_or_none(low)
    high = _finite_or_none(high)
    if close is None or low is None or high is None:
        return None
    denominator = high - low
    if denominator == 0:
        return None
    return _finite_or_none((close - low) / denominator)
