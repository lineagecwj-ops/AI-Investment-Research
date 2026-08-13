import sys
import unittest
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from portfolio_generation import ExactVersionPolicyResolver
from portfolio_generation import HOLDING_TYPE_MAPPING
from portfolio_generation import MonitoringContextBuilderError
from portfolio_generation import PolicyResolverError
from portfolio_generation import PositionAdapterError
from portfolio_generation import RiskContextBuilderError
from portfolio_generation import adapt_position_state
from portfolio_generation import build_monitoring_context
from portfolio_generation import build_risk_context
from portfolio_generation import resolve_active_position
from portfolio_state import HoldingType as PortfolioHoldingType
from portfolio_state import PortfolioPositionState
from portfolio_state import PortfolioSnapshot
from portfolio_state import RiskEvaluationInput
from risk import HoldingType as RiskHoldingType
from risk import RiskArtifact
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskDefinition
from risk import RiskRegistry
from risk import RiskSeverity
from risk import RiskSignal


class PortfolioGenerationContractBuildersTestCase(unittest.TestCase):

    def created_at(self, day=13):
        return datetime(2026, 8, day, 12, 0, tzinfo=UTC)

    def position(
        self,
        *,
        position_id="position_001",
        symbol="2330.TW",
        shares=Decimal("10"),
        average_cost=Decimal("650.00"),
        holding_type=PortfolioHoldingType.WHOLE_SHARE,
        position_status="ACTIVE",
        portfolio_id="portfolio_synthetic_001",
    ):
        return PortfolioPositionState(
            portfolio_id=portfolio_id,
            position_id=position_id,
            symbol=symbol,
            shares=shares,
            average_cost=average_cost,
            currency="TWD",
            position_status=position_status,
            holding_type=holding_type,
            acquisition_date=date(2026, 1, 5),
        )

    def snapshot(self, *, positions=None):
        return PortfolioSnapshot(
            snapshot_id="snapshot_001",
            portfolio_id="portfolio_synthetic_001",
            as_of_date=date(2026, 8, 13),
            valuation_date=date(2026, 8, 12),
            positions=positions if positions is not None else (self.position(),),
            created_at=self.created_at(),
            source_lineage={"source_type": "manual_contract_test", "source_version": "v1"},
        )

    def evaluation_input(self, snapshot=None, **overrides):
        active_snapshot = snapshot or self.snapshot()
        params = {
            "feature_version": "feature_set_v1",
            "model_version": "baseline_model_v1",
            "risk_definition_version": "risk_definition_v1",
            "risk_policy_version": "risk_policy_v1",
            "monitoring_policy_version": "monitoring_policy_v1",
        }
        params.update(overrides)
        return RiskEvaluationInput.from_snapshot(active_snapshot, **params)

    def risk_artifact(
        self,
        *,
        portfolio_id="portfolio_synthetic_001",
        symbol="2330.TW",
        artifact_id="risk_artifact_001",
        checksum="risk_checksum_001",
        calculation_id=None,
        created_at=None,
    ):
        active_created_at = created_at or self.created_at(day=14)
        signal = RiskSignal(
            risk_id="TECH_TREND_WEAKENING_V1",
            symbol=symbol,
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.HIGH,
            trigger_reason="synthetic risk metadata",
            created_at=active_created_at,
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id=portfolio_id,
            symbol=symbol,
            signals=(signal,),
            assessment_date=date(2026, 8, 13),
        )
        return RiskArtifact(
            artifact_id=artifact_id,
            position_identity={"symbol": symbol},
            risk_assessment=assessment,
            signals=(signal,),
            feature_lineage={"feature_version": "feature_set_v1", "model_version": "baseline_model_v1"},
            calculation_metadata={
                "portfolio_id": portfolio_id,
                "symbol": symbol,
                "analysis_date": "2026-08-13",
                "calculation_id": calculation_id or self.evaluation_input().calculation_id,
            },
            created_at=active_created_at,
            checksum=checksum,
        )

    def registry(self):
        registry = RiskRegistry()
        registry.register(
            RiskDefinition(
                risk_id="TECH_TREND_WEAKENING_V1",
                risk_name="Trend Weakening",
                category=RiskCategory.TECHNICAL,
                version="risk_definition_v1",
                description="Synthetic risk definition.",
                severity_rule="metadata threshold",
            )
        )
        return registry

    def test_whole_share_explicit_mapping(self):
        position = self.position(holding_type=PortfolioHoldingType.WHOLE_SHARE)
        evaluation_input = self.evaluation_input()

        adapted = adapt_position_state(position, evaluation_input)

        self.assertEqual(HOLDING_TYPE_MAPPING[PortfolioHoldingType.WHOLE_SHARE], RiskHoldingType.WHOLE_SHARE)
        self.assertEqual(adapted.holding_type, RiskHoldingType.WHOLE_SHARE)
        self.assertEqual(adapted.shares, Decimal("10"))

    def test_fractional_share_explicit_mapping(self):
        position = self.position(
            shares=Decimal("10.125"),
            holding_type=PortfolioHoldingType.FRACTIONAL_SHARE,
        )
        snapshot = self.snapshot(positions=(position,))
        evaluation_input = self.evaluation_input(snapshot)

        adapted = adapt_position_state(position, evaluation_input)

        self.assertEqual(HOLDING_TYPE_MAPPING[PortfolioHoldingType.FRACTIONAL_SHARE], RiskHoldingType.FRACTIONAL_SHARE)
        self.assertEqual(adapted.holding_type, RiskHoldingType.FRACTIONAL_SHARE)
        self.assertEqual(adapted.shares, Decimal("10.125"))

    def test_holding_type_mapping_does_not_depend_on_enum_coincidence(self):
        position = self.position()
        object.__setattr__(position, "holding_type", "whole_share")

        with self.assertRaises(PositionAdapterError):
            adapt_position_state(position, self.evaluation_input())

    def test_inactive_position_rejection(self):
        position = self.position(position_status="CLOSED")
        object.__setattr__(position, "position_status", "CLOSED")
        evaluation_input = replace(self.evaluation_input(), active_position_ids=("position_001",))

        with self.assertRaisesRegex(PositionAdapterError, "ACTIVE"):
            adapt_position_state(position, evaluation_input)

    def test_missing_active_position_rejection(self):
        snapshot = self.snapshot(positions=(self.position(position_id="position_002"),))
        evaluation_input = replace(self.evaluation_input(snapshot), active_position_ids=("missing_position",))

        with self.assertRaisesRegex(PositionAdapterError, "missing"):
            resolve_active_position(snapshot, evaluation_input, "missing_position")

    def test_portfolio_mismatch_rejection(self):
        position = self.position(portfolio_id="other_portfolio")
        object.__setattr__(position, "portfolio_id", "other_portfolio")

        with self.assertRaisesRegex(PositionAdapterError, "portfolio_id"):
            adapt_position_state(position, self.evaluation_input())

    def test_invalid_decimal_and_currency_fail_closed(self):
        fractional_whole = self.position()
        object.__setattr__(fractional_whole, "shares", Decimal("10.5"))
        with self.assertRaisesRegex(PositionAdapterError, "integer shares"):
            adapt_position_state(fractional_whole, self.evaluation_input())

        bad_currency = self.position()
        object.__setattr__(bad_currency, "currency", "")
        with self.assertRaisesRegex(PositionAdapterError, "currency"):
            adapt_position_state(bad_currency, self.evaluation_input())

    def test_risk_context_deterministic_build(self):
        position = self.position()
        evaluation_input = self.evaluation_input()

        first = build_risk_context(evaluation_input, position)
        second = build_risk_context(evaluation_input, position)

        self.assertEqual(first, second)
        self.assertEqual(first.portfolio_id, evaluation_input.portfolio_id)
        self.assertEqual(first.symbol, position.symbol)

    def test_risk_context_analysis_date_is_as_of_date(self):
        context = build_risk_context(self.evaluation_input(), self.position())

        self.assertEqual(context.analysis_date, date(2026, 8, 13))

    def test_risk_context_retains_generation_calculation_id(self):
        evaluation_input = self.evaluation_input()
        context = build_risk_context(evaluation_input, self.position())

        self.assertEqual(context.calculation_id, evaluation_input.calculation_id)

    def test_nullable_model_version(self):
        evaluation_input = self.evaluation_input(model_version=None)
        context = build_risk_context(evaluation_input, self.position())

        self.assertIsNone(context.model_version)

    def test_risk_context_rejects_missing_feature_version(self):
        evaluation_input = self.evaluation_input()
        object.__setattr__(evaluation_input, "feature_version", "")

        with self.assertRaisesRegex(RiskContextBuilderError, "feature_version"):
            build_risk_context(evaluation_input, self.position())

    def test_monitoring_context_monitoring_date_is_as_of_date(self):
        evaluation_input = self.evaluation_input()
        context = build_monitoring_context(
            self.risk_artifact(calculation_id=evaluation_input.calculation_id),
            evaluation_input,
            self.position(),
        )

        self.assertEqual(context.monitoring_date, evaluation_input.as_of_date)

    def test_created_at_does_not_affect_monitoring_date(self):
        evaluation_input = self.evaluation_input()
        context = build_monitoring_context(
            self.risk_artifact(
                calculation_id=evaluation_input.calculation_id,
                created_at=self.created_at(day=14),
            ),
            evaluation_input,
            self.position(),
        )

        self.assertEqual(context.monitoring_date, date(2026, 8, 13))
        self.assertNotEqual(context.monitoring_date, date(2026, 8, 14))

    def test_monitoring_context_rejects_risk_artifact_portfolio_mismatch(self):
        evaluation_input = self.evaluation_input()

        with self.assertRaisesRegex(MonitoringContextBuilderError, "portfolio_id"):
            build_monitoring_context(
                self.risk_artifact(
                    portfolio_id="other_portfolio",
                    calculation_id=evaluation_input.calculation_id,
                ),
                evaluation_input,
                self.position(),
            )

    def test_monitoring_context_rejects_risk_artifact_symbol_mismatch(self):
        evaluation_input = self.evaluation_input()

        with self.assertRaisesRegex(MonitoringContextBuilderError, "symbol"):
            build_monitoring_context(
                self.risk_artifact(
                    symbol="2454.TW",
                    calculation_id=evaluation_input.calculation_id,
                ),
                evaluation_input,
                self.position(),
            )

    def test_monitoring_context_rejects_missing_checksum(self):
        evaluation_input = self.evaluation_input()

        with self.assertRaisesRegex(MonitoringContextBuilderError, "checksum"):
            build_monitoring_context(
                self.risk_artifact(checksum=None, calculation_id=evaluation_input.calculation_id),
                evaluation_input,
                self.position(),
            )

    def test_monitoring_context_rejects_calculation_id_mismatch(self):
        evaluation_input = self.evaluation_input()

        with self.assertRaisesRegex(MonitoringContextBuilderError, "calculation_id"):
            build_monitoring_context(
                self.risk_artifact(calculation_id="different_calculation"),
                evaluation_input,
                self.position(),
            )

    def test_exact_policy_version_resolution(self):
        resolver = ExactVersionPolicyResolver(
            risk_registry=self.registry(),
            allowed_risk_policy_versions=("risk_policy_v1",),
            allowed_monitoring_policy_versions=("monitoring_policy_v1",),
        )

        definition = resolver.resolve_risk_definition("TECH_TREND_WEAKENING_V1", "risk_definition_v1")
        risk_policy = resolver.resolve_risk_policy_version("risk_policy_v1")
        monitoring_policy = resolver.resolve_monitoring_policy_version("monitoring_policy_v1")

        self.assertEqual(definition.version, "risk_definition_v1")
        self.assertEqual(risk_policy.version, "risk_policy_v1")
        self.assertEqual(monitoring_policy.version, "monitoring_policy_v1")

    def test_unknown_version_rejection(self):
        resolver = ExactVersionPolicyResolver(
            risk_registry=self.registry(),
            allowed_risk_policy_versions=("risk_policy_v1",),
        )

        with self.assertRaises(PolicyResolverError):
            resolver.resolve_risk_definition("TECH_TREND_WEAKENING_V1", "risk_definition_v2")
        with self.assertRaises(PolicyResolverError):
            resolver.resolve_risk_policy_version("risk_policy_v2")

    def test_no_latest_or_default_fallback(self):
        resolver = ExactVersionPolicyResolver(
            risk_registry=self.registry(),
            allowed_risk_policy_versions=("risk_policy_v1",),
        )

        with self.assertRaisesRegex(PolicyResolverError, "required"):
            resolver.resolve_risk_policy_version("")
        with self.assertRaises(PolicyResolverError):
            resolver.resolve_risk_definition("TECH_TREND_WEAKENING_V1", "")

    def test_deterministic_builder_output(self):
        position = self.position()
        evaluation_input = self.evaluation_input()
        risk_artifact = self.risk_artifact(calculation_id=evaluation_input.calculation_id)

        first_context = build_risk_context(evaluation_input, position)
        second_context = build_risk_context(evaluation_input, position)
        first_monitoring = build_monitoring_context(risk_artifact, evaluation_input, position)
        second_monitoring = build_monitoring_context(risk_artifact, evaluation_input, position)

        self.assertEqual(first_context, second_context)
        self.assertEqual(first_monitoring, second_monitoring)

    def test_architecture_boundary_scan(self):
        source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "portfolio_generation").glob("*.py"))
        )

        forbidden_terms = (
            "RiskMonitoringEngine(",
            ".evaluate(",
            "RiskArtifactGenerator(",
            "RiskMonitoringArtifactGenerator(",
            "RiskAssessment(",
            "RiskAssessment.from_signals",
            "sqlite3",
            "LiveDataStore",
            "live_data_store",
            "ResearchDataStore",
            "research_data_store",
            "swing_scanner",
            "scanner_service",
            "pdf_export",
            "yfinance",
            "portfolio_artifacts",
            "portfolio_dashboard",
            "open(",
            "Path(",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
