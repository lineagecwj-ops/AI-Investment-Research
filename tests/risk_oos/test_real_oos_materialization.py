import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database_config import DEFAULT_RESEARCH_MATERIALIZATION_VERSION
from features import FeatureCalculationContext
from features.calculators import PriceVolumePoint
from features.calculators import RSI14Calculator
from features.calculators import SMA20Calculator
from features.calculators import SMA60Calculator
from risk_oos import TECHNICAL_RISK_REAL_OOS_MATERIALIZER_VERSION
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskOOSSplitSpec
from risk_oos import TechnicalRiskRealOOSDatasetMaterializationError
from risk_oos import TechnicalRiskRealOOSDatasetMaterializationRequest
from risk_oos import TechnicalRiskRealOOSDatasetMaterializer
from targets import MaximumAdverseExcursion20DRegressionGenerator
from targets import MaximumAdverseExcursion60DRegressionGenerator
from targets import TargetCalculationContext
from targets import TargetPricePoint


class TechnicalRiskRealOOSMaterializationTestCase(unittest.TestCase):
    snapshot_id = "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1"
    snapshot_version = "v1"
    semantic_checksum = "semantic_checksum_for_real_oos_fixture"
    feature_set_id = "technical_risk_v1_required_features"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "research_fixture.db"
        self.manifest_path = self.root / "research_fixture_manifest.json"
        self.start = date(2020, 1, 1)
        self._create_research_db(symbols=("2330.TW",), days=235)
        self.before_sha = self._sha256(self.db_path)

    def request(self, **overrides):
        values = {
            "research_db_path": self.db_path,
            "research_manifest_path": self.manifest_path,
            "source_snapshot_id": self.snapshot_id,
            "source_snapshot_checksum": self.semantic_checksum,
            "symbols": ("2330.TW",),
            "analysis_start_date": self.start + timedelta(days=69),
            "analysis_end_date": self.start + timedelta(days=160),
            "split_specs": (
                TechnicalRiskOOSSplitSpec(
                    split_id="validation_2020",
                    split_role=TechnicalRiskOOSSplitRole.VALIDATION,
                    start_date=self.start + timedelta(days=69),
                    end_date=self.start + timedelta(days=150),
                ),
                TechnicalRiskOOSSplitSpec(
                    split_id="holdout_2020",
                    split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
                    start_date=self.start + timedelta(days=151),
                    end_date=self.start + timedelta(days=220),
                ),
            ),
            "dataset_spec_id": "technical_risk_real_oos_fixture",
            "dataset_spec_version": "v1",
            "feature_set_id": self.feature_set_id,
        }
        values.update(overrides)
        return TechnicalRiskRealOOSDatasetMaterializationRequest(**values)

    def materialize(self, **request_overrides):
        return TechnicalRiskRealOOSDatasetMaterializer().materialize(self.request(**request_overrides))

    def _create_research_db(self, *, symbols, days):
        if self.db_path.exists():
            self.db_path.unlink()
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE historical_prices (
                    symbol TEXT NOT NULL,
                    trading_date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    adjusted_close REAL,
                    volume INTEGER,
                    dividends REAL,
                    stock_splits REAL,
                    currency TEXT,
                    fetched_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE TABLE snapshot_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            fetched_at = datetime(2020, 1, 1, tzinfo=UTC).isoformat()
            for symbol in symbols:
                for index in range(days):
                    trading_date = self.start + timedelta(days=index)
                    close = 100.0 + index
                    connection.execute(
                        """
                        INSERT INTO historical_prices
                        (symbol, trading_date, open, high, low, close, adjusted_close,
                         volume, dividends, stock_splits, currency, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            symbol,
                            trading_date.isoformat(),
                            close,
                            close + 1,
                            close - 1,
                            close,
                            close,
                            1000 + index,
                            0.0,
                            0.0,
                            "TWD",
                            fetched_at,
                        ),
                    )
            metadata = {
                "snapshot_id": self.snapshot_id,
                "snapshot_version": self.snapshot_version,
                "materialization_version": DEFAULT_RESEARCH_MATERIALIZATION_VERSION,
                "semantic_checksum": self.semantic_checksum,
            }
            connection.executemany("INSERT INTO snapshot_metadata (key, value) VALUES (?, ?)", metadata.items())
            connection.commit()
        finally:
            connection.close()
        db_sha = self._sha256(self.db_path)
        self.manifest_path.write_text(
            json.dumps(
                {
                    "identity": {
                        "snapshot_id": self.snapshot_id,
                        "snapshot_version": self.snapshot_version,
                        "materialization_version": DEFAULT_RESEARCH_MATERIALIZATION_VERSION,
                    },
                    "semantic_checksum": {
                        "expected": self.semantic_checksum,
                        "materialized": self.semantic_checksum,
                        "recomputed": self.semantic_checksum,
                    },
                    "database": {"sha256": db_sha},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def _sha256(self, path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _price_points(self, symbol="2330.TW", days=235):
        return tuple(
            PriceVolumePoint(
                symbol=symbol,
                trading_date=self.start + timedelta(days=index),
                close=100.0 + index,
                volume=float(1000 + index),
            )
            for index in range(days)
        )

    def _target_points(self, symbol="2330.TW", days=235):
        return tuple(
            TargetPricePoint(symbol=symbol, trading_date=self.start + timedelta(days=index), price=100.0 + index)
            for index in range(days)
        )

    def test_materializes_real_oos_dataset_with_validation_and_holdout_rows(self):
        result = self.materialize()

        self.assertGreater(result.feature_observation_count, 60)
        self.assertGreater(result.mae20_artifact_count, 0)
        self.assertGreater(result.mae60_artifact_count, 0)
        self.assertGreater(result.split_counts["validation"], 0)
        self.assertGreater(result.split_counts["holdout"], 0)
        self.assertEqual(result.aligned_row_count, len(result.oos_dataset_result.included_rows))
        self.assertEqual(self.before_sha, self._sha256(self.db_path))

    def test_feature_values_match_existing_calculators(self):
        result = self.materialize()
        row = result.oos_dataset_result.included_rows[0]
        context = FeatureCalculationContext(
            snapshot_id=self.snapshot_id,
            snapshot_version=self.semantic_checksum,
            universe_id=self.feature_set_id,
            as_of_date=row.evaluation_date,
            calculation_id=row.observation_id,
        )
        points = self._price_points()

        self.assertEqual(row.as_of_close, 100.0 + (row.evaluation_date - self.start).days)
        self.assertEqual(row.sma20, SMA20Calculator(points).calculate(context).values[0]["feature_value"])
        self.assertEqual(row.sma60, SMA60Calculator(points).calculate(context).values[0]["feature_value"])
        self.assertEqual(row.rsi14, RSI14Calculator(points).calculate(context).values[0]["feature_value"])

    def test_mae_values_match_existing_generators(self):
        result = self.materialize()
        row = result.oos_dataset_result.included_rows[0]
        generator20 = MaximumAdverseExcursion20DRegressionGenerator(self._target_points())
        output20 = generator20.calculate(
            TargetCalculationContext(
                snapshot_id=self.snapshot_id,
                symbol=row.symbol,
                reference_date=row.evaluation_date,
                evaluation_window=20,
                target_version="v1",
                calculation_id=row.mae20_calculation_id,
            )
        )
        output60 = MaximumAdverseExcursion60DRegressionGenerator(self._target_points()).calculate(
            TargetCalculationContext(
                snapshot_id=self.snapshot_id,
                symbol=row.symbol,
                reference_date=row.evaluation_date,
                evaluation_window=60,
                target_version="v1",
                calculation_id=row.mae60_calculation_id,
            )
        )
        self.assertEqual(row.mae20_value, output20.target_value)
        self.assertEqual(row.mae60_value, output60.target_value)

    def test_dataset_identity_is_deterministic(self):
        first = self.materialize()
        second = self.materialize()

        self.assertEqual(first.oos_dataset_result.dataset_id, second.oos_dataset_result.dataset_id)
        self.assertEqual(first.oos_dataset_result.dataset_checksum, second.oos_dataset_result.dataset_checksum)
        self.assertEqual(first.oos_dataset_result.summary_counts, second.oos_dataset_result.summary_counts)

    def test_target_split_boundary_leakage_is_row_exclusion(self):
        result = self.materialize()

        self.assertGreater(result.excluded_split_leakage_count, 0)
        self.assertGreater(
            result.oos_dataset_result.summary_counts["excluded_excluded_target_crosses_split_boundary"],
            0,
        )

    def test_incomplete_mae_exclusions_are_row_level(self):
        self._create_research_db(symbols=("2317.TW",), days=225)
        request = self.request(
            symbols=("2317.TW",),
            analysis_start_date=self.start + timedelta(days=69),
            analysis_end_date=self.start + timedelta(days=210),
            split_specs=(
                TechnicalRiskOOSSplitSpec(
                    split_id="validation_2020",
                    split_role=TechnicalRiskOOSSplitRole.VALIDATION,
                    start_date=self.start + timedelta(days=69),
                    end_date=self.start + timedelta(days=150),
                ),
                TechnicalRiskOOSSplitSpec(
                    split_id="holdout_2020",
                    split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
                    start_date=self.start + timedelta(days=151),
                    end_date=self.start + timedelta(days=220),
                ),
            ),
        )

        result = TechnicalRiskRealOOSDatasetMaterializer().materialize(request)

        self.assertGreater(result.split_counts["validation"], 0)
        self.assertGreater(result.split_counts["holdout"], 0)
        self.assertGreater(result.excluded_incomplete_mae20_count, 0)
        self.assertGreater(result.excluded_incomplete_mae60_count, 0)

    def test_duplicate_raw_trading_date_fails_run(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """
                INSERT INTO historical_prices
                (symbol, trading_date, open, high, low, close, adjusted_close,
                 volume, dividends, stock_splits, currency, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("2330.TW", self.start.isoformat(), 1, 1, 1, 1, 1, 1, 0, 0, "TWD", datetime(2020, 1, 1, tzinfo=UTC).isoformat()),
            )
            connection.commit()
        finally:
            connection.close()
        db_sha = self._sha256(self.db_path)
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        payload["database"]["sha256"] = db_sha
        self.manifest_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

        with self.assertRaisesRegex(TechnicalRiskRealOOSDatasetMaterializationError, "Duplicate raw price observation"):
            self.materialize()

    def test_empty_symbols_fail_closed(self):
        with self.assertRaisesRegex(TechnicalRiskRealOOSDatasetMaterializationError, "symbols cannot be empty"):
            self.request(symbols=())

    def test_missing_required_split_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskRealOOSDatasetMaterializationError, "HOLDOUT"):
            self.request(
                split_specs=(
                    TechnicalRiskOOSSplitSpec(
                        split_id="validation_2020",
                        split_role=TechnicalRiskOOSSplitRole.VALIDATION,
                        start_date=self.start + timedelta(days=69),
                        end_date=self.start + timedelta(days=150),
                    ),
                )
            )

    def test_empty_validation_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskRealOOSDatasetMaterializationError, "No validation aligned rows"):
            self.materialize(
                split_specs=(
                    TechnicalRiskOOSSplitSpec(
                        split_id="validation_2020",
                        split_role=TechnicalRiskOOSSplitRole.VALIDATION,
                        start_date=self.start + timedelta(days=69),
                        end_date=self.start + timedelta(days=80),
                    ),
                    TechnicalRiskOOSSplitSpec(
                        split_id="holdout_2020",
                        split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
                        start_date=self.start + timedelta(days=151),
                        end_date=self.start + timedelta(days=220),
                    ),
                )
            )

    def test_empty_holdout_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskRealOOSDatasetMaterializationError, "No holdout aligned rows"):
            self.materialize(
                split_specs=(
                    TechnicalRiskOOSSplitSpec(
                        split_id="validation_2020",
                        split_role=TechnicalRiskOOSSplitRole.VALIDATION,
                        start_date=self.start + timedelta(days=69),
                        end_date=self.start + timedelta(days=180),
                    ),
                    TechnicalRiskOOSSplitSpec(
                        split_id="holdout_2020",
                        split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
                        start_date=self.start + timedelta(days=210),
                        end_date=self.start + timedelta(days=220),
                    ),
                )
            )

    def test_manifest_identity_mismatch_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskRealOOSDatasetMaterializationError, "identity verification failed"):
            self.materialize(source_snapshot_checksum="wrong_checksum")

    def test_production_path_is_rejected(self):
        with self.assertRaisesRegex(TechnicalRiskRealOOSDatasetMaterializationError, "data/production"):
            self.request(research_db_path=PROJECT_ROOT / "data" / "production" / "risk_artifacts.db")

    def test_source_boundary_excludes_network_and_production_runtime(self):
        source = (SRC_PATH / "risk_oos" / "real_oos_materialization.py").read_text(encoding="utf-8")

        forbidden = (
            "yfinance",
            "Yahoo",
            "production_runtime",
            "ProductionPolicyPin",
            "threshold grid",
            "find_best",
            "optimize",
            "sqlite3.connect",
            "write_text",
        )
        for term in forbidden:
            self.assertNotIn(term, source)
        self.assertIn("connect_read_only", (SRC_PATH / "research_data_store.py").read_text(encoding="utf-8"))
        self.assertEqual(TECHNICAL_RISK_REAL_OOS_MATERIALIZER_VERSION, "technical_risk_real_oos_materializer_v1")


if __name__ == "__main__":
    unittest.main()
