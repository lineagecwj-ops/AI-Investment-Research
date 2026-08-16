import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from datetime import datetime
from datetime import timezone
from enum import StrEnum
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import FilesystemTechnicalCloseSeriesStore
from market_inputs import MarketArtifactCorruptionError
from market_inputs import MarketArtifactNotFoundError
from market_inputs import MarketArtifactSaveResult
from market_inputs import MarketArtifactSaveStatus
from market_inputs import MarketArtifactStoreError
from market_inputs import MarketInputValidationError
from market_inputs import MarketSourceUnavailableError
from market_inputs import ProductionMarketInputConfig
from market_inputs import ProductionMarketInputMode
from market_inputs import ProductionTechnicalMarketInputResult
from market_inputs import ProductionTechnicalMarketInputService
from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseObservation
from market_inputs import TechnicalCloseObservationSeries
from market_inputs import TechnicalCloseSeriesArtifactIdentity
from market_inputs import TechnicalCloseSeriesRequest
from market_inputs import YAHOO_FINANCE_PROVIDER_ID_V1
from market_inputs import YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1


class FakeSource:
    def __init__(self, series=None, exception=None):
        self.series = series
        self.exception = exception
        self.fetch_call_count = 0
        self.last_request = None

    def fetch(self, request):
        self.fetch_call_count += 1
        self.last_request = request
        if self.exception is not None:
            raise self.exception
        return self.series


class FakeStore:
    def __init__(self, save_result=None, get_result=None, save_exception=None, get_exception=None):
        self.save_result = save_result
        self.get_result = get_result
        self.save_exception = save_exception
        self.get_exception = get_exception
        self.save_call_count = 0
        self.get_call_count = 0
        self.last_saved_series = None
        self.last_get_identity = None

    def save(self, series):
        self.save_call_count += 1
        self.last_saved_series = series
        if self.save_exception is not None:
            raise self.save_exception
        return self.save_result

    def get(self, identity):
        self.get_call_count += 1
        self.last_get_identity = identity
        if self.get_exception is not None:
            raise self.get_exception
        return self.get_result


class ProductionTechnicalMarketInputServiceTestCase(unittest.TestCase):

    def request(self):
        return TechnicalCloseSeriesRequest(
            symbol="2330.TW",
            provider_symbol="2330.TW",
            valuation_date=date(2026, 8, 14),
            start_date=date(2026, 5, 1),
            timezone="Asia/Taipei",
            close_basis=TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            provider=YAHOO_FINANCE_PROVIDER_ID_V1,
        )

    def observation(self, market_session_date=date(2026, 8, 14), technical_close=100.25):
        return TechnicalCloseObservation(
            market_session_date=market_session_date,
            technical_close=technical_close,
        )

    def series(self, **overrides):
        values = {
            "symbol": "2330.TW",
            "provider": YAHOO_FINANCE_PROVIDER_ID_V1,
            "provider_symbol": "2330.TW",
            "timezone": "Asia/Taipei",
            "close_basis": TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            "valuation_date": date(2026, 8, 14),
            "observations": (
                self.observation(date(2026, 8, 12), 98.0),
                self.observation(date(2026, 8, 13), 99.5),
                self.observation(date(2026, 8, 14), 100.25),
            ),
            "fetched_at": datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
            "producer_version": YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1,
        }
        values.update(overrides)
        return TechnicalCloseObservationSeries(**values)

    def identity(self, series):
        return TechnicalCloseSeriesArtifactIdentity.from_series(series)

    def save_result(self, series, status=MarketArtifactSaveStatus.INSERTED):
        return MarketArtifactSaveResult(
            status=status,
            identity=self.identity(series),
            relative_path=Path("yahoo_finance_v1/2330.tw/2026-08-14/artifact.json"),
        )

    def service(self, source=None, store=None):
        series = self.series()
        return ProductionTechnicalMarketInputService(
            source=source or FakeSource(series),
            store=store or FakeStore(save_result=self.save_result(series), get_result=series),
        )

    def test_result_is_frozen_and_validates_fresh_and_replay_invariants(self):
        series = self.series()
        fresh = ProductionTechnicalMarketInputResult(
            mode=ProductionMarketInputMode.FRESH,
            series=series,
            artifact_identity=self.identity(series),
            save_result=self.save_result(series),
        )
        replay = ProductionTechnicalMarketInputResult(
            mode=ProductionMarketInputMode.REPLAY,
            series=series,
            artifact_identity=self.identity(series),
            save_result=None,
        )

        with self.assertRaises(FrozenInstanceError):
            fresh.mode = ProductionMarketInputMode.REPLAY
        self.assertEqual(replay.mode, ProductionMarketInputMode.REPLAY)
        with self.assertRaisesRegex(MarketInputValidationError, "Fresh result requires"):
            ProductionTechnicalMarketInputResult(
                mode=ProductionMarketInputMode.FRESH,
                series=series,
                artifact_identity=self.identity(series),
                save_result=None,
            )
        with self.assertRaisesRegex(MarketInputValidationError, "Replay result must not"):
            ProductionTechnicalMarketInputResult(
                mode=ProductionMarketInputMode.REPLAY,
                series=series,
                artifact_identity=self.identity(series),
                save_result=self.save_result(series),
            )

    def test_result_mode_requires_exact_production_market_input_mode(self):
        class OtherMode(StrEnum):
            FRESH = "FRESH"

        series = self.series()
        accepted_cases = (
            (ProductionMarketInputMode.FRESH, self.save_result(series)),
            (ProductionMarketInputMode.REPLAY, None),
        )
        for mode, save_result in accepted_cases:
            with self.subTest(mode=mode):
                result = ProductionTechnicalMarketInputResult(
                    mode=mode,
                    series=series,
                    artifact_identity=self.identity(series),
                    save_result=save_result,
                )
                self.assertIs(result.mode, mode)

        rejected_modes = ("FRESH", "REPLAY", "fresh", "replay", 1, True, None, OtherMode.FRESH, object())
        for mode in rejected_modes:
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(MarketInputValidationError, "mode must be ProductionMarketInputMode"):
                    ProductionTechnicalMarketInputResult(
                        mode=mode,
                        series=series,
                        artifact_identity=self.identity(series),
                        save_result=self.save_result(series),
                    )

    def test_constructor_accepts_protocol_objects_and_rejects_missing_methods(self):
        self.assertIsInstance(self.service(), ProductionTechnicalMarketInputService)
        with self.assertRaisesRegex(MarketInputValidationError, "source must implement"):
            ProductionTechnicalMarketInputService(source=object(), store=FakeStore())
        with self.assertRaisesRegex(MarketInputValidationError, "store must implement"):
            ProductionTechnicalMarketInputService(source=FakeSource(), store=object())

    def test_resolve_fresh_success_inserted_calls_fetch_and_save_once(self):
        series = self.series()
        source = FakeSource(series)
        store = FakeStore(save_result=self.save_result(series))

        result = ProductionTechnicalMarketInputService(source=source, store=store).resolve_fresh(self.request())

        self.assertEqual(result.mode, ProductionMarketInputMode.FRESH)
        self.assertEqual(result.series, series)
        self.assertEqual(result.artifact_identity, self.identity(series))
        self.assertEqual(result.save_result.status, MarketArtifactSaveStatus.INSERTED)
        self.assertEqual(source.fetch_call_count, 1)
        self.assertEqual(store.save_call_count, 1)
        self.assertEqual(store.get_call_count, 0)
        self.assertEqual(store.last_saved_series, series)

    def test_resolve_fresh_success_idempotent_keeps_newly_fetched_series(self):
        series = self.series(fetched_at=datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc))
        source = FakeSource(series)
        store = FakeStore(save_result=self.save_result(series, MarketArtifactSaveStatus.IDEMPOTENT))

        result = ProductionTechnicalMarketInputService(source=source, store=store).resolve_fresh(self.request())

        self.assertEqual(result.mode, ProductionMarketInputMode.FRESH)
        self.assertEqual(result.series.fetched_at, series.fetched_at)
        self.assertEqual(result.save_result.status, MarketArtifactSaveStatus.IDEMPOTENT)
        self.assertEqual(source.fetch_call_count, 1)
        self.assertEqual(store.save_call_count, 1)
        self.assertEqual(store.get_call_count, 0)

    def test_resolve_fresh_rejects_wrong_request_type_without_calls(self):
        source = FakeSource(self.series())
        store = FakeStore(save_result=self.save_result(self.series()))

        with self.assertRaisesRegex(MarketInputValidationError, "request must be"):
            ProductionTechnicalMarketInputService(source=source, store=store).resolve_fresh({"symbol": "2330.TW"})

        self.assertEqual(source.fetch_call_count, 0)
        self.assertEqual(store.save_call_count, 0)
        self.assertEqual(store.get_call_count, 0)

    def test_resolve_fresh_rejects_source_wrong_type_before_save(self):
        source = FakeSource(object())
        store = FakeStore()

        with self.assertRaisesRegex(MarketInputValidationError, "series must be"):
            ProductionTechnicalMarketInputService(source=source, store=store).resolve_fresh(self.request())

        self.assertEqual(source.fetch_call_count, 1)
        self.assertEqual(store.save_call_count, 0)
        self.assertEqual(store.get_call_count, 0)

    def test_resolve_fresh_rejects_source_output_mismatches_before_save(self):
        wrong_close_basis = self.series()
        object.__setattr__(wrong_close_basis, "close_basis", "WRONG_CLOSE_BASIS")
        cases = (
            ("symbol", self.series(symbol="NVDA"), "symbol"),
            ("provider_symbol", self.series(provider_symbol="NVDA"), "provider_symbol"),
            ("provider", self.series(provider="BOGUS_PROVIDER"), "provider"),
            ("valuation_date", self.series(valuation_date=date(2026, 8, 13)), "valuation_date"),
            ("timezone", self.series(timezone="UTC"), "timezone"),
            ("close_basis", wrong_close_basis, "close_basis"),
        )
        for label, series, expected_message in cases:
            with self.subTest(label=label):
                source = FakeSource(series)
                store = FakeStore()
                service = ProductionTechnicalMarketInputService(source=source, store=store)
                with self.assertRaisesRegex(MarketInputValidationError, expected_message):
                    service.resolve_fresh(self.request())
                self.assertEqual(store.save_call_count, 0)

    def test_resolve_fresh_source_failure_propagates_without_store_calls(self):
        error = MarketSourceUnavailableError("offline")
        source = FakeSource(exception=error)
        store = FakeStore()

        with self.assertRaises(MarketSourceUnavailableError):
            ProductionTechnicalMarketInputService(source=source, store=store).resolve_fresh(self.request())

        self.assertEqual(source.fetch_call_count, 1)
        self.assertEqual(store.save_call_count, 0)
        self.assertEqual(store.get_call_count, 0)

    def test_resolve_fresh_store_failure_propagates_without_success(self):
        series = self.series()
        source = FakeSource(series)
        store = FakeStore(save_exception=MarketArtifactStoreError("disk full"))

        with self.assertRaises(MarketArtifactStoreError):
            ProductionTechnicalMarketInputService(source=source, store=store).resolve_fresh(self.request())

        self.assertEqual(source.fetch_call_count, 1)
        self.assertEqual(store.save_call_count, 1)
        self.assertEqual(store.get_call_count, 0)

    def test_resolve_fresh_rejects_broken_save_result(self):
        series = self.series()
        wrong_identity = self.identity(self.series(symbol="NVDA", provider_symbol="NVDA"))
        cases = (
            ("wrong type", object(), "store.save must return"),
            (
                "wrong identity",
                MarketArtifactSaveResult(
                    status=MarketArtifactSaveStatus.INSERTED,
                    identity=wrong_identity,
                    relative_path=Path("wrong.json"),
                ),
                "store.save identity",
            ),
        )
        for label, save_result, message in cases:
            with self.subTest(label=label):
                source = FakeSource(series)
                store = FakeStore(save_result=save_result)
                with self.assertRaisesRegex(MarketInputValidationError, message):
                    ProductionTechnicalMarketInputService(source=source, store=store).resolve_fresh(self.request())

    def test_resolve_replay_success_calls_get_once_without_source_or_save(self):
        series = self.series()
        identity = self.identity(series)
        source = FakeSource(exception=AssertionError("must not fetch"))
        store = FakeStore(get_result=series)

        result = ProductionTechnicalMarketInputService(source=source, store=store).resolve_replay(identity)

        self.assertEqual(result.mode, ProductionMarketInputMode.REPLAY)
        self.assertEqual(result.series, series)
        self.assertEqual(result.artifact_identity, identity)
        self.assertIsNone(result.save_result)
        self.assertEqual(source.fetch_call_count, 0)
        self.assertEqual(store.get_call_count, 1)
        self.assertEqual(store.save_call_count, 0)
        self.assertEqual(store.last_get_identity, identity)

    def test_resolve_replay_rejects_wrong_identity_type_without_calls(self):
        source = FakeSource()
        store = FakeStore()

        with self.assertRaisesRegex(MarketInputValidationError, "identity must be"):
            ProductionTechnicalMarketInputService(source=source, store=store).resolve_replay("market_revision")

        self.assertEqual(source.fetch_call_count, 0)
        self.assertEqual(store.get_call_count, 0)
        self.assertEqual(store.save_call_count, 0)

    def test_resolve_replay_missing_fails_closed_without_fallback(self):
        source = FakeSource(exception=AssertionError("must not fetch"))
        store = FakeStore(get_result=None)

        with self.assertRaises(MarketArtifactNotFoundError):
            ProductionTechnicalMarketInputService(source=source, store=store).resolve_replay(self.identity(self.series()))

        self.assertEqual(source.fetch_call_count, 0)
        self.assertEqual(store.get_call_count, 1)
        self.assertEqual(store.save_call_count, 0)

    def test_resolve_replay_corruption_and_store_errors_propagate(self):
        cases = (
            MarketArtifactCorruptionError("bad artifact"),
            MarketArtifactStoreError("store unavailable"),
        )
        for error in cases:
            with self.subTest(error=type(error).__name__):
                source = FakeSource(exception=AssertionError("must not fetch"))
                store = FakeStore(get_exception=error)
                with self.assertRaises(type(error)):
                    ProductionTechnicalMarketInputService(source=source, store=store).resolve_replay(self.identity(self.series()))
                self.assertEqual(source.fetch_call_count, 0)
                self.assertEqual(store.save_call_count, 0)

    def test_resolve_replay_rejects_wrong_returned_type_and_identity(self):
        requested = self.series()
        wrong = self.series(symbol="NVDA", provider_symbol="NVDA")
        cases = (
            ("wrong type", object(), "series must be"),
            ("wrong identity", wrong, "Replay series identity"),
        )
        for label, get_result, message in cases:
            with self.subTest(label=label):
                source = FakeSource()
                store = FakeStore(get_result=get_result)
                with self.assertRaisesRegex(MarketInputValidationError, message):
                    ProductionTechnicalMarketInputService(source=source, store=store).resolve_replay(self.identity(requested))
                self.assertEqual(source.fetch_call_count, 0)
                self.assertEqual(store.save_call_count, 0)

    def test_cross_mode_fresh_inserted_then_replay_identity(self):
        series = self.series()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = FilesystemTechnicalCloseSeriesStore(ProductionMarketInputConfig.from_project_root(temp_dir))
            service = ProductionTechnicalMarketInputService(source=FakeSource(series), store=store)

            fresh = service.resolve_fresh(self.request())
            replay = service.resolve_replay(fresh.artifact_identity)

            self.assertEqual(fresh.save_result.status, MarketArtifactSaveStatus.INSERTED)
            self.assertEqual(replay.artifact_identity, fresh.artifact_identity)
            self.assertEqual(replay.series, series)

    def test_semantic_idempotent_fresh_repeat_then_replay_keeps_first_fetched_at(self):
        first = self.series(fetched_at=datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc))
        second = self.series(fetched_at=datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc))
        self.assertEqual(first.market_revision_id, second.market_revision_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            store = FilesystemTechnicalCloseSeriesStore(ProductionMarketInputConfig.from_project_root(temp_dir))
            first_result = ProductionTechnicalMarketInputService(source=FakeSource(first), store=store).resolve_fresh(self.request())
            second_result = ProductionTechnicalMarketInputService(source=FakeSource(second), store=store).resolve_fresh(self.request())
            replay = ProductionTechnicalMarketInputService(source=FakeSource(), store=store).resolve_replay(first_result.artifact_identity)

            self.assertEqual(first_result.save_result.status, MarketArtifactSaveStatus.INSERTED)
            self.assertEqual(second_result.save_result.status, MarketArtifactSaveStatus.IDEMPOTENT)
            self.assertEqual(second_result.series.fetched_at, second.fetched_at)
            self.assertEqual(replay.series.fetched_at, first.fetched_at)
            self.assertEqual(second_result.artifact_identity, first_result.artifact_identity)
            self.assertEqual(replay.artifact_identity, first_result.artifact_identity)

    def test_changed_market_revision_gets_new_identity(self):
        first = self.series()
        second = self.series(
            observations=(
                self.observation(date(2026, 8, 12), 98.0),
                self.observation(date(2026, 8, 13), 99.5),
                self.observation(date(2026, 8, 14), 101.25),
            )
        )
        self.assertNotEqual(first.market_revision_id, second.market_revision_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            store = FilesystemTechnicalCloseSeriesStore(ProductionMarketInputConfig.from_project_root(temp_dir))
            first_result = ProductionTechnicalMarketInputService(source=FakeSource(first), store=store).resolve_fresh(self.request())
            second_result = ProductionTechnicalMarketInputService(source=FakeSource(second), store=store).resolve_fresh(self.request())

            self.assertEqual(first_result.save_result.status, MarketArtifactSaveStatus.INSERTED)
            self.assertEqual(second_result.save_result.status, MarketArtifactSaveStatus.INSERTED)
            self.assertNotEqual(first_result.artifact_identity, second_result.artifact_identity)

    def test_no_auto_latest_or_concrete_runtime_boundary(self):
        self.assertEqual(tuple(item.value for item in ProductionMarketInputMode), ("FRESH", "REPLAY"))
        forbidden_api = ("resolve", "latest", "get_latest", "list", "scan", "resolve_latest")
        for name in forbidden_api:
            with self.subTest(name=name):
                self.assertFalse(hasattr(ProductionTechnicalMarketInputService, name))

        source = (SRC_PATH / "market_inputs" / "production_technical_market_input_service.py").read_text()
        forbidden_terms = (
            "YahooFinanceTechnicalCloseSeriesSource",
            "FilesystemTechnicalCloseSeriesStore",
            "ProductionMarketInputConfig",
            "yfinance",
            "pandas",
            "sqlite3",
            "risk_persistence",
            "features",
            "risk_evaluation",
            "portfolio_generation",
            "portfolio_sources",
            "dashboard",
            "scheduler",
            "RiskEvaluationInput",
            "RiskSignalProductionInput",
            "TechnicalFeatureBundle",
            "checksum",
        )
        for term in forbidden_terms:
            with self.subTest(term=term):
                self.assertNotIn(term, source)

    def test_public_api_exports_and_real_production_path_untouched(self):
        import market_inputs

        self.assertIs(market_inputs.ProductionTechnicalMarketInputService, ProductionTechnicalMarketInputService)
        self.assertIs(market_inputs.ProductionTechnicalMarketInputResult, ProductionTechnicalMarketInputResult)
        self.assertIs(market_inputs.MarketArtifactNotFoundError, MarketArtifactNotFoundError)
        self.assertFalse((PROJECT_ROOT / "data" / "production").exists())


if __name__ == "__main__":
    unittest.main()
