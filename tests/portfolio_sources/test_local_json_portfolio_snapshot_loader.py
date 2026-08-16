import json
import sys
import tempfile
import unittest
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

from portfolio_sources import LocalJsonPortfolioSnapshotLoader
from portfolio_sources import PortfolioSourceError
from portfolio_sources import PortfolioSourceFormatError
from portfolio_state import HoldingType
from portfolio_state import PositionStatus


class LocalJsonPortfolioSnapshotLoaderTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def payload(self, *, positions=None, **overrides):
        data = {
            "schema_version": "1",
            "portfolio_id": "portfolio_台灣_001",
            "snapshot_id": "snapshot_2026_08_16_v1",
            "as_of_date": "2026-08-16",
            "valuation_date": "2026-08-14",
            "snapshot_created_at": "2026-08-16T09:00:00+08:00",
            "source_lineage": {
                "source_type": "local_json_portfolio_snapshot",
                "source_version": "1",
            },
            "positions": positions
            if positions is not None
            else (
                self.position(),
            ),
        }
        data.update(overrides)
        return data

    def position(self, **overrides):
        data = {
            "position_id": "tw-2330-lot-001",
            "symbol": "2330.TW",
            "shares": "12",
            "average_cost": "650.00",
            "currency": "twd",
            "position_status": "ACTIVE",
            "holding_type": "whole_share",
            "acquisition_date": "2026-01-05",
        }
        data.update(overrides)
        return data

    def write_json(self, payload, filename="portfolio.json"):
        path = self.root / filename
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def write_text(self, text, filename="portfolio.json"):
        path = self.root / filename
        path.write_text(text, encoding="utf-8")
        return path

    def load(self, payload):
        return LocalJsonPortfolioSnapshotLoader().load(self.write_json(payload))

    def test_valid_one_position_snapshot(self):
        snapshot = self.load(self.payload())

        self.assertEqual(snapshot.portfolio_id, "portfolio_台灣_001")
        self.assertEqual(snapshot.snapshot_id, "snapshot_2026_08_16_v1")
        self.assertEqual(snapshot.as_of_date, date(2026, 8, 16))
        self.assertEqual(snapshot.valuation_date, date(2026, 8, 14))
        self.assertEqual(snapshot.created_at, datetime(2026, 8, 16, 9, 0, tzinfo=timezone(timedelta(hours=8))))
        self.assertEqual(snapshot.source_lineage["source_type"], "local_json_portfolio_snapshot")
        self.assertEqual(snapshot.positions[0].position_id, "tw-2330-lot-001")
        self.assertEqual(snapshot.positions[0].shares, Decimal("12"))
        self.assertEqual(snapshot.positions[0].average_cost, Decimal("650.00"))
        self.assertEqual(snapshot.positions[0].currency, "TWD")

    def test_whole_and_fractional_shares(self):
        whole = self.load(self.payload(positions=(self.position(shares="12", holding_type="whole_share"),)))
        fractional = self.load(
            self.payload(
                positions=(
                    self.position(position_id="tw-2330-fractional", shares="0.75", holding_type="fractional_share"),
                )
            )
        )

        self.assertEqual(whole.positions[0].holding_type, HoldingType.WHOLE_SHARE)
        self.assertEqual(fractional.positions[0].holding_type, HoldingType.FRACTIONAL_SHARE)
        self.assertEqual(fractional.positions[0].shares, Decimal("0.75"))

    def test_same_symbol_multi_position_supported(self):
        snapshot = self.load(
            self.payload(
                positions=(
                    self.position(position_id="tw-2330-lot-b"),
                    self.position(position_id="tw-2330-lot-a", shares="0.5", holding_type="fractional_share"),
                )
            )
        )

        self.assertEqual(tuple(position.symbol for position in snapshot.positions), ("2330.TW", "2330.TW"))
        self.assertEqual(tuple(position.position_id for position in snapshot.positions), ("tw-2330-lot-a", "tw-2330-lot-b"))

    def test_duplicate_position_id_rejected(self):
        path = self.write_json(
            self.payload(
                positions=(
                    self.position(position_id="same-position"),
                    self.position(position_id="same-position", symbol="2454.TW"),
                )
            )
        )

        with self.assertRaisesRegex(PortfolioSourceFormatError, "Duplicate portfolio position_id"):
            LocalJsonPortfolioSnapshotLoader().load(path)

    def test_zero_negative_and_bad_decimal_rejected(self):
        cases = (
            self.position(shares="0"),
            self.position(shares="-1"),
            self.position(average_cost="-1"),
            self.position(shares="not-decimal"),
            self.position(average_cost="not-decimal"),
        )
        for index, position in enumerate(cases):
            with self.subTest(index=index):
                with self.assertRaises(PortfolioSourceFormatError):
                    self.load(self.payload(positions=(position,)))

    def test_json_number_shares_and_average_cost_rejected(self):
        for position in (
            self.position(shares=12),
            self.position(shares=12.5),
            self.position(shares=True),
            self.position(average_cost=650),
            self.position(average_cost=650.0),
            self.position(average_cost=True),
        ):
            with self.subTest(position=position):
                with self.assertRaisesRegex(PortfolioSourceFormatError, "decimal string"):
                    self.load(self.payload(positions=(position,)))

    def test_unknown_and_missing_fields_rejected(self):
        unknown_top = self.payload(extra="not allowed")
        missing_top = self.payload()
        missing_top.pop("snapshot_id")
        unknown_position = self.payload(positions=(self.position(extra="not allowed"),))
        missing_position = self.payload(positions=(dict(self.position(), symbol=None),))

        for payload in (unknown_top, missing_top, unknown_position, missing_position):
            with self.subTest(payload=payload):
                with self.assertRaises(PortfolioSourceFormatError):
                    self.load(payload)

    def test_bad_status_holding_type_and_dates_rejected(self):
        cases = (
            self.payload(positions=(self.position(position_status="UNKNOWN"),)),
            self.payload(positions=(self.position(holding_type="unknown"),)),
            self.payload(as_of_date="2026-08-16T00:00:00"),
            self.payload(valuation_date="2026-08-14T00:00:00"),
            self.payload(positions=(self.position(acquisition_date="2026-01-05T00:00:00"),)),
            self.payload(snapshot_created_at="2026-08-16T09:00:00"),
        )
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(PortfolioSourceFormatError):
                    self.load(payload)

    def test_duplicate_json_keys_rejected(self):
        path = self.write_text(
            """
            {
              "schema_version": "1",
              "schema_version": "1",
              "portfolio_id": "portfolio_001",
              "snapshot_id": "snapshot_001",
              "as_of_date": "2026-08-16",
              "valuation_date": "2026-08-14",
              "snapshot_created_at": "2026-08-16T09:00:00+08:00",
              "source_lineage": {"source_type": "local_json_portfolio_snapshot", "source_version": "1"},
              "positions": []
            }
            """
        )

        with self.assertRaisesRegex(PortfolioSourceFormatError, "duplicate JSON key"):
            LocalJsonPortfolioSnapshotLoader().load(path)

    def test_missing_file_directory_and_oversized_file_rejected(self):
        loader = LocalJsonPortfolioSnapshotLoader(max_bytes=32)
        with self.assertRaises(PortfolioSourceError):
            loader.load(self.root / "missing.json")
        with self.assertRaises(PortfolioSourceError):
            loader.load(self.root)
        path = self.write_text("x" * 33)
        with self.assertRaises(PortfolioSourceFormatError):
            loader.load(path)

    def test_utf8_unicode_and_inactive_positions(self):
        snapshot = self.load(
            self.payload(
                positions=(
                    self.position(position_id="active", symbol="台積電.TW", position_status="ACTIVE"),
                    self.position(position_id="closed", symbol="2454.TW", position_status="CLOSED"),
                    self.position(position_id="ignored", symbol="NVDA", position_status="IGNORED"),
                )
            )
        )

        self.assertEqual(tuple(position.position_status for position in snapshot.positions), (
            PositionStatus.ACTIVE,
            PositionStatus.CLOSED,
            PositionStatus.IGNORED,
        ))
        self.assertEqual(snapshot.active_position_ids, ("active",))

    def test_deterministic_repeat_load_and_source_order_not_identity(self):
        first_payload = self.payload(
            positions=(
                self.position(position_id="position_b", symbol="2454.TW"),
                self.position(position_id="position_a", symbol="2330.TW"),
            )
        )
        second_payload = self.payload(
            positions=(
                self.position(position_id="position_a", symbol="2330.TW"),
                self.position(position_id="position_b", symbol="2454.TW"),
            )
        )

        first = self.load(first_payload)
        repeat = LocalJsonPortfolioSnapshotLoader().load(self.write_json(first_payload, "repeat.json"))
        second = self.load(second_payload)

        self.assertEqual(first, repeat)
        self.assertEqual(first.checksum, second.checksum)
        self.assertEqual(tuple(position.position_id for position in first.positions), ("position_a", "position_b"))

    def test_loader_has_no_forbidden_runtime_boundaries(self):
        source = (SRC_PATH / "portfolio_sources" / "local_json_portfolio_snapshot_loader.py").read_text()
        forbidden_terms = (
            "yfinance",
            "Yahoo",
            "TWSE",
            "TPEx",
            "historical_price_service",
            "features.calculators",
            "TECH_",
            "ProductionTechnicalRiskPolicy",
            "ExactVersionPolicyResolver",
            "risk_oos",
            "RiskSignalProductionInput",
            "RiskEvaluationInput",
            "PortfolioRiskGenerationService",
            "risk_persistence",
            "sqlite3",
            "write_text",
            "write_bytes",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
