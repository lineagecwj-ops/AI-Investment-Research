import json
import sys
import unittest
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseObservation
from market_inputs import TechnicalCloseObservationSeries
from market_inputs import TechnicalCloseObservationSeriesCodec
from market_inputs import TechnicalCloseObservationSeriesCodecError
from market_inputs import TECHNICAL_CLOSE_OBSERVATION_CODEC_VERSION_V1
from market_inputs import TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1


class TechnicalCloseObservationSeriesCodecTestCase(unittest.TestCase):

    def observation(self, market_session_date=date(2026, 8, 14), technical_close=100.25):
        return TechnicalCloseObservation(
            market_session_date=market_session_date,
            technical_close=technical_close,
        )

    def series(self, **overrides):
        values = {
            "symbol": "台積電",
            "provider": "Yahoo Finance",
            "provider_symbol": "2330.TW",
            "timezone": "Asia/Taipei",
            "close_basis": TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            "valuation_date": date(2026, 8, 14),
            "observations": (
                self.observation(date(2026, 8, 12), 98.0),
                self.observation(date(2026, 8, 14), 100.25),
            ),
            "fetched_at": datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
        }
        values.update(overrides)
        return TechnicalCloseObservationSeries(**values)

    def codec(self):
        return TechnicalCloseObservationSeriesCodec()

    def test_codec_round_trip_returns_domain_object(self):
        series = self.series()

        decoded = self.codec().decode(self.codec().encode(series))

        self.assertEqual(decoded, series)
        self.assertIsInstance(decoded, TechnicalCloseObservationSeries)

    def test_codec_envelope_versions(self):
        payload = json.loads(self.codec().encode(self.series()))

        self.assertEqual(payload["schema_version"], TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1)
        self.assertEqual(payload["codec_version"], TECHNICAL_CLOSE_OBSERVATION_CODEC_VERSION_V1)

    def test_encode_is_deterministic(self):
        series = self.series()

        self.assertEqual(self.codec().encode(series), self.codec().encode(series))

    def test_source_order_does_not_change_encoded_payload_or_revision(self):
        first = self.series()
        second = self.series(observations=tuple(reversed(first.observations)))

        self.assertEqual(first.market_revision_id, second.market_revision_id)
        self.assertEqual(self.codec().encode(first), self.codec().encode(second))

    def test_same_bars_different_fetched_at_same_revision_but_different_audit_payload(self):
        first = self.series()
        second = self.series(fetched_at=datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc))

        self.assertEqual(first.market_revision_id, second.market_revision_id)
        self.assertNotEqual(self.codec().encode(first), self.codec().encode(second))

    def test_one_close_changed_changes_revision(self):
        first = self.series()
        second = self.series(
            observations=(
                self.observation(date(2026, 8, 12), 98.0),
                self.observation(date(2026, 8, 14), 101.25),
            )
        )

        self.assertNotEqual(first.market_revision_id, second.market_revision_id)

    def test_float_hex_payload_round_trips_repr_sensitive_values(self):
        values = (0.1, 100.25, 5e-324, 1.7976931348623157e308, 0.30000000000000004)
        codec = self.codec()

        for value in values:
            with self.subTest(value=value):
                series = self.series(observations=(self.observation(technical_close=value),))
                payload = json.loads(codec.encode(series))
                stored = payload["series"]["observations"][0]["technical_close"]
                self.assertEqual(stored, value.hex())
                self.assertEqual(codec.decode(codec.encode(series)), series)

    def test_unknown_envelope_field_rejected(self):
        payload = json.loads(self.codec().encode(self.series()))
        payload["unexpected"] = True

        with self.assertRaisesRegex(TechnicalCloseObservationSeriesCodecError, "unknown field"):
            self.codec().decode(json.dumps(payload))

    def test_missing_series_field_rejected(self):
        payload = json.loads(self.codec().encode(self.series()))
        del payload["series"]["provider"]

        with self.assertRaisesRegex(TechnicalCloseObservationSeriesCodecError, "missing required field"):
            self.codec().decode(json.dumps(payload))

    def test_unknown_schema_or_codec_version_rejected(self):
        for field_name in ("schema_version", "codec_version"):
            with self.subTest(field_name=field_name):
                payload = json.loads(self.codec().encode(self.series()))
                payload[field_name] = "unsupported"
                with self.assertRaisesRegex(TechnicalCloseObservationSeriesCodecError, "Unsupported"):
                    self.codec().decode(json.dumps(payload))

    def test_bad_date_and_bad_datetime_rejected(self):
        payload = json.loads(self.codec().encode(self.series()))
        payload["series"]["valuation_date"] = "2026-8-14"
        with self.assertRaisesRegex(TechnicalCloseObservationSeriesCodecError, "ISO date"):
            self.codec().decode(json.dumps(payload))

        payload = json.loads(self.codec().encode(self.series()))
        payload["series"]["fetched_at"] = "2026-08-16T09:00:00"
        with self.assertRaisesRegex(TechnicalCloseObservationSeriesCodecError, "timezone-aware"):
            self.codec().decode(json.dumps(payload))

    def test_duplicate_observations_rejected_on_decode(self):
        payload = json.loads(self.codec().encode(self.series()))
        payload["series"]["observations"].append(payload["series"]["observations"][0])

        with self.assertRaisesRegex(TechnicalCloseObservationSeriesCodecError, "duplicate"):
            self.codec().decode(json.dumps(payload))

    def test_revision_tamper_rejected(self):
        payload = json.loads(self.codec().encode(self.series()))
        payload["series"]["market_revision_id"] = "market_revision_tampered"

        with self.assertRaisesRegex(TechnicalCloseObservationSeriesCodecError, "market_revision_id"):
            self.codec().decode(json.dumps(payload))

    def test_nan_infinity_and_non_positive_payloads_rejected(self):
        for value in ("nan", "inf", "-inf", "0x0.0p+0", "-0x1.0000000000000p+0"):
            with self.subTest(value=value):
                payload = json.loads(self.codec().encode(self.series()))
                payload["series"]["observations"][0]["technical_close"] = value
                with self.assertRaises(TechnicalCloseObservationSeriesCodecError):
                    self.codec().decode(json.dumps(payload))

    def test_unicode_round_trip_uses_ascii_escaped_canonical_json(self):
        encoded = self.codec().encode(self.series())

        self.assertIn("\\u53f0\\u7a4d\\u96fb", encoded)
        self.assertEqual(self.codec().decode(encoded).symbol, "台積電")

    def test_decode_requires_json_string_and_object(self):
        with self.assertRaisesRegex(TechnicalCloseObservationSeriesCodecError, "JSON string"):
            self.codec().decode({"not": "json"})
        with self.assertRaisesRegex(TechnicalCloseObservationSeriesCodecError, "JSON object"):
            self.codec().decode("[]")


if __name__ == "__main__":
    unittest.main()
