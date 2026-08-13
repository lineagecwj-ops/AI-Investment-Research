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

from portfolio_state import GenerationIdentityMismatchError
from portfolio_state import HoldingType
from portfolio_state import PortfolioPositionState
from portfolio_state import PortfolioPositionStateError
from portfolio_state import PortfolioSnapshot
from portfolio_state import PortfolioSnapshotChecksumMismatchError
from portfolio_state import PortfolioSnapshotError
from portfolio_state import PositionStatus
from portfolio_state import RiskEvaluationInput
from portfolio_state import RiskEvaluationInputError


class PortfolioStateContractTestCase(unittest.TestCase):

    def created_at(self):
        return datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    def position(
        self,
        *,
        position_id="position_001",
        symbol="2330.TW",
        shares=Decimal("10"),
        average_cost=Decimal("650.00"),
        holding_type="whole_share",
        position_status="ACTIVE",
        portfolio_id="portfolio_synthetic_001",
    ):
        return PortfolioPositionState(
            portfolio_id=portfolio_id,
            position_id=position_id,
            symbol=symbol,
            shares=shares,
            average_cost=average_cost,
            currency="twd",
            position_status=position_status,
            holding_type=holding_type,
            acquisition_date=date(2026, 1, 5),
        )

    def snapshot(self, *, positions=None, snapshot_id="snapshot_001", feature_seed="source_manual_v1"):
        return PortfolioSnapshot(
            snapshot_id=snapshot_id,
            portfolio_id="portfolio_synthetic_001",
            as_of_date=date(2026, 8, 13),
            valuation_date=date(2026, 8, 12),
            positions=positions if positions is not None else (self.position(),),
            created_at=self.created_at(),
            source_lineage={
                "source_type": "manual_contract_test",
                "source_version": feature_seed,
            },
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

    def test_whole_share_position(self):
        position = self.position()

        self.assertEqual(position.holding_type, HoldingType.WHOLE_SHARE)
        self.assertEqual(position.shares, Decimal("10"))
        self.assertEqual(position.currency, "TWD")

    def test_fractional_share_position(self):
        position = self.position(
            shares=Decimal("15.125"),
            holding_type="fractional_share",
        )

        self.assertEqual(position.holding_type, HoldingType.FRACTIONAL_SHARE)
        self.assertEqual(position.shares, Decimal("15.125"))

    def test_decimal_precision(self):
        position = self.position(
            shares=Decimal("0.125"),
            average_cost=Decimal("650.125"),
            holding_type="fractional_share",
        )

        self.assertEqual(position.identity["shares"], "0.125")
        self.assertEqual(position.identity["average_cost"], "650.125")

    def test_position_status(self):
        active = self.position(position_status="ACTIVE")
        closed = self.position(position_id="position_closed", position_status="CLOSED")
        ignored = self.position(position_id="position_ignored", position_status="IGNORED")

        self.assertEqual(active.position_status, PositionStatus.ACTIVE)
        self.assertEqual(closed.position_status, PositionStatus.CLOSED)
        self.assertEqual(ignored.position_status, PositionStatus.IGNORED)

    def test_duplicate_position_id_rejection(self):
        with self.assertRaisesRegex(PortfolioSnapshotError, "Duplicate portfolio position_id"):
            self.snapshot(positions=(self.position(), self.position(symbol="2454.TW")))

    def test_deterministic_snapshot_ordering(self):
        later = self.position(position_id="position_b", symbol="2454.TW")
        earlier = self.position(position_id="position_a", symbol="2330.TW")
        snapshot = self.snapshot(positions=(later, earlier))

        self.assertEqual(tuple(position.position_id for position in snapshot.positions), ("position_a", "position_b"))

    def test_deterministic_snapshot_checksum(self):
        first = self.snapshot(
            positions=(
                self.position(position_id="position_b", symbol="2454.TW"),
                self.position(position_id="position_a", symbol="2330.TW"),
            )
        )
        second = self.snapshot(
            positions=(
                self.position(position_id="position_a", symbol="2330.TW"),
                self.position(position_id="position_b", symbol="2454.TW"),
            )
        )

        self.assertEqual(first.checksum, second.checksum)

    def test_snapshot_immutability(self):
        snapshot = self.snapshot()

        with self.assertRaises(FrozenInstanceError):
            snapshot.snapshot_id = "changed"
        with self.assertRaises(TypeError):
            snapshot.source_lineage["source_type"] = "changed"

    def test_active_closed_ignored_preservation(self):
        snapshot = self.snapshot(
            positions=(
                self.position(position_id="position_active", position_status="ACTIVE"),
                self.position(position_id="position_closed", position_status="CLOSED"),
                self.position(position_id="position_ignored", position_status="IGNORED"),
            )
        )

        self.assertEqual(
            tuple(position.position_status for position in snapshot.positions),
            (PositionStatus.ACTIVE, PositionStatus.CLOSED, PositionStatus.IGNORED),
        )

    def test_risk_evaluation_input_active_only_scope(self):
        snapshot = self.snapshot(
            positions=(
                self.position(position_id="position_active", position_status="ACTIVE"),
                self.position(position_id="position_closed", position_status="CLOSED"),
                self.position(position_id="position_ignored", position_status="IGNORED"),
            )
        )

        evaluation_input = self.evaluation_input(snapshot)

        self.assertEqual(evaluation_input.active_position_ids, ("position_active",))
        self.assertEqual(len(snapshot.positions), 3)

    def test_same_generation_input_same_identity(self):
        snapshot = self.snapshot()
        first = self.evaluation_input(snapshot)
        second = self.evaluation_input(snapshot)

        self.assertEqual(first.generation_key, second.generation_key)
        self.assertEqual(first.calculation_id, second.calculation_id)

    def test_different_snapshot_changes_identity(self):
        first = self.evaluation_input(self.snapshot(snapshot_id="snapshot_001"))
        second = self.evaluation_input(self.snapshot(snapshot_id="snapshot_002"))

        self.assertNotEqual(first.generation_key, second.generation_key)
        self.assertNotEqual(first.calculation_id, second.calculation_id)

    def test_different_feature_version_changes_identity(self):
        snapshot = self.snapshot()

        self.assertNotEqual(
            self.evaluation_input(snapshot, feature_version="feature_set_v1").generation_key,
            self.evaluation_input(snapshot, feature_version="feature_set_v2").generation_key,
        )

    def test_different_policy_version_changes_identity(self):
        snapshot = self.snapshot()

        self.assertNotEqual(
            self.evaluation_input(snapshot, risk_policy_version="risk_policy_v1").generation_key,
            self.evaluation_input(snapshot, risk_policy_version="risk_policy_v2").generation_key,
        )
        self.assertNotEqual(
            self.evaluation_input(snapshot, monitoring_policy_version="monitoring_policy_v1").generation_key,
            self.evaluation_input(snapshot, monitoring_policy_version="monitoring_policy_v2").generation_key,
        )

    def test_nullable_model_version_deterministic(self):
        snapshot = self.snapshot()
        first = self.evaluation_input(snapshot, model_version=None)
        second = self.evaluation_input(snapshot, model_version=None)
        with_model = self.evaluation_input(snapshot, model_version="baseline_model_v1")

        self.assertEqual(first.generation_key, second.generation_key)
        self.assertNotEqual(first.generation_key, with_model.generation_key)
        self.assertEqual(first.identity_material["model_version"], "<none>")

    def test_as_of_date_vs_valuation_date_semantics(self):
        snapshot = self.snapshot()
        evaluation_input = self.evaluation_input(snapshot)

        self.assertEqual(snapshot.as_of_date, date(2026, 8, 13))
        self.assertEqual(snapshot.valuation_date, date(2026, 8, 12))
        self.assertEqual(evaluation_input.as_of_date, date(2026, 8, 13))
        self.assertEqual(evaluation_input.valuation_date, date(2026, 8, 12))

    def test_timezone_aware_created_at(self):
        with self.assertRaisesRegex(PortfolioSnapshotError, "timezone-aware"):
            PortfolioSnapshot(
                snapshot_id="snapshot_bad_time",
                portfolio_id="portfolio_synthetic_001",
                as_of_date=date(2026, 8, 13),
                valuation_date=date(2026, 8, 12),
                positions=(self.position(),),
                created_at=datetime(2026, 8, 13, 12, 0),
                source_lineage={"source_type": "manual", "source_version": "v1"},
            )

    def test_validation_fail_closed(self):
        with self.assertRaisesRegex(PortfolioPositionStateError, "portfolio_id"):
            self.position(portfolio_id="")
        with self.assertRaisesRegex(PortfolioPositionStateError, "position_status"):
            self.position(position_status="UNKNOWN")
        with self.assertRaisesRegex(PortfolioPositionStateError, "currency"):
            PortfolioPositionState(
                portfolio_id="portfolio_synthetic_001",
                position_id="position_bad_currency",
                symbol="2330.TW",
                shares=Decimal("10"),
                average_cost=Decimal("650.00"),
                currency="TWDD",
                position_status="ACTIVE",
                holding_type="whole_share",
                acquisition_date=date(2026, 1, 5),
            )
        with self.assertRaisesRegex(PortfolioPositionStateError, "Decimal"):
            self.position(shares=10.5)
        with self.assertRaisesRegex(PortfolioSnapshotError, "portfolio_id mismatch"):
            self.snapshot(positions=(self.position(portfolio_id="other_portfolio"),))
        with self.assertRaises(PortfolioSnapshotChecksumMismatchError):
            replace(self.snapshot(), checksum="bad_checksum")
        with self.assertRaisesRegex(RiskEvaluationInputError, "feature_version"):
            self.evaluation_input(feature_version="")
        with self.assertRaises(GenerationIdentityMismatchError):
            replace(self.evaluation_input(), generation_key="bad_generation_key")

    def test_portfolio_state_package_does_not_import_runtime_boundaries(self):
        source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "portfolio_state").glob("*.py"))
        )

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
            "serialize_risk_monitoring_artifact",
            "deserialize_risk_monitoring_artifact",
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
