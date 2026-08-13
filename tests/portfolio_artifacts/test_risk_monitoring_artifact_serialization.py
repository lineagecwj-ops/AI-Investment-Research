import sys
import unittest
from copy import deepcopy
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

from portfolio_artifacts import RISK_MONITORING_ARTIFACT_SCHEMA_VERSION
from portfolio_artifacts import RiskMonitoringArtifactSerializationError
from portfolio_artifacts import canonical_json_dumps
from portfolio_artifacts import deserialize_risk_monitoring_artifact
from portfolio_artifacts import serialize_risk_monitoring_artifact
from portfolio_artifacts import serialized_payload_checksum
from portfolio_dashboard import PortfolioArtifactInputRequest
from portfolio_dashboard import build_portfolio_dashboard_input
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
from risk_monitoring import MonitoringState
from risk_monitoring import RiskMonitoringArtifactGenerator
from risk_monitoring import RiskMonitoringContext
from risk_monitoring import RiskMonitoringEvent


class RiskMonitoringArtifactSerializationTestCase(unittest.TestCase):

    def created_at(self, hour=12):
        return datetime(2026, 8, 13, hour, 0, tzinfo=UTC)

    def risk_context(self, symbol="2330.TW"):
        return RiskContext(
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            analysis_date=date(2026, 8, 13),
            feature_version="feature_set_v1",
            model_version="baseline_model_v1",
            calculation_id=f"risk_calc_{symbol}",
        )

    def monitoring_context(self, symbol="2330.TW", source_artifact_id="risk_artifact_001"):
        return RiskMonitoringContext(
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            monitoring_date=date(2026, 8, 13),
            source_risk_artifact_id=source_artifact_id,
            risk_artifact_checksum=f"{source_artifact_id}_checksum",
            monitoring_policy_version="policy_v1",
            calculation_id=f"monitoring_calc_{symbol}",
        )

    def risk_artifact(self, *, symbol="2330.TW", artifact_id="risk_artifact_001", severity=RiskSeverity.HIGH):
        signal = RiskSignal(
            risk_id=f"TECH_RISK_{symbol}",
            symbol=symbol,
            category=RiskCategory.TECHNICAL,
            severity=severity,
            trigger_reason="synthetic risk review metadata",
            created_at=self.created_at(),
        )
        assessment = RiskAssessment.from_signals(
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            signals=(signal,),
            assessment_date=date(2026, 8, 13),
        )
        return RiskArtifactGenerator().generate(
            artifact_id=artifact_id,
            position=PortfolioPosition(
                symbol=symbol,
                shares=Decimal("10"),
                average_cost=Decimal("650.00"),
                holding_type="whole_share",
                acquisition_date=date(2026, 1, 5),
                currency="TWD",
            ),
            context=self.risk_context(symbol),
            assessment=assessment,
            created_at=self.created_at(),
        )

    def event(self, *, symbol="2330.TW", event_id="event_001", severity=RiskSeverity.HIGH):
        return RiskMonitoringEvent(
            event_id=event_id,
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            source_risk_id=f"TECH_RISK_{symbol}",
            risk_category=RiskCategory.TECHNICAL,
            risk_severity=severity,
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            reason="synthetic risk review metadata",
            created_at=self.created_at(),
        )

    def alert(self, *, symbol="2330.TW", alert_id="alert_001", event_id="event_001"):
        return AlertCandidate(
            alert_id=alert_id,
            portfolio_id="portfolio_synthetic_001",
            symbol=symbol,
            alert_level=AlertLevel.REVIEW,
            alert_type=AlertType.RISK_REVIEW,
            reason="synthetic review metadata",
            source_event_ids=(event_id,),
            created_at=self.created_at(),
        )

    def artifact(self, *, symbol="2330.TW", artifact_id="monitoring_artifact_001"):
        risk_artifact = self.risk_artifact(symbol=symbol)
        return RiskMonitoringArtifactGenerator().generate(
            artifact_id=artifact_id,
            risk_artifact=risk_artifact,
            context=self.monitoring_context(symbol=symbol),
            monitoring_state=MonitoringState.REVIEW_REQUIRED,
            events=(self.event(symbol=symbol),),
            alert_candidates=(self.alert(symbol=symbol),),
            created_at=self.created_at(),
            checksum=f"{artifact_id}_checksum",
        )

    def test_serialize_valid_artifact(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())

        self.assertEqual(payload["schema_version"], RISK_MONITORING_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(payload["artifact_id"], "monitoring_artifact_001")
        self.assertEqual(payload["monitoring_date"], "2026-08-13")
        self.assertEqual(payload["checksum"], "monitoring_artifact_001_checksum")
        self.assertIn("serialization_checksum", payload)
        self.assertEqual(payload["serialization_checksum"], serialized_payload_checksum(payload))

    def test_deserialize_valid_payload(self):
        artifact = deserialize_risk_monitoring_artifact(serialize_risk_monitoring_artifact(self.artifact()))

        self.assertEqual(artifact.artifact_id, "monitoring_artifact_001")
        self.assertEqual(artifact.monitoring_state, MonitoringState.REVIEW_REQUIRED)
        self.assertEqual(artifact.events[0].risk_category, RiskCategory.TECHNICAL)
        self.assertEqual(artifact.alert_candidates[0].alert_level, AlertLevel.REVIEW)
        self.assertEqual(artifact.created_at, self.created_at())

    def test_round_trip_equality(self):
        artifact = self.artifact()

        restored = deserialize_risk_monitoring_artifact(serialize_risk_monitoring_artifact(artifact))

        self.assertEqual(restored, artifact)

    def test_deterministic_serialization(self):
        artifact = self.artifact()

        first = canonical_json_dumps(serialize_risk_monitoring_artifact(artifact))
        second = canonical_json_dumps(serialize_risk_monitoring_artifact(artifact))

        self.assertEqual(first, second)

    def test_stable_datetime_and_date_encoding(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())

        self.assertEqual(payload["created_at"], "2026-08-13T12:00:00+00:00")
        self.assertEqual(payload["monitoring_date"], "2026-08-13")
        self.assertEqual(payload["events"][0]["created_at"], "2026-08-13T12:00:00+00:00")

    def test_stable_enum_encoding(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())

        self.assertEqual(payload["monitoring_state"], "REVIEW_REQUIRED")
        self.assertEqual(payload["events"][0]["risk_category"], "technical")
        self.assertEqual(payload["events"][0]["risk_severity"], "HIGH")
        self.assertEqual(payload["alert_candidates"][0]["alert_level"], "REVIEW")

    def test_tuple_restoration(self):
        artifact = deserialize_risk_monitoring_artifact(serialize_risk_monitoring_artifact(self.artifact()))

        self.assertIsInstance(artifact.events, tuple)
        self.assertIsInstance(artifact.alert_candidates, tuple)
        self.assertIsInstance(artifact.alert_candidates[0].source_event_ids, tuple)

    def test_checksum_preservation_and_verification(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())

        self.assertEqual(payload["checksum"], "monitoring_artifact_001_checksum")
        self.assertEqual(payload["serialization_checksum"], serialized_payload_checksum(payload))
        self.assertEqual(deserialize_risk_monitoring_artifact(payload).checksum, "monitoring_artifact_001_checksum")

    def test_checksum_mismatch_rejection(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())
        payload["events"][0]["reason"] = "changed after serialization"

        with self.assertRaises(RiskMonitoringArtifactSerializationError) as context:
            deserialize_risk_monitoring_artifact(payload)

        self.assertIn("serialization checksum mismatch", str(context.exception))

    def test_missing_required_field_rejection(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())
        del payload["lineage"]

        with self.assertRaises(RiskMonitoringArtifactSerializationError) as context:
            deserialize_risk_monitoring_artifact(payload)

        self.assertIn("missing required fields", str(context.exception))

    def test_invalid_enum_rejection(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())
        payload["monitoring_state"] = "UNKNOWN"
        payload["serialization_checksum"] = serialized_payload_checksum(payload)

        with self.assertRaises(RiskMonitoringArtifactSerializationError):
            deserialize_risk_monitoring_artifact(payload)

    def test_invalid_datetime_rejection(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())
        payload["created_at"] = "not-a-datetime"
        payload["serialization_checksum"] = serialized_payload_checksum(payload)

        with self.assertRaises(RiskMonitoringArtifactSerializationError) as context:
            deserialize_risk_monitoring_artifact(payload)

        self.assertIn("created_at", str(context.exception))

    def test_invalid_monitoring_date_rejection(self):
        artifact = self.artifact()
        bad_artifact = replace(
            artifact,
            calculation_metadata={**artifact.calculation_metadata, "monitoring_date": "not-a-date"},
        )

        with self.assertRaises(RiskMonitoringArtifactSerializationError) as context:
            serialize_risk_monitoring_artifact(bad_artifact)

        self.assertIn("monitoring_date", str(context.exception))

    def test_invalid_payload_monitoring_date_rejection(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())
        payload["monitoring_date"] = "not-a-date"
        payload["serialization_checksum"] = serialized_payload_checksum(payload)

        with self.assertRaises(RiskMonitoringArtifactSerializationError) as context:
            deserialize_risk_monitoring_artifact(payload)

        self.assertIn("monitoring_date", str(context.exception))

    def test_corrupted_nested_event_rejection(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())
        del payload["events"][0]["event_id"]
        payload["serialization_checksum"] = serialized_payload_checksum(payload)

        with self.assertRaises(RiskMonitoringArtifactSerializationError) as context:
            deserialize_risk_monitoring_artifact(payload)

        self.assertIn("event_id", str(context.exception))

    def test_unsupported_schema_version_rejection(self):
        payload = serialize_risk_monitoring_artifact(self.artifact())
        payload["schema_version"] = "999"
        payload["serialization_checksum"] = serialized_payload_checksum(payload)

        with self.assertRaises(RiskMonitoringArtifactSerializationError) as context:
            deserialize_risk_monitoring_artifact(payload)

        self.assertIn("Unsupported RiskMonitoringArtifact schema_version", str(context.exception))

    def test_artifact_input_contract_compatibility(self):
        artifact = deserialize_risk_monitoring_artifact(serialize_risk_monitoring_artifact(self.artifact()))

        result = build_portfolio_dashboard_input(PortfolioArtifactInputRequest(artifacts=(artifact,)))

        self.assertTrue(result.success)
        self.assertEqual(result.projection.overview.artifact_count, 1)
        self.assertEqual(result.projection.positions[0].artifact_id, "monitoring_artifact_001")

    def test_serialization_does_not_mutate_artifact(self):
        artifact = self.artifact()
        original_events = artifact.events
        original_alerts = artifact.alert_candidates
        original_lineage = deepcopy(artifact.lineage)

        serialize_risk_monitoring_artifact(artifact)

        self.assertIs(artifact.events, original_events)
        self.assertIs(artifact.alert_candidates, original_alerts)
        self.assertEqual(artifact.lineage, original_lineage)

    def test_serialization_module_does_not_import_runtime_boundaries(self):
        source = (SRC_PATH / "portfolio_artifacts" / "serialization.py").read_text()

        forbidden_terms = (
            "sqlite3",
            "LiveDataStore",
            "live_data_store",
            "ResearchDataStore",
            "research_data_store",
            "swing_scanner",
            "scanner_service",
            "pdf_export",
            "yfinance",
            "RiskMonitoringEngine",
            "RiskArtifactGenerator",
            "RiskMonitoringArtifactGenerator",
            "open(",
            "Path(",
            "read_text",
            "read_bytes",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
