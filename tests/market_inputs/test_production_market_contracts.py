import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import MARKET_INPUT_ARTIFACT_ROOT_ALIAS
from market_inputs import MarketArtifactConflictError
from market_inputs import MarketArtifactCorruptionError
from market_inputs import MarketArtifactSaveResult
from market_inputs import MarketArtifactSaveStatus
from market_inputs import MarketArtifactStoreError
from market_inputs import MarketInputError
from market_inputs import MarketInputValidationError
from market_inputs import MarketSourceError
from market_inputs import MarketSourceUnavailableError
from market_inputs import ProductionMarketInputConfig
from market_inputs import ProductionMarketInputMode
from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseObservation
from market_inputs import TechnicalCloseObservationSeries
from market_inputs import TechnicalCloseSeriesArtifactIdentity
from market_inputs import TechnicalCloseSeriesRequest
from market_inputs import TechnicalCloseSeriesSource
from market_inputs import TechnicalCloseSeriesStore
from market_inputs import TechnicalMarketDataProvider
from market_inputs import YAHOO_FINANCE_PROVIDER_ID_V1


class ProductionMarketContractsTestCase(unittest.TestCase):

    def request(self, **overrides):
        values = {
            "symbol": "2330.TW",
            "provider_symbol": "2330.TW",
            "valuation_date": date(2026, 8, 14),
            "start_date": date(2026, 1, 1),
            "timezone": "Asia/Taipei",
            "close_basis": TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            "provider": TechnicalMarketDataProvider.YAHOO_FINANCE_V1,
        }
        values.update(overrides)
        return TechnicalCloseSeriesRequest(**values)

    def series(self, **overrides):
        values = {
            "symbol": "2330.TW",
            "provider": YAHOO_FINANCE_PROVIDER_ID_V1,
            "provider_symbol": "2330.TW",
            "timezone": "Asia/Taipei",
            "close_basis": TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            "valuation_date": date(2026, 8, 14),
            "observations": (
                TechnicalCloseObservation(date(2026, 8, 13), 100.0),
                TechnicalCloseObservation(date(2026, 8, 14), 101.0),
            ),
            "fetched_at": datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
        }
        values.update(overrides)
        return TechnicalCloseObservationSeries(**values)

    def identity(self, **overrides):
        values = {
            "provider": TechnicalMarketDataProvider.YAHOO_FINANCE_V1,
            "symbol": "2330.TW",
            "provider_symbol": "2330.TW",
            "valuation_date": date(2026, 8, 14),
            "market_revision_id": "market_revision_" + "a" * 64,
        }
        values.update(overrides)
        return TechnicalCloseSeriesArtifactIdentity(**values)

    def test_provider_enum_exact_versioned_identifier(self):
        self.assertEqual(TechnicalMarketDataProvider.YAHOO_FINANCE_V1.value, "YAHOO_FINANCE_V1")
        self.assertEqual(YAHOO_FINANCE_PROVIDER_ID_V1, "YAHOO_FINANCE_V1")

    def test_request_is_frozen_and_validates_dates_range_timezone_and_symbols(self):
        request = self.request()
        self.assertEqual(request.provider.value, "YAHOO_FINANCE_V1")
        self.assertEqual(request.close_basis.value, "TECHNICAL_CLOSE_ADJUSTED_FIRST_V1")

        with self.assertRaises(FrozenInstanceError):
            request.symbol = "NVDA"
        with self.assertRaisesRegex(MarketInputValidationError, "symbol"):
            self.request(symbol="")
        with self.assertRaisesRegex(MarketInputValidationError, "provider_symbol"):
            self.request(provider_symbol="")
        with self.assertRaisesRegex(MarketInputValidationError, "date"):
            self.request(valuation_date=datetime(2026, 8, 14, tzinfo=timezone.utc))
        with self.assertRaisesRegex(MarketInputValidationError, "date"):
            self.request(start_date=datetime(2026, 1, 1, tzinfo=timezone.utc))
        with self.assertRaisesRegex(MarketInputValidationError, "start_date"):
            self.request(start_date=date(2026, 8, 15))
        with self.assertRaisesRegex(MarketInputValidationError, "timezone"):
            self.request(timezone="Asia/Taipeii")
        with self.assertRaisesRegex(MarketInputValidationError, "provider"):
            self.request(provider="YAHOO")
        with self.assertRaisesRegex(MarketInputValidationError, "close_basis"):
            self.request(close_basis="RAW_CLOSE_V1")

    def test_request_does_not_know_technical_feature_windows(self):
        request_fields = set(TechnicalCloseSeriesRequest.__dataclass_fields__)

        self.assertNotIn("sma20", request_fields)
        self.assertNotIn("sma60", request_fields)
        self.assertNotIn("rsi14", request_fields)
        self.assertNotIn("feature_window", request_fields)

    def test_mode_enum_is_exact_without_auto_latest_or_stale_fallback(self):
        self.assertEqual(tuple(item.value for item in ProductionMarketInputMode), ("FRESH", "REPLAY"))
        self.assertNotIn("AUTO", ProductionMarketInputMode.__members__)
        self.assertNotIn("LATEST", ProductionMarketInputMode.__members__)
        self.assertNotIn("STALE_FALLBACK", ProductionMarketInputMode.__members__)

    def test_artifact_identity_is_frozen_and_validates_revision_format(self):
        identity = self.identity()

        self.assertEqual(identity.market_revision_id, "market_revision_" + "a" * 64)
        with self.assertRaises(FrozenInstanceError):
            identity.symbol = "NVDA"
        with self.assertRaisesRegex(MarketInputValidationError, "market_revision_id"):
            self.identity(market_revision_id="market_revision_wrong")
        with self.assertRaisesRegex(MarketInputValidationError, "market_revision_id"):
            self.identity(market_revision_id="market_revision_" + "A" * 64)
        with self.assertRaisesRegex(MarketInputValidationError, "date"):
            self.identity(valuation_date=datetime(2026, 8, 14, tzinfo=timezone.utc))

    def test_identity_from_series_uses_revision_without_creating_another_checksum(self):
        series = self.series()

        identity = TechnicalCloseSeriesArtifactIdentity.from_series(series)

        self.assertEqual(identity.provider, TechnicalMarketDataProvider.YAHOO_FINANCE_V1)
        self.assertEqual(identity.symbol, series.symbol)
        self.assertEqual(identity.provider_symbol, series.provider_symbol)
        self.assertEqual(identity.valuation_date, series.valuation_date)
        self.assertEqual(identity.market_revision_id, series.market_revision_id)
        self.assertFalse(hasattr(identity, "artifact_checksum"))

    def test_config_derives_canonical_artifact_root_without_mkdir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            config = ProductionMarketInputConfig.from_project_root(project_root)

            self.assertEqual(config.project_root, project_root.resolve())
            self.assertEqual(config.artifact_root, project_root.resolve() / "data" / "production" / "market_inputs")
            self.assertEqual(config.artifact_root_alias, MARKET_INPUT_ARTIFACT_ROOT_ALIAS)
            self.assertFalse(config.artifact_root.exists())

    def test_config_rejects_missing_or_file_project_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            missing = project_root / "missing"
            file_root = project_root / "file.txt"
            file_root.write_text("not a dir", encoding="utf-8")

            with self.assertRaisesRegex(MarketInputValidationError, "exist"):
                ProductionMarketInputConfig.from_project_root(missing)
            with self.assertRaisesRegex(MarketInputValidationError, "directory"):
                ProductionMarketInputConfig.from_project_root(file_root)

    def test_artifact_path_is_safe_deterministic_and_collision_resistant(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ProductionMarketInputConfig.from_project_root(temp_dir)
            identity = self.identity(symbol="../evil", provider_symbol="a/b")
            path = config.artifact_path(identity)
            relative = config.artifact_relative_path(identity)

            self.assertEqual(path, config.artifact_root / relative)
            self.assertFalse(relative.is_absolute())
            self.assertEqual(relative.parts[0], "yahoo_finance_v1")
            self.assertEqual(relative.parts[2], "2026-08-14")
            self.assertEqual(relative.parts[3], identity.market_revision_id + ".json")
            self.assertNotIn("..", relative.parts)
            self.assertNotIn("/", relative.parts[1])
            self.assertNotIn("\\", relative.parts[1])
            self.assertEqual(relative, config.artifact_relative_path(identity))

    def test_path_cases_cover_provider_symbols_unicode_and_revision_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ProductionMarketInputConfig.from_project_root(temp_dir)
            cases = (
                ("2330.TW", "2330.TW"),
                ("2330.TWO", "2330.TWO"),
                ("NVDA", "NVDA"),
                ("台積電", "2330.TW"),
                ("a/b", "a\\b"),
                ("../evil", "/absolute"),
            )
            paths = {
                config.artifact_relative_path(self.identity(symbol=symbol, provider_symbol=provider_symbol))
                for symbol, provider_symbol in cases
            }

            self.assertEqual(len(paths), len(cases))
            for path in paths:
                self.assertEqual(path.suffix, ".json")
                self.assertEqual(path.name, "market_revision_" + "a" * 64 + ".json")
                self.assertTrue(all(part and "/" not in part and "\\" not in part for part in path.parts))

    def test_different_revision_uses_different_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ProductionMarketInputConfig.from_project_root(temp_dir)

            first = config.artifact_relative_path(self.identity(market_revision_id="market_revision_" + "a" * 64))
            second = config.artifact_relative_path(self.identity(market_revision_id="market_revision_" + "b" * 64))

            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, second.parent)

    def test_save_status_and_result_contract_excludes_update_replace(self):
        self.assertEqual(tuple(item.value for item in MarketArtifactSaveStatus), ("INSERTED", "IDEMPOTENT"))
        self.assertNotIn("UPDATED", MarketArtifactSaveStatus.__members__)
        self.assertNotIn("REPLACED", MarketArtifactSaveStatus.__members__)

        result = MarketArtifactSaveResult(
            status=MarketArtifactSaveStatus.INSERTED,
            identity=self.identity(),
            relative_path=Path("yahoo_finance_v1/symbol/2026-08-14/market_revision_" + "a" * 64 + ".json"),
        )
        self.assertEqual(result.status, MarketArtifactSaveStatus.INSERTED)
        with self.assertRaises(FrozenInstanceError):
            result.status = MarketArtifactSaveStatus.IDEMPOTENT
        with self.assertRaisesRegex(MarketInputValidationError, "relative"):
            MarketArtifactSaveResult(
                status=MarketArtifactSaveStatus.INSERTED,
                identity=self.identity(),
                relative_path=Path("/absolute/path.json"),
            )

    def test_source_and_store_protocols_are_structural(self):
        class StaticSource:
            def fetch(self, request):
                return self.series

        class StaticStore:
            def save(self, series):
                return self.result

            def get(self, identity):
                return None

        self.assertIsInstance(StaticSource(), TechnicalCloseSeriesSource)
        self.assertIsInstance(StaticStore(), TechnicalCloseSeriesStore)

    def test_store_get_missing_contract_is_none(self):
        class StaticStore:
            def save(self, series):
                raise AssertionError("not used")

            def get(self, identity):
                return None

        self.assertIsNone(StaticStore().get(self.identity()))

    def test_error_hierarchy_and_safe_message_fields(self):
        self.assertTrue(issubclass(MarketSourceError, MarketInputError))
        self.assertTrue(issubclass(MarketSourceUnavailableError, MarketSourceError))
        self.assertTrue(issubclass(MarketArtifactStoreError, MarketInputError))
        self.assertTrue(issubclass(MarketArtifactConflictError, MarketArtifactStoreError))
        self.assertTrue(issubclass(MarketArtifactCorruptionError, MarketArtifactStoreError))

        error = MarketSourceUnavailableError("provider unavailable for YAHOO_FINANCE_V1 2330.TW 2026-08-14")
        self.assertNotIn("[", str(error))
        self.assertNotIn("{", str(error))

    def test_no_network_filesystem_db_or_feature_boundary(self):
        source = "\n".join(path.read_text() for path in sorted((SRC_PATH / "market_inputs").glob("*.py")))

        forbidden = (
            "yfinance",
            "requests",
            "urllib",
            "LiveDataStore",
            "ResearchDataStore",
            "RiskEvaluationInput",
            "generation_key",
            "calculation_id",
            "sqlite3",
            "technical_indicator_service",
            "SMA20",
            "SMA60",
            "RSI14",
            "write_text",
            "open(",
            "mkdir",
            "replace(",
            "rename(",
        )
        for term in forbidden:
            self.assertNotIn(term, source)

    def test_real_production_directory_not_created(self):
        self.assertFalse((PROJECT_ROOT / "data" / "production").exists())


if __name__ == "__main__":
    unittest.main()
