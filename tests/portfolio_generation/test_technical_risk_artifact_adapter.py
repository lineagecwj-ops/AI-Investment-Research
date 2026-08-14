import inspect
import sys
import unittest
from dataclasses import FrozenInstanceError
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

import portfolio_generation.technical_risk_artifact_adapter as adapter_module
from portfolio_generation import PortfolioRiskGenerationService
from portfolio_generation import TechnicalRiskArtifactAdapter
from portfolio_generation import TechnicalRiskArtifactAdapterError
from risk import HoldingType
from risk import PortfolioPosition
from risk import RiskArtifact
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskChecksumGenerator
from risk import RiskContext
from risk import RiskSeverity
from risk import RiskSignal
from risk_evaluation import ProducedRiskSignal
from risk_evaluation import TechnicalRiskProductionResult


class TechnicalRiskArtifactAdapterTestCase(unittest.TestCase):

    def created_at(self, day=14):
        return datetime(2026, 8, day, 12, 0, tzinfo=UTC)

    def context(self, **overrides):
        values = {
            "portfolio_id": "portfolio_001",
            "symbol": "2330.TW",
            "analysis_date": date(2026, 8, 14),
            "feature_version": "technical_risk_feature_set_v1",
            "calculation_id": "technical_calc_001",
            "model_version": None,
        }
        values.update(overrides)
        return RiskContext(**values)

    def position(self, **overrides):
        values = {
            "symbol": "2330.TW",
            "shares": Decimal("10"),
            "average_cost": Decimal("650.00"),
            "holding_type": HoldingType.WHOLE_SHARE,
            "acquisition_date": date(2026, 1, 5),
            "currency": "TWD",
        }
        values.update(overrides)
        return PortfolioPosition(**values)

    def produced_signal(self, severity=RiskSeverity.HIGH, **overrides):
        signal = RiskSignal(
            risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
            symbol=overrides.pop("signal_symbol", "2330.TW"),
            category=overrides.pop("category", RiskCategory.TECHNICAL),
            severity=severity,
            trigger_reason=overrides.pop("trigger_reason", "technical downside risk evidence: TREND_WEAKNESS"),
            created_at=self.created_at(),
        )
        values = {
            "signal": signal,
            "policy_id": "TECH_RISK_POLICY_V1",
            "policy_version": "v1",
            "producer_version": "TECHNICAL_RISK_SIGNAL_PRODUCER_V1",
            "source_feature_ids": ("TECH_AS_OF_CLOSE_V1", "TECH_SMA20_V1", "TECH_SMA60_V1", "TECH_RSI14_V1"),
            "source_checksums": ("close_checksum", "sma20_checksum", "sma60_checksum", "rsi14_checksum"),
            "calculation_id": "technical_calc_001",
            "policy_checksum": "policy_checksum_001",
            "evaluation_id": "technical_eval_001",
            "evaluation_checksum": "evaluation_checksum_001",
            "portfolio_id": "portfolio_001",
            "position_id": "position_001",
            "as_of_date": date(2026, 8, 14),
            "valuation_date": date(2026, 8, 13),
        }
        values.update(overrides)
        return ProducedRiskSignal(**values)

    def result(self, severity=RiskSeverity.HIGH, **overrides):
        produced_signal = self.produced_signal(severity=severity, **overrides)
        assessment = RiskAssessment.from_signals(
            portfolio_id=produced_signal.portfolio_id,
            symbol=produced_signal.signal.symbol,
            signals=(produced_signal.signal,),
            assessment_date=produced_signal.as_of_date or date(2026, 8, 14),
        )
        return TechnicalRiskProductionResult(
            produced_signal=produced_signal,
            risk_assessment=assessment,
        )

    def malformed_result(self, produced_signal, assessment):
        result = object.__new__(TechnicalRiskProductionResult)
        object.__setattr__(result, "produced_signal", produced_signal)
        object.__setattr__(result, "risk_assessment", assessment)
        return result

    def build(self, result=None, context=None, position=None, artifact_id="risk_artifact_001", created_at=None):
        return TechnicalRiskArtifactAdapter().build(
            result or self.result(),
            context or self.context(),
            position or self.position(),
            artifact_id,
            created_at or self.created_at(15),
        )

    def test_builds_low_medium_high_existing_risk_artifacts(self):
        for severity in (RiskSeverity.LOW, RiskSeverity.MEDIUM, RiskSeverity.HIGH):
            with self.subTest(severity=severity):
                artifact = self.build(result=self.result(severity))

                self.assertIsInstance(artifact, RiskArtifact)
                self.assertEqual(artifact.signals[0].severity, severity)
                self.assertEqual(artifact.risk_assessment.overall_risk_level, severity)
                self.assertIsNotNone(artifact.checksum)

    def test_reuses_existing_assessment_and_signal_without_rebuild(self):
        result = self.result(RiskSeverity.MEDIUM)

        artifact = self.build(result=result)

        self.assertIs(artifact.risk_assessment, result.risk_assessment)
        self.assertEqual(artifact.signals, result.risk_assessment.signals)
        self.assertIs(artifact.signals[0], result.produced_signal.signal)

    def test_preserves_full_production_lineage_metadata(self):
        result = self.result()

        artifact = self.build(result=result)

        self.assertEqual(artifact.feature_lineage["feature_version"], "technical_risk_feature_set_v1")
        self.assertEqual(artifact.feature_lineage["model_version"], None)
        self.assertEqual(artifact.feature_lineage["technical_source_feature_ids"], result.produced_signal.source_feature_ids)
        self.assertEqual(artifact.feature_lineage["technical_source_checksums"], result.produced_signal.source_checksums)
        self.assertEqual(artifact.calculation_metadata["technical_policy_id"], result.produced_signal.policy_id)
        self.assertEqual(artifact.calculation_metadata["technical_policy_version"], result.produced_signal.policy_version)
        self.assertEqual(artifact.calculation_metadata["technical_policy_checksum"], result.produced_signal.policy_checksum)
        self.assertEqual(artifact.calculation_metadata["technical_evaluation_id"], result.produced_signal.evaluation_id)
        self.assertEqual(artifact.calculation_metadata["technical_evaluation_checksum"], result.produced_signal.evaluation_checksum)
        self.assertEqual(artifact.calculation_metadata["technical_position_id"], result.produced_signal.position_id)
        self.assertEqual(artifact.calculation_metadata["technical_as_of_date"], "2026-08-14")
        self.assertEqual(artifact.calculation_metadata["technical_valuation_date"], "2026-08-13")
        self.assertEqual(artifact.calculation_metadata["technical_calculation_id"], result.produced_signal.calculation_id)
        self.assertEqual(artifact.calculation_metadata["technical_producer_version"], result.produced_signal.producer_version)

    def test_checksum_uses_existing_generator_and_covers_lineage_metadata(self):
        artifact = self.build()
        context = self.context()

        self.assertEqual(artifact.checksum, RiskChecksumGenerator().generate(replace(artifact, checksum=None), context))

        policy_changed = self.build(result=self.result(policy_checksum="policy_checksum_002"))
        evaluation_changed = self.build(result=self.result(evaluation_checksum="evaluation_checksum_002"))
        valuation_changed = self.build(result=self.result(valuation_date=date(2026, 8, 12)))

        self.assertNotEqual(artifact.checksum, policy_changed.checksum)
        self.assertNotEqual(artifact.checksum, evaluation_changed.checksum)
        self.assertNotEqual(artifact.checksum, valuation_changed.checksum)

    def test_same_semantic_input_is_deterministic(self):
        first = self.build()
        second = self.build()

        self.assertEqual(first, second)
        self.assertEqual(first.checksum, second.checksum)

    def test_caller_supplied_artifact_id_and_created_at_are_preserved(self):
        created_at = self.created_at(16)

        artifact = self.build(artifact_id="caller_artifact_001", created_at=created_at)

        self.assertEqual(artifact.artifact_id, "caller_artifact_001")
        self.assertEqual(artifact.created_at, created_at)

    def test_rejects_invalid_result_type(self):
        with self.assertRaisesRegex(TechnicalRiskArtifactAdapterError, "TechnicalRiskProductionResult"):
            self.build(result=object())

    def test_rejects_result_assessment_mismatch(self):
        produced = self.produced_signal()
        other_signal = RiskSignal(
            risk_id="OTHER_TECH_SIGNAL",
            symbol="2330.TW",
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.LOW,
            trigger_reason="other technical evidence",
            created_at=self.created_at(),
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id="portfolio_001",
            symbol="2330.TW",
            signals=(other_signal,),
            assessment_date=date(2026, 8, 14),
        )

        with self.assertRaisesRegex(TechnicalRiskArtifactAdapterError, "exactly once"):
            self.build(result=self.malformed_result(produced, assessment))

    def test_rejects_non_technical_category_and_critical(self):
        with self.assertRaisesRegex(TechnicalRiskArtifactAdapterError, "TECHNICAL"):
            self.build(result=self.result(category=RiskCategory.MARKET))

        with self.assertRaisesRegex(TechnicalRiskArtifactAdapterError, "CRITICAL"):
            self.build(result=self.result(RiskSeverity.CRITICAL))

    def test_rejects_cross_lineage_mismatches(self):
        mismatch_cases = (
            (self.result(portfolio_id="portfolio_other"), self.context(), self.position(), "portfolio_id"),
            (self.result(signal_symbol="2454.TW"), self.context(), self.position(), "symbol"),
            (self.result(calculation_id="technical_calc_other"), self.context(), self.position(), "calculation_id"),
            (self.result(as_of_date=date(2026, 8, 13)), self.context(), self.position(), "as_of_date"),
            (self.result(), self.context(), self.position(symbol="2454.TW"), "position symbol"),
        )
        for result, context, position, expected in mismatch_cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(TechnicalRiskArtifactAdapterError, expected):
                    self.build(result=result, context=context, position=position)

    def test_rejects_missing_required_lineage(self):
        missing_cases = (
            ("policy_checksum", None, "policy_checksum"),
            ("evaluation_id", None, "evaluation_id"),
            ("evaluation_checksum", None, "evaluation_checksum"),
            ("position_id", None, "position_id"),
            ("as_of_date", None, "as_of_date"),
            ("valuation_date", None, "valuation_date"),
            ("source_feature_ids", (), "source_feature_ids"),
            ("source_checksums", (), "source_checksums"),
        )
        for field_name, value, expected in missing_cases:
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(TechnicalRiskArtifactAdapterError, expected):
                    self.build(result=self.result(**{field_name: value}))

    def test_rejects_parallel_source_lineage_mismatch(self):
        with self.assertRaisesRegex(TechnicalRiskArtifactAdapterError, "source feature/checksum"):
            self.build(result=self.result(source_checksums=("close_checksum",)))

    def test_rejects_invalid_artifact_id_and_naive_created_at(self):
        with self.assertRaisesRegex(TechnicalRiskArtifactAdapterError, "artifact_id"):
            self.build(artifact_id="")

        with self.assertRaisesRegex(TechnicalRiskArtifactAdapterError, "timezone-aware"):
            self.build(created_at=datetime(2026, 8, 15, 12, 0))

    def test_whole_and_fractional_shares_preserve_severity_but_position_identity_differs(self):
        result = self.result(RiskSeverity.HIGH)
        whole = self.build(result=result, position=self.position(shares=Decimal("10"), holding_type=HoldingType.WHOLE_SHARE))
        fractional = self.build(
            result=result,
            position=self.position(shares=Decimal("10.5"), holding_type=HoldingType.FRACTIONAL_SHARE),
        )

        self.assertEqual(whole.signals[0].severity, RiskSeverity.HIGH)
        self.assertEqual(fractional.signals[0].severity, RiskSeverity.HIGH)
        self.assertNotEqual(whole.position_identity, fractional.position_identity)

    def test_position_id_is_preserved_as_lineage_without_inventing_position_identity_field(self):
        artifact = self.build(result=self.result(position_id="position_technical_001"))

        self.assertNotIn("position_id", artifact.position_identity)
        self.assertEqual(artifact.calculation_metadata["technical_position_id"], "position_technical_001")
        self.assertEqual(artifact.position_identity["symbol"], "2330.TW")

    def test_adapter_is_immutable_and_exported(self):
        adapter = TechnicalRiskArtifactAdapter()

        with self.assertRaises(FrozenInstanceError):
            adapter.checksum_generator = RiskChecksumGenerator()

        self.assertIs(TechnicalRiskArtifactAdapter, adapter_module.TechnicalRiskArtifactAdapter)
        self.assertIs(TechnicalRiskArtifactAdapterError, adapter_module.TechnicalRiskArtifactAdapterError)

    def test_source_boundary_no_runtime_or_research_dependencies(self):
        source = inspect.getsource(adapter_module)

        forbidden = (
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "RiskAssessment.from_signals",
            "RiskSignal(",
            "TechnicalRiskEvaluator",
            "TechnicalRiskSignalProducer",
            "TechnicalRiskProductionService",
            "risk_oos",
            "risk_integration",
            "targets",
            "datasets",
            "sqlite",
            "DB",
            "yfinance",
            "scheduler",
            "alert",
            "dashboard",
            "app.py",
            "hashlib",
            "json.dumps",
            "policy activation",
            "recommendation",
        )
        for forbidden_text in forbidden:
            with self.subTest(forbidden_text=forbidden_text):
                self.assertNotIn(forbidden_text, source)

    def test_does_not_modify_portfolio_generation_service_contract(self):
        source = inspect.getsource(PortfolioRiskGenerationService)

        self.assertNotIn("TechnicalRiskArtifactAdapter", source)
        self.assertNotIn("TechnicalRiskProductionResult", source)


if __name__ == "__main__":
    unittest.main()
