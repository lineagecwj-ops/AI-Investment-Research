import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import FilesystemTechnicalCloseSeriesStore
from market_inputs import ProductionMarketInputConfig
from market_inputs import ProductionMarketInputMode
from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseObservation
from market_inputs import TechnicalCloseObservationSeries
from market_inputs import TechnicalCloseSeriesArtifactIdentity
from market_inputs import YAHOO_FINANCE_PROVIDER_ID_V1
from market_inputs import YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1
from production_runtime import ProductionTechnicalRiskRuntime
from production_runtime import ProductionTechnicalRiskRuntimeError
from production_runtime import ProductionTechnicalRiskRuntimeRequest
from risk import RiskSeverity
from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1
from risk_evaluation import TECH_RISK_REASON_MAPPING_V1
from risk_evaluation import TECH_RISK_REQUIRED_FEATURE_IDS_V1
from risk_evaluation import TECH_RISK_SEVERITY_MAPPING_V1
from risk_evaluation import ProductionTechnicalRiskPolicy
from risk_evaluation import ProductionTechnicalRiskPredicateId
from risk_evaluation import ProductionTechnicalRiskReasonCode
from risk_evaluation import ProductionTechnicalRiskRule
from risk_evaluation import ProductionTechnicalRiskThresholdDimension
from risk_evaluation import ProductionTechnicalRiskThresholdDimensionId
from risk_evaluation import ProductionTechnicalRiskThresholdOperator


class FakeSource:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.requests = []

    def fetch(self, request):
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("source failed")
        return series(
            symbol=request.symbol,
            provider_symbol=request.provider_symbol,
            valuation_date=request.valuation_date,
            close_basis=request.close_basis,
        )


class WrongSymbolMaterializer:
    def materialize(self, series_value):
        from market_inputs import ProductionTechnicalFeatureMaterializer

        bundle = ProductionTechnicalFeatureMaterializer().materialize(series_value)
        return replace(bundle, symbol="MISSING.TW", feature_bundle_checksum=None)


def policy():
    def dimension(dimension_id, value):
        return ProductionTechnicalRiskThresholdDimension(
            dimension_id=dimension_id,
            operator=ProductionTechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            canonical_value=Decimal(value),
        )

    return ProductionTechnicalRiskPolicy(
        policy_id=None,
        policy_version=PRODUCTION_TECHNICAL_RISK_POLICY_V1,
        policy_checksum=None,
        technical_policy_version="TECH_RISK_POLICY_V1_RESEARCH_FREEZE",
        source_research_freeze_id="freeze_001",
        source_research_freeze_checksum="freeze_checksum_001",
        candidate_id="candidate_a",
        candidate_version="v1",
        candidate_structural_checksum="candidate_checksum_001",
        rules=(
            ProductionTechnicalRiskRule(
                rule_id="HIGH",
                rule_priority=10,
                severity=RiskSeverity.HIGH,
                required_predicates=(
                    ProductionTechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                    ProductionTechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                ),
                optional_confirmation_predicates=(),
                reason_codes=(ProductionTechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,),
            ),
            ProductionTechnicalRiskRule(
                rule_id="MEDIUM",
                rule_priority=20,
                severity=RiskSeverity.MEDIUM,
                required_predicates=(ProductionTechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,),
                optional_confirmation_predicates=(ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,),
                reason_codes=(ProductionTechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,),
            ),
        ),
        threshold_set_id="threshold_set_001",
        threshold_set_version="v1",
        threshold_set_checksum="threshold_checksum_001",
        threshold_dimensions=(
            dimension(ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.025"),
            dimension(ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.05"),
            dimension(ProductionTechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.02"),
            dimension(ProductionTechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40"),
        ),
        required_feature_ids=TECH_RISK_REQUIRED_FEATURE_IDS_V1,
        derived_evidence_version="TECH_RISK_DERIVED_EVIDENCE_V1",
        numeric_context_version="TECH_RISK_DECIMAL_CONTEXT_V1",
        severity_mapping_version=TECH_RISK_SEVERITY_MAPPING_V1,
        reason_mapping_version=TECH_RISK_REASON_MAPPING_V1,
    )


def observation(day, close):
    return TechnicalCloseObservation(market_session_date=day, technical_close=close)


def series(*, symbol="2330.TW", provider_symbol="2330.TW", valuation_date=date(2026, 8, 14), close_basis=None):
    start = valuation_date - timedelta(days=59)
    return TechnicalCloseObservationSeries(
        symbol=symbol,
        provider=YAHOO_FINANCE_PROVIDER_ID_V1,
        provider_symbol=provider_symbol,
        timezone="Asia/Taipei",
        close_basis=close_basis or TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
        valuation_date=valuation_date,
        observations=tuple(observation(start + timedelta(days=index), 100.0 + index) for index in range(60)),
        fetched_at=datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
        producer_version=YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1,
    )


class ProductionTechnicalRiskRuntimeTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "risk.db"
        self.policy = policy()
        self.created_at = datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp_dir.cleanup()

    def portfolio_payload(self, positions):
        return {
            "schema_version": "1",
            "portfolio_id": "portfolio_001",
            "snapshot_id": "snapshot_001",
            "as_of_date": "2026-08-14",
            "valuation_date": "2026-08-14",
            "snapshot_created_at": "2026-08-16T09:00:00+00:00",
            "source_lineage": {"source_type": "local_json_portfolio_snapshot", "source_version": "1"},
            "positions": positions,
        }

    def position(self, position_id="p1", symbol="2330.TW", status="ACTIVE", shares="1"):
        return {
            "position_id": position_id,
            "symbol": symbol,
            "shares": shares,
            "average_cost": "100",
            "currency": "TWD",
            "position_status": status,
            "holding_type": "fractional_share",
            "acquisition_date": "2026-01-01",
        }

    def write_portfolio(self, positions):
        path = self.root / "portfolio.json"
        path.write_text(json.dumps(self.portfolio_payload(positions)), encoding="utf-8")
        return path

    def request(
        self,
        portfolio_path,
        *,
        mode=ProductionMarketInputMode.FRESH,
        replay_identities=None,
        provider_symbol_by_symbol=None,
        db_path=None,
    ):
        return ProductionTechnicalRiskRuntimeRequest(
            portfolio_source_path=portfolio_path,
            as_of_date=date(2026, 8, 14),
            valuation_date=date(2026, 8, 14),
            market_mode=mode,
            created_at=self.created_at,
            policy=self.policy,
            policy_version=self.policy.policy_version,
            db_path=db_path or self.db_path,
            project_root=self.root,
            replay_identities=replay_identities,
            provider_symbol_by_symbol=provider_symbol_by_symbol,
        )

    def runtime(self, source=None, store=None, materializer=None):
        return ProductionTechnicalRiskRuntime(
            market_source=source or FakeSource(),
            market_store=store or FilesystemTechnicalCloseSeriesStore(ProductionMarketInputConfig.from_project_root(self.root)),
            feature_materializer=materializer or __import__("market_inputs").ProductionTechnicalFeatureMaterializer(),
        )

    def test_one_position_fresh_success(self):
        source = FakeSource()
        result = self.runtime(source=source).run(
            self.request(
                self.write_portfolio((self.position(),)),
                provider_symbol_by_symbol={"2330.TW": "2330.TW"},
            )
        )

        self.assertEqual(len(source.requests), 1)
        self.assertEqual(result.active_position_ids, ("p1",))
        self.assertEqual(result.active_symbols, ("2330.TW",))
        self.assertEqual(result.run_record.feature_set_checksum, result.feature_set_checksum)
        self.assertEqual(tuple(ref.position_id for ref in result.run_record.risk_artifact_refs), ("p1",))

    def test_same_symbol_multi_position_fetches_and_materializes_once(self):
        source = FakeSource()
        result = self.runtime(source=source).run(
            self.request(
                self.write_portfolio(
                    (
                        self.position(position_id="p2", symbol="2330.TW", shares="0.5"),
                        self.position(position_id="p1", symbol="2330.TW"),
                    )
                ),
                provider_symbol_by_symbol={"2330.TW": "2330.TW"},
            )
        )

        self.assertEqual(len(source.requests), 1)
        self.assertEqual(result.active_position_ids, ("p1", "p2"))
        self.assertEqual(tuple(ref.position_id for ref in result.run_record.risk_artifact_refs), ("p1", "p2"))

    def test_multi_symbol_success(self):
        source = FakeSource()
        result = self.runtime(source=source).run(
            self.request(
                self.write_portfolio(
                    (
                        self.position(position_id="p1", symbol="2330.TW"),
                        self.position(position_id="p2", symbol="2454.TW"),
                    )
                ),
                provider_symbol_by_symbol={"2330.TW": "2330.TW", "2454.TW": "2454.TW"},
            )
        )

        self.assertEqual(tuple(request.symbol for request in source.requests), ("2330.TW", "2454.TW"))
        self.assertEqual(result.active_symbols, ("2330.TW", "2454.TW"))

    def test_zero_active_positions_fail(self):
        with self.assertRaisesRegex(ProductionTechnicalRiskRuntimeError, "zero active"):
            self.runtime().run(self.request(self.write_portfolio((self.position(status="CLOSED"),))))

    def test_fresh_missing_provider_mapping_rejected_before_fetch(self):
        source = FakeSource()

        with self.assertRaisesRegex(ProductionTechnicalRiskRuntimeError, "provider symbol mapping missing"):
            self.runtime(source=source).run(
                self.request(
                    self.write_portfolio((self.position(symbol="2330.TW"),)),
                    provider_symbol_by_symbol={},
                )
            )

        self.assertEqual(source.requests, [])

    def test_fresh_partial_provider_mapping_rejected_before_fetch(self):
        source = FakeSource()

        with self.assertRaisesRegex(ProductionTechnicalRiskRuntimeError, "provider symbol mapping missing"):
            self.runtime(source=source).run(
                self.request(
                    self.write_portfolio(
                        (
                            self.position(position_id="p1", symbol="2330.TW"),
                            self.position(position_id="p2", symbol="NVDA"),
                        )
                    ),
                    provider_symbol_by_symbol={"2330.TW": "2330.TW"},
                )
            )

        self.assertEqual(source.requests, [])

    def test_fresh_numeric_symbol_has_no_normalization_fallback(self):
        source = FakeSource()

        with self.assertRaisesRegex(ProductionTechnicalRiskRuntimeError, "provider symbol mapping missing"):
            self.runtime(source=source).run(
                self.request(
                    self.write_portfolio((self.position(symbol="2330"),)),
                    provider_symbol_by_symbol={},
                )
            )

        self.assertEqual(source.requests, [])

    def test_fresh_invalid_provider_mapping_rejected_before_fetch(self):
        source = FakeSource()

        with self.assertRaisesRegex(ProductionTechnicalRiskRuntimeError, "provider symbol mapping invalid"):
            self.runtime(source=source).run(
                self.request(
                    self.write_portfolio((self.position(symbol="2330.TW"),)),
                    provider_symbol_by_symbol={"2330.TW": " \n"},
                )
            )

        self.assertEqual(source.requests, [])

    def test_missing_feature_symbol_fail(self):
        with self.assertRaisesRegex(ProductionTechnicalRiskRuntimeError, "symbol mismatch"):
            self.runtime(materializer=WrongSymbolMaterializer()).run(
                self.request(
                    self.write_portfolio((self.position(),)),
                    provider_symbol_by_symbol={"2330.TW": "2330.TW"},
                )
            )

    def test_replay_performs_no_source_fetch(self):
        store = FilesystemTechnicalCloseSeriesStore(ProductionMarketInputConfig.from_project_root(self.root))
        replay_series = series()
        store.save(replay_series)
        identity = TechnicalCloseSeriesArtifactIdentity.from_series(replay_series)
        source = FakeSource(fail=True)

        result = self.runtime(source=source, store=store).run(
            self.request(
                self.write_portfolio((self.position(),)),
                mode=ProductionMarketInputMode.REPLAY,
                replay_identities={"2330.TW": identity},
            )
        )

        self.assertEqual(source.requests, [])
        self.assertEqual(result.active_symbols, ("2330.TW",))

    def test_fresh_source_failure_fail_closed(self):
        with self.assertRaisesRegex(ProductionTechnicalRiskRuntimeError, "market input resolution failed"):
            self.runtime(source=FakeSource(fail=True)).run(
                self.request(
                    self.write_portfolio((self.position(),)),
                    provider_symbol_by_symbol={"2330.TW": "2330.TW"},
                )
            )

    def test_persistence_failure_fail_closed(self):
        with self.assertRaises(Exception):
            self.runtime().run(
                self.request(
                    self.write_portfolio((self.position(),)),
                    provider_symbol_by_symbol={"2330.TW": "2330.TW"},
                    db_path=self.root,
                )
            )

    def test_feature_set_checksum_reaches_run_record(self):
        result = self.runtime().run(
            self.request(
                self.write_portfolio((self.position(),)),
                provider_symbol_by_symbol={"2330.TW": "2330.TW"},
            )
        )

        self.assertTrue(result.feature_set_checksum.startswith("technical_feature_set_"))
        self.assertEqual(result.run_record.feature_set_checksum, result.feature_set_checksum)

    def test_deterministic_same_inputs(self):
        portfolio_path = self.write_portfolio((self.position(),))
        runtime = self.runtime(source=FakeSource())

        first = runtime.run(self.request(portfolio_path, provider_symbol_by_symbol={"2330.TW": "2330.TW"}))
        second = runtime.run(self.request(portfolio_path, provider_symbol_by_symbol={"2330.TW": "2330.TW"}))

        self.assertEqual(first.calculation_id, second.calculation_id)
        self.assertEqual(first.generation_key, second.generation_key)
        self.assertEqual(first.feature_set_checksum, second.feature_set_checksum)
        self.assertEqual(first.run_record.record_checksum, second.run_record.record_checksum)

    def test_production_path_untouched(self):
        self.runtime().run(
            self.request(
                self.write_portfolio((self.position(),)),
                provider_symbol_by_symbol={"2330.TW": "2330.TW"},
            )
        )

        self.assertFalse((PROJECT_ROOT / "data" / "production").exists())


if __name__ == "__main__":
    unittest.main()
