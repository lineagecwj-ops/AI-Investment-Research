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

from portfolio_generation import RiskEvaluationOutput
from risk import HoldingType
from risk import PortfolioPosition
from risk import RiskArtifact
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskContext
from risk import RiskSeverity
from risk import RiskSignal
from risk_persistence import CapturingRiskEvaluator
from risk_persistence.capturing_risk_evaluator import CapturingRiskEvaluatorError


class FakeRiskEvaluator:
    def __init__(self, outputs=None, *, fail_on_call=None):
        self.outputs = list(outputs or ())
        self.fail_on_call = fail_on_call
        self.calls = 0

    def evaluate(self, position, context, risk_artifact_id):
        self.calls += 1
        if self.fail_on_call == self.calls:
            raise RuntimeError("delegate failure")
        return self.outputs.pop(0)


class CapturingRiskEvaluatorTestCase(unittest.TestCase):
    def position(self):
        return PortfolioPosition(
            symbol="2330.TW",
            shares=Decimal("10"),
            average_cost=Decimal("650"),
            holding_type=HoldingType.WHOLE_SHARE,
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )

    def context(self):
        return RiskContext(
            portfolio_id="portfolio_001",
            symbol="2330.TW",
            analysis_date=date(2026, 8, 15),
            feature_version="feature_set_v1",
            calculation_id="calc_001",
            model_version=None,
        )

    def output(self, artifact_id):
        signal = RiskSignal(
            risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
            symbol="2330.TW",
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.LOW,
            trigger_reason="technical risk context",
            created_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id="portfolio_001",
            symbol="2330.TW",
            signals=(signal,),
            assessment_date=date(2026, 8, 15),
        )
        artifact = RiskArtifact(
            artifact_id=artifact_id,
            position_identity=self.position().identity,
            risk_assessment=assessment,
            signals=(signal,),
            feature_lineage={"feature_version": "feature_set_v1", "model_version": None},
            calculation_metadata={"portfolio_id": "portfolio_001", "symbol": "2330.TW", "calculation_id": "calc_001"},
            created_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
            checksum=f"{artifact_id}_checksum",
        )
        return RiskEvaluationOutput(position_id="position_a", symbol="2330.TW", risk_artifact=artifact)

    def test_delegate_success_captures_and_returns_original_output(self):
        output = self.output("artifact_a")
        evaluator = CapturingRiskEvaluator(FakeRiskEvaluator((output,)))

        returned = evaluator.evaluate(self.position(), self.context(), "artifact_a")

        self.assertIs(returned, output)
        self.assertEqual(evaluator.captured_artifacts, (output.risk_artifact,))

    def test_error_type_stays_internal_to_module(self):
        import risk_persistence

        self.assertNotIn("CapturingRiskEvaluatorError", risk_persistence.__all__)
        self.assertFalse(hasattr(risk_persistence, "CapturingRiskEvaluatorError"))

    def test_multiple_success_preserves_delegate_order(self):
        first = self.output("artifact_a")
        second = replace(self.output("artifact_b"), position_id="position_b")
        evaluator = CapturingRiskEvaluator(FakeRiskEvaluator((first, second)))

        evaluator.evaluate(self.position(), self.context(), "artifact_a")
        evaluator.evaluate(self.position(), self.context(), "artifact_b")

        self.assertEqual(evaluator.captured_artifacts, (first.risk_artifact, second.risk_artifact))

    def test_delegate_failure_does_not_capture_failed_artifact_and_retains_prior_capture(self):
        first = self.output("artifact_a")
        evaluator = CapturingRiskEvaluator(FakeRiskEvaluator((first,), fail_on_call=2))

        evaluator.evaluate(self.position(), self.context(), "artifact_a")
        with self.assertRaisesRegex(RuntimeError, "delegate failure"):
            evaluator.evaluate(self.position(), self.context(), "artifact_b")

        self.assertEqual(evaluator.captured_artifacts, (first.risk_artifact,))

    def test_captured_artifacts_is_immutable_snapshot(self):
        first = self.output("artifact_a")
        evaluator = CapturingRiskEvaluator(FakeRiskEvaluator((first,)))

        evaluator.evaluate(self.position(), self.context(), "artifact_a")
        snapshot = evaluator.captured_artifacts

        self.assertIsInstance(snapshot, tuple)
        with self.assertRaises(AttributeError):
            snapshot.append(first.risk_artifact)

    def test_invalid_delegate_and_output_fail_closed(self):
        with self.assertRaises(CapturingRiskEvaluatorError):
            CapturingRiskEvaluator(object())

        evaluator = CapturingRiskEvaluator(FakeRiskEvaluator((object(),)))
        with self.assertRaises(CapturingRiskEvaluatorError):
            evaluator.evaluate(self.position(), self.context(), "artifact_a")


if __name__ == "__main__":
    unittest.main()
