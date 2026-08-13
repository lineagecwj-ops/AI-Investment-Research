import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk import PortfolioPosition
from risk import RiskAssessment
from risk import RiskArtifactGenerator
from risk import RiskCategory
from risk import RiskContext
from risk import RiskSeverity
from risk import RiskSignal
from risk_monitoring import AlertCandidate
from risk_monitoring import AlertLevel
from risk_monitoring import AlertType
from risk_monitoring import ForbiddenMonitoringActionError
from risk_monitoring import MonitoringPolicy
from risk_monitoring import MonitoringState
from risk_monitoring import RiskMonitoringArtifactGenerator
from risk_monitoring import RiskMonitoringChecksumGenerator
from risk_monitoring import RiskMonitoringContext
from risk_monitoring import RiskMonitoringEngine
from risk_monitoring import RiskMonitoringEngineError
from risk_monitoring import RiskMonitoringEvent
from risk_monitoring import RiskMonitoringValidationError
from risk_monitoring import RiskMonitoringValidator


class RiskMonitoringFrameworkTestCase(unittest.TestCase):

    def created_at(self):
        return datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    def monitoring_context(self):
        return RiskMonitoringContext(
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            monitoring_date=date(2026, 8, 13),
            source_risk_artifact_id="risk_artifact_phase7l_source",
            risk_artifact_checksum="risk_checksum_synthetic_001",
            monitoring_policy_version="policy_v1",
            calculation_id="monitoring_calc_phase7l_001",
        )

    def policy(self):
        return MonitoringPolicy(
            policy_id="MONITORING_POLICY_V1",
            policy_name="Default Risk Monitoring Policy",
            version="policy_v1",
            description="Synthetic metadata-only monitoring policy.",
        )

    def risk_artifact(self, severity=RiskSeverity.HIGH):
        created_at = self.created_at()
        position = PortfolioPosition(
            symbol="2330.TW",
            shares=Decimal("10"),
            average_cost=Decimal("650.00"),
            holding_type="whole_share",
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )
        risk_context = RiskContext(
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            analysis_date=date(2026, 8, 13),
            feature_version="feature_set_v1",
            model_version="baseline_model_v1",
            calculation_id="risk_calc_phase7k_001",
        )
        signal = RiskSignal(
            risk_id="TECH_TREND_WEAKENING_V1",
            symbol="2330.TW",
            category=RiskCategory.TECHNICAL,
            severity=severity,
            trigger_reason="synthetic monitoring source risk",
            created_at=created_at,
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            signals=(signal,),
            assessment_date=date(2026, 8, 13),
        )
        return RiskArtifactGenerator().generate(
            artifact_id="risk_artifact_phase7l_source",
            position=position,
            context=risk_context,
            assessment=assessment,
            created_at=created_at,
        )

    def monitoring_event(self, state=MonitoringState.REVIEW_REQUIRED, severity=RiskSeverity.HIGH):
        return RiskMonitoringEvent(
            event_id="monitoring_event_001",
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            source_risk_id="TECH_TREND_WEAKENING_V1",
            risk_category=RiskCategory.TECHNICAL,
            risk_severity=severity,
            monitoring_state=state,
            reason="synthetic risk review metadata",
            created_at=self.created_at(),
        )

    def alert_candidate(self):
        return AlertCandidate(
            alert_id="alert_candidate_001",
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            alert_level=AlertLevel.REVIEW,
            alert_type=AlertType.RISK_REVIEW,
            reason="synthetic review metadata",
            source_event_ids=("monitoring_event_001",),
            created_at=self.created_at(),
        )

    def monitoring_artifact(self):
        context = self.monitoring_context()
        risk_artifact = self.risk_artifact()
        return RiskMonitoringArtifactGenerator().generate(
            artifact_id="monitoring_artifact_001",
            risk_artifact=risk_artifact,
            context=context,
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            events=(self.monitoring_event(),),
            alert_candidates=(self.alert_candidate(),),
            created_at=self.created_at(),
        )

    def test_monitoring_enums(self):
        self.assertEqual(MonitoringState.NORMAL.value, "NORMAL")
        self.assertEqual(AlertLevel.REVIEW.value, "REVIEW")
        self.assertEqual(AlertType.RISK_REVIEW.value, "RISK_REVIEW")

    def test_risk_monitoring_context_creation(self):
        context = self.monitoring_context()

        self.assertEqual(context.portfolio_id, "portfolio_synthetic_001")
        self.assertEqual(context.source_risk_artifact_id, "risk_artifact_phase7l_source")
        self.assertEqual(context.monitoring_policy_version, "policy_v1")

    def test_monitoring_policy_severity_mapping(self):
        policy = self.policy()

        self.assertEqual(policy.state_for_severity(RiskSeverity.LOW), MonitoringState.NORMAL)
        self.assertEqual(policy.state_for_severity(RiskSeverity.MEDIUM), MonitoringState.WATCH)
        self.assertEqual(policy.state_for_severity(RiskSeverity.HIGH), MonitoringState.REVIEW_REQUIRED)
        self.assertEqual(policy.state_for_severity(RiskSeverity.CRITICAL), MonitoringState.ESCALATED_REVIEW)

    def test_monitoring_event_creation(self):
        event = self.monitoring_event()

        self.assertEqual(event.monitoring_state, MonitoringState.REVIEW_REQUIRED)
        self.assertEqual(event.risk_category, RiskCategory.TECHNICAL)
        self.assertEqual(event.risk_severity, RiskSeverity.HIGH)

    def test_alert_candidate_creation(self):
        alert = self.alert_candidate()

        self.assertEqual(alert.alert_level, AlertLevel.REVIEW)
        self.assertEqual(alert.alert_type, AlertType.RISK_REVIEW)
        self.assertEqual(alert.source_event_ids, ("monitoring_event_001",))

    def test_risk_monitoring_artifact_generation(self):
        artifact = self.monitoring_artifact()

        self.assertEqual(artifact.artifact_id, "monitoring_artifact_001")
        self.assertEqual(artifact.source_risk_artifact_id, "risk_artifact_phase7l_source")
        self.assertEqual(artifact.monitoring_state, MonitoringState.REVIEW_REQUIRED)
        self.assertEqual(artifact.overall_risk_level, "HIGH")
        self.assertEqual(artifact.calculation_metadata["event_count"], 1)

    def test_monitoring_engine_integrates_high_risk_artifact(self):
        artifact = RiskMonitoringEngine(self.policy()).evaluate(
            risk_artifact=self.risk_artifact(RiskSeverity.HIGH),
            context=self.monitoring_context(),
            created_at=self.created_at(),
            artifact_id="monitoring_artifact_engine_001",
        )

        self.assertEqual(artifact.monitoring_state, MonitoringState.REVIEW_REQUIRED)
        self.assertEqual(artifact.overall_risk_level, "HIGH")
        self.assertEqual(len(artifact.events), 1)
        self.assertEqual(artifact.events[0].monitoring_state, MonitoringState.REVIEW_REQUIRED)
        self.assertEqual(len(artifact.alert_candidates), 1)
        self.assertEqual(artifact.alert_candidates[0].alert_level, AlertLevel.REVIEW)
        self.assertEqual(artifact.alert_candidates[0].source_event_ids, (artifact.events[0].event_id,))
        self.assertIsNotNone(artifact.checksum)

    def test_monitoring_engine_low_risk_has_no_alert_candidate(self):
        artifact = RiskMonitoringEngine(self.policy()).evaluate(
            risk_artifact=self.risk_artifact(RiskSeverity.LOW),
            context=self.monitoring_context(),
            created_at=self.created_at(),
            artifact_id="monitoring_artifact_engine_low",
        )

        self.assertEqual(artifact.monitoring_state, MonitoringState.NORMAL)
        self.assertEqual(artifact.overall_risk_level, "LOW")
        self.assertEqual(len(artifact.events), 1)
        self.assertEqual(artifact.events[0].monitoring_state, MonitoringState.NORMAL)
        self.assertEqual(artifact.alert_candidates, ())

    def test_monitoring_engine_rejects_source_mismatch(self):
        context = RiskMonitoringContext(
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            monitoring_date=date(2026, 8, 13),
            source_risk_artifact_id="different_risk_artifact",
            risk_artifact_checksum="risk_checksum_synthetic_001",
            monitoring_policy_version="policy_v1",
            calculation_id="monitoring_calc_phase7l_001",
        )

        with self.assertRaisesRegex(RiskMonitoringEngineError, "does not match"):
            RiskMonitoringEngine(self.policy()).evaluate(
                risk_artifact=self.risk_artifact(),
                context=context,
                created_at=self.created_at(),
            )

    def test_checksum_reproducibility(self):
        generator = RiskMonitoringChecksumGenerator()
        artifact = self.monitoring_artifact()
        context = self.monitoring_context()

        self.assertEqual(generator.generate(artifact, context), generator.generate(artifact, context))

    def test_monitoring_engine_checksum_verification(self):
        artifact = RiskMonitoringEngine(self.policy()).evaluate(
            risk_artifact=self.risk_artifact(),
            context=self.monitoring_context(),
            created_at=self.created_at(),
            artifact_id="monitoring_artifact_engine_checksum",
        )

        RiskMonitoringChecksumGenerator().verify(artifact, self.monitoring_context(), artifact.checksum)

    def test_validator_rejects_trading_semantics(self):
        artifact = RiskMonitoringArtifactGenerator().generate(
            artifact_id="monitoring_artifact_bad",
            risk_artifact=self.risk_artifact(),
            context=self.monitoring_context(),
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            events=(
                RiskMonitoringEvent(
                    event_id="monitoring_event_bad",
                    portfolio_id="portfolio_synthetic_001",
                    symbol="2330.TW",
                    source_risk_id="TECH_TREND_WEAKENING_V1",
                    risk_category=RiskCategory.TECHNICAL,
                    risk_severity=RiskSeverity.HIGH,
                    monitoring_state=MonitoringState.REVIEW_REQUIRED,
                    reason="synthetic buy wording should fail",
                    created_at=self.created_at(),
                ),
            ),
            alert_candidates=(),
            created_at=self.created_at(),
        )

        with self.assertRaises(ForbiddenMonitoringActionError):
            RiskMonitoringValidator().validate_no_trading_semantics(artifact)

    def test_validator_rejects_unknown_alert_event_reference(self):
        artifact = RiskMonitoringArtifactGenerator().generate(
            artifact_id="monitoring_artifact_bad_alert",
            risk_artifact=self.risk_artifact(),
            context=self.monitoring_context(),
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            events=(self.monitoring_event(),),
            alert_candidates=(
                AlertCandidate(
                    alert_id="alert_candidate_bad",
                    portfolio_id="portfolio_synthetic_001",
                    symbol="2330.TW",
                    alert_level=AlertLevel.REVIEW,
                    alert_type=AlertType.RISK_REVIEW,
                    reason="synthetic review metadata",
                    source_event_ids=("missing_event",),
                    created_at=self.created_at(),
                ),
            ),
            created_at=self.created_at(),
        )

        with self.assertRaisesRegex(RiskMonitoringValidationError, "unknown monitoring event"):
            RiskMonitoringValidator().validate_alert_candidates(artifact)

    def test_monitoring_engine_event_ordering_is_deterministic(self):
        created_at = self.created_at()
        position = PortfolioPosition(
            symbol="2330.TW",
            shares=Decimal("10"),
            average_cost=Decimal("650.00"),
            holding_type="whole_share",
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )
        risk_context = RiskContext(
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            analysis_date=date(2026, 8, 13),
            feature_version="feature_set_v1",
            model_version="baseline_model_v1",
            calculation_id="risk_calc_phase7k_001",
        )
        signals = (
            RiskSignal(
                risk_id="PORT_POSITION_CONCENTRATION_V1",
                symbol="2330.TW",
                category=RiskCategory.PORTFOLIO,
                severity=RiskSeverity.MEDIUM,
                trigger_reason="synthetic concentration metadata",
                created_at=created_at,
            ),
            RiskSignal(
                risk_id="TECH_TREND_WEAKENING_V1",
                symbol="2330.TW",
                category=RiskCategory.TECHNICAL,
                severity=RiskSeverity.HIGH,
                trigger_reason="synthetic trend risk metadata",
                created_at=created_at,
            ),
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            signals=signals,
            assessment_date=date(2026, 8, 13),
        )
        risk_artifact = RiskArtifactGenerator().generate(
            artifact_id="risk_artifact_phase7l_source",
            position=position,
            context=risk_context,
            assessment=assessment,
            created_at=created_at,
        )

        artifact = RiskMonitoringEngine(self.policy()).evaluate(
            risk_artifact=risk_artifact,
            context=self.monitoring_context(),
            created_at=created_at,
            artifact_id="monitoring_artifact_engine_order",
        )

        self.assertEqual(
            tuple(event.source_risk_id for event in artifact.events),
            ("PORT_POSITION_CONCENTRATION_V1", "TECH_TREND_WEAKENING_V1"),
        )
        self.assertEqual(tuple(event.event_id for event in artifact.events), tuple(sorted(event.event_id for event in artifact.events)))

    def test_risk_monitoring_modules_do_not_import_runtime_boundaries(self):
        source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "risk_monitoring").glob("*.py"))
        )

        forbidden_imports = (
            "sqlite3",
            "LiveDataStore",
            "live_data_store",
            "ResearchDataStore",
            "research_data_store",
            "swing_scanner",
            "scanner_service",
            "pdf_export",
            "yfinance",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
