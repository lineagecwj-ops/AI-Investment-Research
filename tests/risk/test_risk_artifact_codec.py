import inspect
import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk.risk_artifact_codec as codec_module
from portfolio_generation import TechnicalRiskArtifactAdapter
from risk import RISK_ARTIFACT_CODEC_VERSION_V1
from risk import RISK_ARTIFACT_SCHEMA_VERSION_V1
from risk import HoldingType
from risk import PortfolioPosition
from risk import RiskArtifact
from risk import RiskArtifactCodec
from risk import RiskArtifactCodecError
from risk import RiskArtifactGenerator
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskChecksumGenerator
from risk import RiskContext
from risk import RiskSeverity
from risk import RiskSignal
from risk_evaluation import ProducedRiskSignal
from risk_evaluation import TechnicalRiskProductionResult


class RiskArtifactCodecTestCase(unittest.TestCase):

    def created_at(self, hour=12, tz=UTC):
        return datetime(2026, 8, 15, hour, 0, tzinfo=tz)

    def analysis_date(self):
        return date(2026, 8, 15)

    def context(self, **overrides):
        values = {
            "portfolio_id": "portfolio_codec_001",
            "symbol": "2330.TW",
            "analysis_date": self.analysis_date(),
            "feature_version": "feature_set_v1",
            "model_version": "risk_model_v1",
            "calculation_id": "risk_calc_codec_001",
        }
        values.update(overrides)
        return RiskContext(**values)

    def position(self, **overrides):
        values = {
            "symbol": "2330.TW",
            "shares": Decimal("10.00"),
            "average_cost": Decimal("650.50"),
            "holding_type": HoldingType.FRACTIONAL_SHARE,
            "acquisition_date": date(2026, 1, 5),
            "currency": "TWD",
        }
        values.update(overrides)
        return PortfolioPosition(**values)

    def signal(
        self,
        *,
        risk_id="TECH_TREND_WEAKENING_V1",
        severity=RiskSeverity.MEDIUM,
        category=RiskCategory.TECHNICAL,
        symbol="2330.TW",
        reason="technical risk evidence",
        created_at=None,
    ):
        return RiskSignal(
            risk_id=risk_id,
            symbol=symbol,
            category=category,
            severity=severity,
            trigger_reason=reason,
            created_at=created_at or self.created_at(),
        )

    def artifact(self, *, severity=RiskSeverity.MEDIUM, reason="technical risk evidence", **overrides):
        context = overrides.pop("context", self.context())
        position = overrides.pop("position", self.position())
        signal = self.signal(severity=severity, reason=reason, symbol=context.symbol)
        assessment = RiskAssessment.from_signals(
            portfolio_id=context.portfolio_id,
            symbol=context.symbol,
            signals=(signal,),
            assessment_date=context.analysis_date,
        )
        artifact = RiskArtifactGenerator().generate(
            artifact_id=overrides.pop("artifact_id", "risk_artifact_codec_001"),
            position=position,
            context=context,
            assessment=assessment,
            created_at=overrides.pop("created_at", self.created_at()),
        )
        artifact = replace(
            artifact,
            feature_lineage={
                **artifact.feature_lineage,
                **overrides.pop("feature_lineage", {}),
            },
            calculation_metadata={
                **artifact.calculation_metadata,
                **overrides.pop("calculation_metadata", {}),
            },
        )
        checksum = RiskChecksumGenerator().generate(artifact, context)
        return replace(artifact, checksum=checksum)

    def payload(self, artifact=None):
        return json.loads(RiskArtifactCodec().encode(artifact or self.artifact()))

    def encode_payload(self, payload):
        payload["serialization_checksum"] = codec_module.serialization_checksum(payload)
        return codec_module.canonical_json_dumps(payload)

    def test_basic_round_trip_returns_real_domain_objects(self):
        artifact = self.artifact()

        decoded = RiskArtifactCodec().decode(RiskArtifactCodec().encode(artifact))

        self.assertEqual(decoded, artifact)
        self.assertIsInstance(decoded, RiskArtifact)
        self.assertIsInstance(decoded.risk_assessment, RiskAssessment)
        self.assertIsInstance(decoded.signals[0], RiskSignal)

    def test_encoded_string_is_deterministic(self):
        artifact = self.artifact()
        codec = RiskArtifactCodec()

        self.assertEqual(codec.encode(artifact), codec.encode(artifact))

    def test_metadata_insertion_order_does_not_change_encoded_string(self):
        first = self.artifact(calculation_metadata={"a": 1, "b": 2})
        second = self.artifact(calculation_metadata={"b": 2, "a": 1})

        self.assertEqual(RiskArtifactCodec().encode(first), RiskArtifactCodec().encode(second))

    def test_low_medium_high_and_critical_round_trip(self):
        for severity in (RiskSeverity.LOW, RiskSeverity.MEDIUM, RiskSeverity.HIGH, RiskSeverity.CRITICAL):
            with self.subTest(severity=severity):
                artifact = self.artifact(severity=severity)

                decoded = RiskArtifactCodec().decode(RiskArtifactCodec().encode(artifact))

                self.assertEqual(decoded.signals[0].severity, severity)
                self.assertEqual(decoded.risk_assessment.overall_risk_level, severity)

    def test_unicode_round_trip(self):
        artifact = self.artifact(reason="技術風險證據：短期趨勢弱於中期趨勢")

        decoded = RiskArtifactCodec().decode(RiskArtifactCodec().encode(artifact))

        self.assertEqual(decoded.signals[0].trigger_reason, "技術風險證據：短期趨勢弱於中期趨勢")

    def test_datetime_offset_fidelity(self):
        offset = timezone.utc
        artifact = self.artifact(created_at=self.created_at(20, offset))

        decoded = RiskArtifactCodec().decode(RiskArtifactCodec().encode(artifact))

        self.assertEqual(decoded.created_at, self.created_at(20, offset))
        self.assertIsNotNone(decoded.created_at.utcoffset())

    def test_tuple_ordering_and_metadata_type_round_trip(self):
        artifact = self.artifact(
            feature_lineage={
                "technical_source_feature_ids": ("TECH_AS_OF_CLOSE_V1", "TECH_SMA20_V1", "TECH_RSI14_V1"),
                "technical_source_checksums": ("close_checksum", "sma20_checksum", "rsi14_checksum"),
                "decimal_value": Decimal("1.00"),
                "date_value": date(2026, 8, 14),
                "datetime_value": self.created_at(9),
                "list_value": ["a", Decimal("2.50")],
                "mapping_value": {"nested": Decimal("3.0")},
                "bool_value": True,
                "float_value": 1.25,
            },
        )

        decoded = RiskArtifactCodec().decode(RiskArtifactCodec().encode(artifact))

        self.assertEqual(decoded.feature_lineage["technical_source_feature_ids"], artifact.feature_lineage["technical_source_feature_ids"])
        self.assertEqual(decoded.feature_lineage["technical_source_checksums"], artifact.feature_lineage["technical_source_checksums"])
        self.assertEqual(decoded.feature_lineage["decimal_value"], Decimal("1.00"))
        self.assertEqual(decoded.feature_lineage["date_value"], date(2026, 8, 14))
        self.assertEqual(decoded.feature_lineage["datetime_value"], self.created_at(9))
        self.assertEqual(decoded.feature_lineage["list_value"], ["a", Decimal("2.50")])
        self.assertEqual(decoded.feature_lineage["mapping_value"], {"nested": Decimal("3.0")})

    def test_technical_artifact_lineage_round_trip_and_pair_fidelity(self):
        artifact = self.technical_artifact()

        decoded = RiskArtifactCodec().decode(RiskArtifactCodec().encode(artifact))

        self.assertEqual(decoded.calculation_metadata["technical_policy_id"], "TECH_RISK_POLICY_V1")
        self.assertEqual(decoded.calculation_metadata["technical_policy_version"], "v1")
        self.assertEqual(decoded.calculation_metadata["technical_policy_checksum"], "policy_checksum_001")
        self.assertEqual(decoded.calculation_metadata["technical_evaluation_id"], "technical_eval_001")
        self.assertEqual(decoded.calculation_metadata["technical_evaluation_checksum"], "evaluation_checksum_001")
        self.assertEqual(decoded.calculation_metadata["technical_position_id"], "position_001")
        self.assertEqual(decoded.calculation_metadata["technical_as_of_date"], "2026-08-15")
        self.assertEqual(decoded.calculation_metadata["technical_valuation_date"], "2026-08-14")
        self.assertEqual(decoded.calculation_metadata["technical_calculation_id"], "risk_calc_codec_001")
        self.assertEqual(decoded.calculation_metadata["technical_producer_version"], "TECHNICAL_RISK_SIGNAL_PRODUCER_V1")
        self.assertEqual(
            tuple(zip(
                decoded.feature_lineage["technical_source_feature_ids"],
                decoded.feature_lineage["technical_source_checksums"],
            )),
            tuple(zip(
                artifact.feature_lineage["technical_source_feature_ids"],
                artifact.feature_lineage["technical_source_checksums"],
            )),
        )

    def technical_artifact(self):
        context = self.context(feature_version="technical_risk_feature_set_v1", model_version=None)
        signal = RiskSignal(
            risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
            symbol="2330.TW",
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.HIGH,
            trigger_reason="technical downside risk evidence: TREND_WEAKNESS",
            created_at=self.created_at(),
        )
        produced_signal = ProducedRiskSignal(
            signal=signal,
            policy_id="TECH_RISK_POLICY_V1",
            policy_version="v1",
            producer_version="TECHNICAL_RISK_SIGNAL_PRODUCER_V1",
            source_feature_ids=("TECH_AS_OF_CLOSE_V1", "TECH_SMA20_V1", "TECH_SMA60_V1", "TECH_RSI14_V1"),
            source_checksums=("close_checksum", "sma20_checksum", "sma60_checksum", "rsi14_checksum"),
            calculation_id="risk_calc_codec_001",
            policy_checksum="policy_checksum_001",
            evaluation_id="technical_eval_001",
            evaluation_checksum="evaluation_checksum_001",
            portfolio_id="portfolio_codec_001",
            position_id="position_001",
            as_of_date=self.analysis_date(),
            valuation_date=date(2026, 8, 14),
        )
        result = TechnicalRiskProductionResult(
            produced_signal=produced_signal,
            risk_assessment=RiskAssessment.from_signals(
                portfolio_id="portfolio_codec_001",
                symbol="2330.TW",
                signals=(signal,),
                assessment_date=self.analysis_date(),
            ),
        )
        return TechnicalRiskArtifactAdapter().build(
            result=result,
            context=context,
            position=self.position(),
            artifact_id="technical_risk_artifact_codec_001",
            created_at=self.created_at(13),
        )

    def test_non_artifact_encode_input_rejected(self):
        with self.assertRaisesRegex(RiskArtifactCodecError, "RiskArtifact"):
            RiskArtifactCodec().encode(object())

    def test_malformed_json_and_wrong_top_level_type_rejected(self):
        with self.assertRaisesRegex(RiskArtifactCodecError, "valid JSON"):
            RiskArtifactCodec().decode("{not-json")

        with self.assertRaisesRegex(RiskArtifactCodecError, "JSON object"):
            RiskArtifactCodec().decode("[]")

    def test_missing_and_unknown_envelope_fields_rejected(self):
        missing = self.payload()
        del missing["codec_version"]

        with self.assertRaisesRegex(RiskArtifactCodecError, "missing required fields"):
            RiskArtifactCodec().decode(codec_module.canonical_json_dumps(missing))

        unknown = self.payload()
        unknown["future_field"] = "unexpected"
        unknown["serialization_checksum"] = codec_module.serialization_checksum(unknown)

        with self.assertRaisesRegex(RiskArtifactCodecError, "unknown fields"):
            RiskArtifactCodec().decode(codec_module.canonical_json_dumps(unknown))

    def test_unknown_schema_and_codec_versions_rejected(self):
        schema = self.payload()
        schema["schema_version"] = "999"
        schema["serialization_checksum"] = codec_module.serialization_checksum(schema)

        with self.assertRaisesRegex(RiskArtifactCodecError, "schema_version"):
            RiskArtifactCodec().decode(codec_module.canonical_json_dumps(schema))

        codec = self.payload()
        codec["codec_version"] = "999"
        codec["serialization_checksum"] = codec_module.serialization_checksum(codec)

        with self.assertRaisesRegex(RiskArtifactCodecError, "codec_version"):
            RiskArtifactCodec().decode(codec_module.canonical_json_dumps(codec))

    def test_serialization_checksum_corruption_rejected(self):
        payload = self.payload()
        payload["artifact"]["signals"][0]["trigger_reason"] = "changed without serialization checksum update"

        with self.assertRaisesRegex(RiskArtifactCodecError, "serialization checksum mismatch"):
            RiskArtifactCodec().decode(codec_module.canonical_json_dumps(payload))

    def test_domain_checksum_corruption_rejected_even_with_valid_serialization_checksum(self):
        payload = self.payload()
        payload["artifact"]["checksum"] = "wrong_domain_checksum"

        with self.assertRaisesRegex(RiskArtifactCodecError, "Risk checksum mismatch"):
            RiskArtifactCodec().decode(self.encode_payload(payload))

    def test_missing_and_unknown_artifact_fields_rejected(self):
        missing = self.payload()
        del missing["artifact"]["feature_lineage"]

        with self.assertRaisesRegex(RiskArtifactCodecError, "missing required fields"):
            RiskArtifactCodec().decode(self.encode_payload(missing))

        unknown = self.payload()
        unknown["artifact"]["future_field"] = "unexpected"

        with self.assertRaisesRegex(RiskArtifactCodecError, "unknown fields"):
            RiskArtifactCodec().decode(self.encode_payload(unknown))

    def test_invalid_category_and_severity_rejected(self):
        category = self.payload()
        category["artifact"]["signals"][0]["category"] = "unknown"
        category["artifact"]["risk_assessment"]["signals"][0]["category"] = "unknown"

        with self.assertRaises(RiskArtifactCodecError):
            RiskArtifactCodec().decode(self.encode_payload(category))

        severity = self.payload()
        severity["artifact"]["signals"][0]["severity"] = "UNKNOWN"
        severity["artifact"]["risk_assessment"]["signals"][0]["severity"] = "UNKNOWN"

        with self.assertRaises(RiskArtifactCodecError):
            RiskArtifactCodec().decode(self.encode_payload(severity))

    def test_invalid_datetime_and_date_rejected(self):
        bad_datetime = self.payload()
        bad_datetime["artifact"]["created_at"] = "not-a-datetime"

        with self.assertRaisesRegex(RiskArtifactCodecError, "created_at"):
            RiskArtifactCodec().decode(self.encode_payload(bad_datetime))

        bad_date = self.payload()
        bad_date["artifact"]["calculation_metadata"]["analysis_date"] = "not-a-date"

        with self.assertRaisesRegex(RiskArtifactCodecError, "analysis_date"):
            RiskArtifactCodec().decode(self.encode_payload(bad_date))

    def test_unsupported_metadata_type_rejected(self):
        artifact = replace(self.artifact(), feature_lineage={"feature_version": "feature_set_v1", "bad": object()})

        with self.assertRaisesRegex(RiskArtifactCodecError, "unsupported metadata type"):
            RiskArtifactCodec().encode(artifact)

    def test_non_finite_float_metadata_rejected(self):
        with self.assertRaisesRegex(RiskArtifactCodecError, "finite"):
            RiskArtifactCodec().encode(self.artifact(feature_lineage={"bad": float("nan")}))

    def test_assessment_signal_mismatch_rejected(self):
        payload = self.payload()
        payload["artifact"]["risk_assessment"]["signals"][0]["risk_id"] = "DIFFERENT_SIGNAL"

        with self.assertRaisesRegex(RiskArtifactCodecError, "signals must match"):
            RiskArtifactCodec().decode(self.encode_payload(payload))

    def test_persisted_assessment_severity_mismatch_rejected(self):
        payload = self.payload(self.artifact(severity=RiskSeverity.HIGH))
        payload["artifact"]["risk_assessment"]["overall_risk_level"] = "LOW"

        with self.assertRaisesRegex(RiskArtifactCodecError, "persisted severity mismatch"):
            RiskArtifactCodec().decode(self.encode_payload(payload))

    def test_missing_checksum_context_rejected(self):
        payload = self.payload()
        del payload["artifact"]["calculation_metadata"]["calculation_id"]

        with self.assertRaisesRegex(RiskArtifactCodecError, "calculation_id"):
            RiskArtifactCodec().decode(self.encode_payload(payload))

    def test_schema_and_codec_versions_are_exported(self):
        self.assertEqual(RISK_ARTIFACT_SCHEMA_VERSION_V1, "1")
        self.assertEqual(RISK_ARTIFACT_CODEC_VERSION_V1, "1")

    def test_codec_source_has_no_persistence_or_runtime_dependencies(self):
        source = inspect.getsource(codec_module)

        forbidden = (
            "sqlite3",
            "risk_persistence",
            "portfolio_generation",
            "risk_evaluation",
            "risk_oos",
            "risk_integration",
            "targets",
            "datasets",
            "features",
            "yfinance",
            "LiveDataStore",
            "ResearchDataStore",
            "TechnicalRisk",
            "Repository",
            "Path(",
            "open(",
        )
        for forbidden_text in forbidden:
            with self.subTest(forbidden_text=forbidden_text):
                self.assertNotIn(forbidden_text, source)


if __name__ == "__main__":
    unittest.main()
