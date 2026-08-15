import json
import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from portfolio_generation import PortfolioRiskGenerationStatus
from risk_persistence import PORTFOLIO_RUN_RECORD_CODEC_VERSION_V1
from risk_persistence import PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1
from risk_persistence import PortfolioRiskGenerationRunArtifactRef
from risk_persistence import PortfolioRiskGenerationRunIssue
from risk_persistence import PortfolioRiskGenerationRunMonitoringArtifactRef
from risk_persistence import PortfolioRiskGenerationRunRecord
from risk_persistence import PortfolioRiskGenerationRunRecordCodec
from risk_persistence import PortfolioRiskGenerationRunRecordCodecError
from risk_persistence import PortfolioRiskGenerationRunWarning


class PortfolioRiskGenerationRunCodecTestCase(unittest.TestCase):

    def risk_ref(self, position_id="position_a", artifact_id=None, checksum=None):
        return PortfolioRiskGenerationRunArtifactRef(
            position_id=position_id,
            artifact_id=artifact_id or f"risk_artifact_{position_id}",
            artifact_checksum=checksum or f"risk_checksum_{position_id}",
        )

    def monitoring_ref(self, position_id="position_a", artifact_id=None):
        return PortfolioRiskGenerationRunMonitoringArtifactRef(
            position_id=position_id,
            artifact_id=artifact_id or f"monitoring_artifact_{position_id}",
        )

    def record(self, **overrides):
        values = {
            "calculation_id": "portfolio_risk_calc_001",
            "generation_key": "portfolio_risk_generation_001",
            "portfolio_id": "portfolio_001",
            "snapshot_id": "snapshot_001",
            "snapshot_checksum": "snapshot_checksum_001",
            "analysis_date": date(2026, 8, 15),
            "valuation_date": date(2026, 8, 14),
            "status": PortfolioRiskGenerationStatus.SUCCESS,
            "attempted_position_ids": ("position_a", "position_b"),
            "risk_evaluated_position_ids": ("position_a", "position_b"),
            "succeeded_position_ids": ("position_a", "position_b"),
            "failed_position_ids": (),
            "risk_artifact_refs": (self.risk_ref("position_a"), self.risk_ref("position_b")),
            "monitoring_artifact_refs": (self.monitoring_ref("position_a"), self.monitoring_ref("position_b")),
            "issues": (),
            "warnings": (
                PortfolioRiskGenerationRunWarning(
                    stage="RISK_EVALUATION",
                    message="risk warning",
                    position_id="position_a",
                ),
            ),
            "created_at": datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        }
        values.update(overrides)
        return PortfolioRiskGenerationRunRecord(**values)

    def codec(self):
        return PortfolioRiskGenerationRunRecordCodec()

    def decoded_payload(self, record=None):
        return json.loads(self.codec().encode(record or self.record()))

    def encode_payload(self, payload):
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)

    def test_round_trip_success_record(self):
        record = self.record()

        decoded = self.codec().decode(self.codec().encode(record))

        self.assertEqual(decoded, record)
        self.assertIsInstance(decoded, PortfolioRiskGenerationRunRecord)

    def test_round_trip_monitoring_failed_record(self):
        record = self.record(
            status=PortfolioRiskGenerationStatus.MONITORING_FAILED,
            attempted_position_ids=("position_a", "position_b"),
            risk_evaluated_position_ids=("position_a", "position_b"),
            succeeded_position_ids=("position_a",),
            failed_position_ids=("position_b",),
            risk_artifact_refs=(self.risk_ref("position_a"), self.risk_ref("position_b")),
            monitoring_artifact_refs=(self.monitoring_ref("position_a"),),
            issues=(PortfolioRiskGenerationRunIssue("MONITORING", "monitoring failed", "position_b"),),
            warnings=(),
        )

        decoded = self.codec().decode(self.codec().encode(record))

        self.assertEqual(decoded.status, PortfolioRiskGenerationStatus.MONITORING_FAILED)
        self.assertEqual(decoded.risk_evaluated_position_ids, ("position_a", "position_b"))
        self.assertEqual(decoded.failed_position_ids, ("position_b",))

    def test_deterministic_encoded_string(self):
        first = self.codec().encode(self.record())
        second = self.codec().encode(self.record())

        self.assertEqual(first, second)
        self.assertNotIn("\n", first)

    def test_unicode_issue_warning_round_trip_with_ascii_envelope(self):
        record = self.record(
            issues=(PortfolioRiskGenerationRunIssue("VALIDATION", "風險評估失敗", "position_a"),),
            warnings=(PortfolioRiskGenerationRunWarning("GENERATION", "提醒：資料延遲", None),),
        )

        encoded = self.codec().encode(record)
        decoded = self.codec().decode(encoded)

        self.assertIn("\\u98a8", encoded)
        self.assertEqual(decoded.issues[0].message, "風險評估失敗")
        self.assertEqual(decoded.warnings[0].message, "提醒：資料延遲")

    def test_tuple_order_preserved(self):
        record = self.record(
            attempted_position_ids=("position_b", "position_a"),
            risk_evaluated_position_ids=("position_b", "position_a"),
            succeeded_position_ids=("position_b", "position_a"),
            risk_artifact_refs=(self.risk_ref("position_b"), self.risk_ref("position_a")),
            monitoring_artifact_refs=(self.monitoring_ref("position_b"), self.monitoring_ref("position_a")),
        )

        decoded = self.codec().decode(self.codec().encode(record))

        self.assertEqual(decoded.attempted_position_ids, ("position_b", "position_a"))

    def test_timezone_offset_fidelity(self):
        offset = timezone.utc
        record = self.record(created_at=datetime(2026, 8, 15, 20, 30, tzinfo=offset))

        decoded = self.codec().decode(self.codec().encode(record))

        self.assertEqual(decoded.created_at.isoformat(), "2026-08-15T20:30:00+00:00")

    def test_exact_date_fidelity(self):
        decoded = self.codec().decode(self.codec().encode(self.record()))

        self.assertEqual(decoded.analysis_date, date(2026, 8, 15))
        self.assertEqual(decoded.valuation_date, date(2026, 8, 14))

    def test_unknown_envelope_field_rejected(self):
        payload = self.decoded_payload()
        payload["unexpected"] = "value"

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "envelope"):
            self.codec().decode(self.encode_payload(payload))

    def test_missing_envelope_field_rejected(self):
        payload = self.decoded_payload()
        del payload["codec_version"]

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "envelope"):
            self.codec().decode(self.encode_payload(payload))

    def test_unknown_schema_rejected(self):
        payload = self.decoded_payload()
        payload["schema_version"] = "999"

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "schema_version"):
            self.codec().decode(self.encode_payload(payload))

    def test_unknown_codec_rejected(self):
        payload = self.decoded_payload()
        payload["codec_version"] = "999"

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "codec_version"):
            self.codec().decode(self.encode_payload(payload))

    def test_known_versions_encoded(self):
        payload = self.decoded_payload()

        self.assertEqual(payload["schema_version"], PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1)
        self.assertEqual(payload["codec_version"], PORTFOLIO_RUN_RECORD_CODEC_VERSION_V1)

    def test_unknown_record_field_rejected(self):
        payload = self.decoded_payload()
        payload["record"]["unexpected"] = "value"

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "payload"):
            self.codec().decode(self.encode_payload(payload))

    def test_missing_record_field_rejected(self):
        payload = self.decoded_payload()
        del payload["record"]["portfolio_id"]

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "payload"):
            self.codec().decode(self.encode_payload(payload))

    def test_unknown_status_enum_rejected(self):
        payload = self.decoded_payload()
        payload["record"]["status"] = "PARTIAL_SUCCESS"

        with self.assertRaises(PortfolioRiskGenerationRunRecordCodecError):
            self.codec().decode(self.encode_payload(payload))

    def test_malformed_json_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "valid JSON"):
            self.codec().decode("{not-json")

    def test_wrong_top_level_type_rejected(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "envelope"):
            self.codec().decode("[]")

    def test_bad_date_rejected(self):
        payload = self.decoded_payload()
        payload["record"]["analysis_date"] = "2026-99-99"

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "analysis_date"):
            self.codec().decode(self.encode_payload(payload))

    def test_bad_datetime_rejected(self):
        payload = self.decoded_payload()
        payload["record"]["created_at"] = "2026-08-15T12:00:00"

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "timezone-aware"):
            self.codec().decode(self.encode_payload(payload))

    def test_record_checksum_corruption_rejected(self):
        payload = self.decoded_payload()
        payload["record"]["record_checksum"] = "bad_checksum"

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "record_checksum"):
            self.codec().decode(self.encode_payload(payload))

    def test_semantic_payload_tamper_with_old_checksum_rejected(self):
        payload = self.decoded_payload()
        payload["record"]["portfolio_id"] = "portfolio_other"

        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "record_checksum"):
            self.codec().decode(self.encode_payload(payload))

    def test_encode_requires_run_record(self):
        with self.assertRaisesRegex(PortfolioRiskGenerationRunRecordCodecError, "requires"):
            self.codec().encode({"not": "record"})


if __name__ == "__main__":
    unittest.main()
