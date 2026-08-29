"""Forward-only, point-in-time research observations for manual dashboard use."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import asdict
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from database_config import PROJECT_ROOT
from database_config import resolve_database_runtime_config
from database import historical_price_bar_from_row
from database import parse_cache_datetime
from models import HistoricalPriceSeries


FORWARD_RESEARCH_OBSERVATION_VERSION = "FORWARD_RESEARCH_OBSERVATION_V0"
POINT_IN_TIME_CLASSIFICATION = "FORWARD_CAPTURED_POINT_IN_TIME_V0"
FORWARD_DATASET_START_DATE = date(2026, 8, 29)
BENCHMARK_SYMBOL = "0050.TW"
PRICE_SEMANTICS = "ADJUSTED_CLOSE_FIRST_FALLBACK_CLOSE_V1"
MARKET_DATA_SOURCE = "LOCAL_LIVE_HISTORICAL_CACHE"
RELATIVE_ALIGNMENT_AVAILABLE = "EXACT_DATE_ALIGNED"
RELATIVE_ALIGNMENT_UNAVAILABLE = "EXACT_DATE_ALIGNMENT_UNAVAILABLE"
DEFAULT_DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "forward_observations"
    / "forward_research_observations_v0.sqlite"
)


class ForwardResearchObservationError(Exception):
    """Raised when a manual forward observation cannot be safely captured."""


@dataclass(frozen=True)
class ForwardMarketDataStatus:
    selected_market_date: date | None
    benchmark_market_date: date | None
    expected_latest_date: date

    @property
    def selected_market_data_is_fresh(self) -> bool:
        return self.selected_market_date is not None and self.selected_market_date >= self.expected_latest_date


@dataclass(frozen=True)
class ForwardResearchObservationContext:
    symbol: str
    company_name: str | None
    industry: str | None
    as_of_date: date
    research_price: float
    return_20d: float
    return_60d: float
    close_vs_sma20: float
    close_vs_sma60: float
    rsi14: float
    rel_return_20d: float | None
    rel_return_60d: float | None
    relative_alignment_status: str
    in_watchlist: bool
    long_term_research_available: bool
    historical_trends_available: bool
    ai_research_available: bool
    swing_research_available: bool
    market_data_source: str = MARKET_DATA_SOURCE
    data_date: date | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ForwardResearchObservationError("研究標的不可為空白。")
        if self.data_date is not None and self.data_date != self.as_of_date:
            raise ForwardResearchObservationError("data_date 必須與 as_of_date 一致。")
        if self.relative_alignment_status not in {
            RELATIVE_ALIGNMENT_AVAILABLE,
            RELATIVE_ALIGNMENT_UNAVAILABLE,
        }:
            raise ForwardResearchObservationError("0050 對齊狀態不正確。")
        if self.relative_alignment_status == RELATIVE_ALIGNMENT_AVAILABLE:
            if self.rel_return_20d is None or self.rel_return_60d is None:
                raise ForwardResearchObservationError("0050 完整對齊時必須有相對報酬。")
        elif self.rel_return_20d is not None or self.rel_return_60d is not None:
            raise ForwardResearchObservationError("0050 未精確對齊時不可寫入相對報酬。")
        _require_finite(self.research_price, "research_price")
        _require_finite(self.return_20d, "return_20d")
        _require_finite(self.return_60d, "return_60d")
        _require_finite(self.close_vs_sma20, "close_vs_sma20")
        _require_finite(self.close_vs_sma60, "close_vs_sma60")
        _require_finite(self.rsi14, "rsi14")
        if not 0.0 <= float(self.rsi14) <= 100.0:
            raise ForwardResearchObservationError("rsi14 必須介於 0 與 100。")
        if self.rel_return_20d is not None:
            _require_finite(self.rel_return_20d, "rel_return_20d")
        if self.rel_return_60d is not None:
            _require_finite(self.rel_return_60d, "rel_return_60d")


@dataclass(frozen=True)
class ForwardResearchObservation:
    observation_id: str
    observation_version: str
    symbol: str
    company_name: str | None
    industry: str | None
    as_of_date: date
    captured_at: datetime
    point_in_time_classification: str
    research_price: float
    price_semantics: str
    return_20d: float
    return_60d: float
    close_vs_sma20: float
    close_vs_sma60: float
    rsi14: float
    rel_return_20d: float | None
    rel_return_60d: float | None
    relative_alignment_status: str
    in_watchlist: bool
    long_term_research_available: bool
    historical_trends_available: bool
    ai_research_available: bool
    swing_research_available: bool
    market_data_source: str
    data_date: date
    observation_checksum: str


@dataclass(frozen=True)
class CaptureResult:
    observation: ForwardResearchObservation
    created: bool


def research_price(bar) -> float | None:
    """Use the released research price semantic without importing ML code."""
    for value in (bar.adjusted_close, bar.close):
        if value is not None and math.isfinite(float(value)) and float(value) > 0.0:
            return float(value)
    return None


def build_local_observation_context(
    *,
    stock_series: HistoricalPriceSeries,
    benchmark_series: HistoricalPriceSeries,
    company_name: str | None,
    industry: str | None,
    in_watchlist: bool,
    long_term_research_available: bool,
    historical_trends_available: bool,
    ai_research_available: bool,
    swing_research_available: bool,
) -> ForwardResearchObservationContext:
    """Derive context only from already-local historical price series."""
    bars = _canonical_price_bars(stock_series)
    if len(bars) < 61:
        raise ForwardResearchObservationError("目前本地研究資料不足，至少需要 61 筆有效交易日價格。")
    as_of_date, latest_price = bars[-1]
    prices = [price for _, price in bars]
    sma20 = sum(prices[-20:]) / 20
    sma60 = sum(prices[-60:]) / 60
    rsi14 = _rsi14(prices[-15:])
    reference_20_date, reference_20_price = bars[-21]
    reference_60_date, reference_60_price = bars[-61]
    return_20d = latest_price / reference_20_price - 1.0
    return_60d = latest_price / reference_60_price - 1.0
    benchmark_lookup = dict(_canonical_price_bars(benchmark_series))
    benchmark_dates = (as_of_date, reference_20_date, reference_60_date)
    if all(value in benchmark_lookup for value in benchmark_dates):
        benchmark_latest = benchmark_lookup[as_of_date]
        rel_return_20d = return_20d - (benchmark_latest / benchmark_lookup[reference_20_date] - 1.0)
        rel_return_60d = return_60d - (benchmark_latest / benchmark_lookup[reference_60_date] - 1.0)
        alignment_status = RELATIVE_ALIGNMENT_AVAILABLE
    else:
        rel_return_20d = None
        rel_return_60d = None
        alignment_status = RELATIVE_ALIGNMENT_UNAVAILABLE
    return ForwardResearchObservationContext(
        symbol=stock_series.symbol,
        company_name=_optional_text(company_name),
        industry=_optional_text(industry),
        as_of_date=as_of_date,
        research_price=latest_price,
        return_20d=return_20d,
        return_60d=return_60d,
        close_vs_sma20=latest_price / sma20 - 1.0,
        close_vs_sma60=latest_price / sma60 - 1.0,
        rsi14=rsi14,
        rel_return_20d=rel_return_20d,
        rel_return_60d=rel_return_60d,
        relative_alignment_status=alignment_status,
        in_watchlist=in_watchlist,
        long_term_research_available=long_term_research_available,
        historical_trends_available=historical_trends_available,
        ai_research_available=ai_research_available,
        swing_research_available=swing_research_available,
        data_date=as_of_date,
    )


def capture_local_forward_observation(
    *,
    symbol: str,
    company_name: str | None,
    industry: str | None,
    in_watchlist: bool,
    long_term_research_available: bool,
    historical_trends_available: bool,
    ai_research_available: bool,
    swing_research_available: bool,
    repository: "ForwardResearchObservationRepository | None" = None,
    live_db_path: Path | str | None = None,
) -> CaptureResult:
    """Capture one immutable observation from already-local market data only."""
    context = build_local_observation_context(
        stock_series=load_live_historical_price_series(symbol, db_path=live_db_path),
        benchmark_series=load_live_historical_price_series(BENCHMARK_SYMBOL, db_path=live_db_path),
        company_name=company_name,
        industry=industry,
        in_watchlist=in_watchlist,
        long_term_research_available=long_term_research_available,
        historical_trends_available=historical_trends_available,
        ai_research_available=ai_research_available,
        swing_research_available=swing_research_available,
    )
    return (repository or ForwardResearchObservationRepository()).capture(context)


def load_live_historical_price_series(
    symbol: str,
    *,
    db_path: Path | str | None = None,
) -> HistoricalPriceSeries:
    """Read an already-populated live historical cache without creating or updating it."""
    path = (Path(db_path) if db_path is not None else resolve_database_runtime_config().active_live_db_path).resolve()
    if not path.exists():
        raise ForwardResearchObservationError("目前本地市場資料尚未建立。")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT symbol, trading_date, open, high, low, close, adjusted_close,
                   volume, dividends, stock_splits, currency, fetched_at
            FROM historical_prices
            WHERE symbol = ?
            ORDER BY trading_date ASC
            """,
            (symbol.strip().upper(),),
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        raise ForwardResearchObservationError("目前本地市場資料不足，請先更新。")
    fetched_at_values = tuple(parse_cache_datetime(row["fetched_at"]) for row in rows if row["fetched_at"])
    return HistoricalPriceSeries(
        symbol=rows[0]["symbol"],
        currency=next((row["currency"] for row in rows if row["currency"]), None),
        bars=tuple(historical_price_bar_from_row(row) for row in rows),
        fetched_at=min(fetched_at_values) if fetched_at_values else datetime.now(ZoneInfo("Asia/Taipei")),
        is_stale=False,
    )


def live_market_data_status(
    symbol: str,
    *,
    captured_at: datetime | None = None,
    db_path: Path | str | None = None,
) -> ForwardMarketDataStatus:
    """Report cache dates without writing or treating classification data as market data."""
    captured_at = captured_at or datetime.now(ZoneInfo("Asia/Taipei"))
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ForwardResearchObservationError("captured_at 必須是含時區的實際時間。")
    return ForwardMarketDataStatus(
        selected_market_date=_latest_valid_market_date(symbol, db_path=db_path),
        benchmark_market_date=_latest_valid_market_date(BENCHMARK_SYMBOL, db_path=db_path),
        expected_latest_date=_expected_latest_market_date(captured_at.date()),
    )


class ForwardResearchObservationRepository:
    """Small, explicit SQLite repository for immutable forward observations."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH, *, now: Callable[[], datetime] | None = None):
        self._db_path = Path(db_path)
        self._now = now or (lambda: datetime.now(ZoneInfo("Asia/Taipei")))

    def capture(self, context: ForwardResearchObservationContext) -> CaptureResult:
        captured_at = self._now()
        _validate_capture_time(captured_at)
        _validate_forward_as_of_date(context.as_of_date, captured_at)
        observation = _build_observation(context, captured_at)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            self._ensure_schema(connection)
            existing = connection.execute(
                "SELECT * FROM forward_research_observations WHERE observation_id = ?",
                (observation.observation_id,),
            ).fetchone()
            if existing is not None:
                return CaptureResult(self._row_to_observation(existing), False)
            connection.execute(
                """
                INSERT INTO forward_research_observations (
                    observation_id, observation_version, symbol, company_name, industry,
                    as_of_date, captured_at, point_in_time_classification, research_price,
                    price_semantics, return_20d, return_60d, close_vs_sma20, close_vs_sma60,
                    rsi14, rel_return_20d, rel_return_60d, relative_alignment_status,
                    in_watchlist, long_term_research_available, historical_trends_available,
                    ai_research_available, swing_research_available, market_data_source,
                    data_date, observation_checksum
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _observation_values(observation),
            )
            connection.commit()
            return CaptureResult(observation, True)
        finally:
            connection.close()

    def count(self) -> int:
        if not self._db_path.exists():
            return 0
        connection = sqlite3.connect(self._db_path.as_uri() + "?mode=ro", uri=True)
        try:
            return int(connection.execute("SELECT COUNT(*) FROM forward_research_observations").fetchone()[0])
        finally:
            connection.close()

    def recent(self, limit: int = 5) -> tuple[ForwardResearchObservation, ...]:
        if limit < 1 or not self._db_path.exists():
            return ()
        connection = sqlite3.connect(self._db_path.as_uri() + "?mode=ro", uri=True)
        try:
            rows = connection.execute(
                "SELECT * FROM forward_research_observations ORDER BY captured_at DESC, observation_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return tuple(self._row_to_observation(row) for row in rows)
        finally:
            connection.close()

    def get(self, observation_id: str) -> ForwardResearchObservation | None:
        """Read an existing immutable observation without creating local storage."""
        if not self._db_path.exists():
            return None
        connection = sqlite3.connect(self._db_path.as_uri() + "?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT * FROM forward_research_observations WHERE observation_id = ?",
                (observation_id,),
            ).fetchone()
            return self._row_to_observation(row) if row is not None else None
        except sqlite3.OperationalError:
            return None
        finally:
            connection.close()

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS forward_research_observations (
                observation_id TEXT PRIMARY KEY,
                observation_version TEXT NOT NULL,
                symbol TEXT NOT NULL,
                company_name TEXT,
                industry TEXT,
                as_of_date TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                point_in_time_classification TEXT NOT NULL,
                research_price REAL NOT NULL,
                price_semantics TEXT NOT NULL,
                return_20d REAL NOT NULL,
                return_60d REAL NOT NULL,
                close_vs_sma20 REAL NOT NULL,
                close_vs_sma60 REAL NOT NULL,
                rsi14 REAL NOT NULL,
                rel_return_20d REAL,
                rel_return_60d REAL,
                relative_alignment_status TEXT NOT NULL,
                in_watchlist INTEGER NOT NULL,
                long_term_research_available INTEGER NOT NULL,
                historical_trends_available INTEGER NOT NULL,
                ai_research_available INTEGER NOT NULL,
                swing_research_available INTEGER NOT NULL,
                market_data_source TEXT NOT NULL,
                data_date TEXT NOT NULL,
                observation_checksum TEXT NOT NULL,
                UNIQUE (observation_version, symbol, as_of_date)
            )
            """
        )

    @staticmethod
    def _row_to_observation(row: tuple) -> ForwardResearchObservation:
        columns = (
            "observation_id", "observation_version", "symbol", "company_name", "industry", "as_of_date",
            "captured_at", "point_in_time_classification", "research_price", "price_semantics", "return_20d",
            "return_60d", "close_vs_sma20", "close_vs_sma60", "rsi14", "rel_return_20d", "rel_return_60d",
            "relative_alignment_status", "in_watchlist", "long_term_research_available",
            "historical_trends_available", "ai_research_available", "swing_research_available",
            "market_data_source", "data_date", "observation_checksum",
        )
        values = dict(zip(columns, row, strict=True))
        return ForwardResearchObservation(
            **{
                **values,
                "as_of_date": date.fromisoformat(values["as_of_date"]),
                "captured_at": datetime.fromisoformat(values["captured_at"]),
                "data_date": date.fromisoformat(values["data_date"]),
                **{key: bool(values[key]) for key in (
                    "in_watchlist", "long_term_research_available", "historical_trends_available",
                    "ai_research_available", "swing_research_available",
                )},
            }
        )


def _build_observation(context: ForwardResearchObservationContext, captured_at: datetime) -> ForwardResearchObservation:
    observation_id = deterministic_observation_id(context.symbol, context.as_of_date)
    payload = {
        **asdict(context),
        "as_of_date": context.as_of_date.isoformat(),
        "data_date": (context.data_date or context.as_of_date).isoformat(),
        "observation_id": observation_id,
        "observation_version": FORWARD_RESEARCH_OBSERVATION_VERSION,
        "price_semantics": PRICE_SEMANTICS,
        "point_in_time_classification": POINT_IN_TIME_CLASSIFICATION,
    }
    checksum = _checksum(payload)
    return ForwardResearchObservation(
        observation_id=observation_id,
        observation_version=FORWARD_RESEARCH_OBSERVATION_VERSION,
        symbol=context.symbol.strip().upper(),
        company_name=context.company_name,
        industry=context.industry,
        as_of_date=context.as_of_date,
        captured_at=captured_at,
        point_in_time_classification=POINT_IN_TIME_CLASSIFICATION,
        research_price=context.research_price,
        price_semantics=PRICE_SEMANTICS,
        return_20d=context.return_20d,
        return_60d=context.return_60d,
        close_vs_sma20=context.close_vs_sma20,
        close_vs_sma60=context.close_vs_sma60,
        rsi14=context.rsi14,
        rel_return_20d=context.rel_return_20d,
        rel_return_60d=context.rel_return_60d,
        relative_alignment_status=context.relative_alignment_status,
        in_watchlist=context.in_watchlist,
        long_term_research_available=context.long_term_research_available,
        historical_trends_available=context.historical_trends_available,
        ai_research_available=context.ai_research_available,
        swing_research_available=context.swing_research_available,
        market_data_source=context.market_data_source,
        data_date=context.data_date or context.as_of_date,
        observation_checksum=checksum,
    )


def deterministic_observation_id(symbol: str, as_of_date: date) -> str:
    identity = f"{FORWARD_RESEARCH_OBSERVATION_VERSION}|{symbol.strip().upper()}|{as_of_date.isoformat()}"
    return "forward_research_observation_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


def _canonical_price_bars(series: HistoricalPriceSeries) -> tuple[tuple[date, float], ...]:
    seen_dates: set[date] = set()
    result = []
    for bar in sorted(series.bars, key=lambda item: item.trading_date):
        if bar.trading_date in seen_dates:
            raise ForwardResearchObservationError("本地研究價格資料存在重複交易日。")
        seen_dates.add(bar.trading_date)
        price = research_price(bar)
        if price is None:
            continue
        result.append((bar.trading_date, price))
    return tuple(result)


def _rsi14(prices: list[float]) -> float:
    deltas = [prices[index] - prices[index - 1] for index in range(1, len(prices))]
    average_gain = sum(max(delta, 0.0) for delta in deltas) / 14
    average_loss = sum(abs(min(delta, 0.0)) for delta in deltas) / 14
    if average_gain == 0.0 and average_loss == 0.0:
        return 50.0
    if average_loss == 0.0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + average_gain / average_loss)


def _observation_values(observation: ForwardResearchObservation) -> tuple[object, ...]:
    return (
        observation.observation_id, observation.observation_version, observation.symbol, observation.company_name,
        observation.industry, observation.as_of_date.isoformat(), observation.captured_at.isoformat(),
        observation.point_in_time_classification, observation.research_price, observation.price_semantics,
        observation.return_20d, observation.return_60d, observation.close_vs_sma20, observation.close_vs_sma60,
        observation.rsi14, observation.rel_return_20d, observation.rel_return_60d,
        observation.relative_alignment_status, int(observation.in_watchlist), int(observation.long_term_research_available),
        int(observation.historical_trends_available), int(observation.ai_research_available),
        int(observation.swing_research_available), observation.market_data_source, observation.data_date.isoformat(),
        observation.observation_checksum,
    )


def _checksum(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_capture_time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ForwardResearchObservationError("captured_at 必須是含時區的實際時間。")
    if value.date() < FORWARD_DATASET_START_DATE:
        raise ForwardResearchObservationError("Forward Observation V0 不接受 2026-08-29 前的回填。")


def _validate_forward_as_of_date(as_of_date: date, captured_at: datetime) -> None:
    if as_of_date.year < FORWARD_DATASET_START_DATE.year:
        raise ForwardResearchObservationError("本地資料日期早於 Forward Observation V0 的允許起點。")
    if as_of_date > captured_at.date():
        raise ForwardResearchObservationError("本地資料日期不可晚於實際擷取日期。")
    expected_latest_date = _expected_latest_market_date(captured_at.date())
    if as_of_date < expected_latest_date:
        raise ForwardResearchObservationError("市場資料過舊，請先更新本地市場資料後再儲存。")


def _require_finite(value: float, field: str) -> None:
    if not math.isfinite(float(value)):
        raise ForwardResearchObservationError(f"{field} 必須是有限數值。")


def _optional_text(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _latest_valid_market_date(symbol: str, *, db_path: Path | str | None) -> date | None:
    try:
        series = load_live_historical_price_series(symbol, db_path=db_path)
    except ForwardResearchObservationError:
        return None
    bars = _canonical_price_bars(series)
    return bars[-1][0] if bars else None


def _expected_latest_market_date(capture_date: date) -> date:
    value = capture_date - timedelta(days=1)
    while value.weekday() >= 5:
        value -= timedelta(days=1)
    return value
