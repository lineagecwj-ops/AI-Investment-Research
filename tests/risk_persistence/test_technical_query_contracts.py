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

from portfolio_generation import TechnicalRiskArtifactAdapter
from risk import HoldingType
from risk import PortfolioPosition
from risk import RiskArtifactGenerator
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskContext
from risk import RiskSeverity
from risk import RiskSignal
from risk_evaluation import ProducedRiskSignal
from risk_evaluation import TechnicalRiskProductionResult
from risk_persistence import RiskArtifactIndexCorruptionError
from risk_persistence import RiskArtifactPersistenceError
from risk_persistence import RiskArtifactRepository
from risk_persistence import TechnicalRiskArtifactIndexRecord
from risk_persistence import TechnicalRiskArtifactQueryRepository


class _TechnicalQueryRepositoryFake:
    def __init__(self, artifacts):
        self.artifacts = tuple(artifacts)

    def get_latest_by_position(self, portfolio_id, position_id):
        _validate_query_ids(portfolio_id, position_id)
        history = self.list_history_by_position(portfolio_id, position_id, limit=1)
        return history[0] if history else None

    def list_history_by_position(self, portfolio_id, position_id, *, limit=None):
        _validate_query_ids(portfolio_id, position_id)
        _validate_limit(limit)
        rows = tuple(
            (TechnicalRiskArtifactIndexRecord.from_artifact(artifact), artifact)
            for artifact in self.artifacts
        )
        matches = tuple(
            item
            for item in rows
            if item[0].portfolio_id == portfolio_id and item[0].position_id == position_id
        )
        ordered = tuple(sorted(matches, key=lambda item: _latest_key(item[0]), reverse=True))
        artifacts = tuple(item[1] for item in ordered)
        return artifacts if limit is None else artifacts[:limit]

    def list_latest_by_portfolio(self, portfolio_id, *, severity=None):
        if not isinstance(portfolio_id, str) or not portfolio_id:
            raise RiskArtifactPersistenceError("portfolio_id must be a non-empty string.")
        if severity is not None and not isinstance(severity, RiskSeverity):
            raise RiskArtifactPersistenceError("severity must be RiskSeverity or None.")
        rows = tuple(
            (TechnicalRiskArtifactIndexRecord.from_artifact(artifact), artifact)
            for artifact in self.artifacts
        )
        latest_by_position = {}
        for record, artifact in sorted(rows, key=lambda item: _latest_key(item[0]), reverse=True):
            if record.portfolio_id != portfolio_id:
                continue
            latest_by_position.setdefault(record.position_id, (record, artifact))
        selected = tuple(latest_by_position.values())
        if severity is not None:
            selected = tuple(item for item in selected if item[0].severity == severity)
        return tuple(
            item[1]
            for item in sorted(
                selected,
                key=lambda item: (item[0].position_id, item[0].symbol, item[0].artifact_id),
            )
        )


def _latest_key(record):
    return (record.analysis_date, record.created_at, record.artifact_id)


def _validate_query_ids(portfolio_id, position_id):
    if not isinstance(portfolio_id, str) or not portfolio_id:
        raise RiskArtifactPersistenceError("portfolio_id must be a non-empty string.")
    if not isinstance(position_id, str) or not position_id:
        raise RiskArtifactPersistenceError("position_id must be a non-empty string.")


def _validate_limit(limit):
    if limit is None:
        return
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise RiskArtifactPersistenceError("limit must be None or a positive integer.")


class TechnicalRiskQueryContractsTestCase(unittest.TestCase):

    def created_at(self, day=15, hour=12):
        return datetime(2026, 8, day, hour, 0, tzinfo=UTC)

    def context(self, *, portfolio_id="portfolio_001", symbol="2330.TW", analysis_date=date(2026, 8, 15)):
        return RiskContext(
            portfolio_id=portfolio_id,
            symbol=symbol,
            analysis_date=analysis_date,
            feature_version="technical_risk_feature_set_v1",
            model_version=None,
            calculation_id=f"risk_calc_{portfolio_id}_{analysis_date.isoformat()}",
        )

    def position(self, *, symbol="2330.TW"):
        return PortfolioPosition(
            symbol=symbol,
            shares=Decimal("10.00"),
            average_cost=Decimal("650.50"),
            holding_type=HoldingType.FRACTIONAL_SHARE,
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )

    def artifact(
        self,
        *,
        artifact_id="technical_artifact_001",
        portfolio_id="portfolio_001",
        position_id="position_001",
        symbol="2330.TW",
        severity=RiskSeverity.MEDIUM,
        analysis_date=date(2026, 8, 15),
        valuation_date=date(2026, 8, 14),
        created_at=None,
    ):
        context = self.context(portfolio_id=portfolio_id, symbol=symbol, analysis_date=analysis_date)
        signal = RiskSignal(
            risk_id="TECHNICAL_DOWNSIDE_RISK_V1",
            symbol=symbol,
            category=RiskCategory.TECHNICAL,
            severity=severity,
            trigger_reason="TREND_WEAKNESS",
            created_at=created_at or self.created_at(),
        )
        produced_signal = ProducedRiskSignal(
            signal=signal,
            policy_id="TECH_RISK_POLICY_V1",
            policy_version="v1",
            producer_version="TECHNICAL_RISK_SIGNAL_PRODUCER_V1",
            source_feature_ids=("TECH_AS_OF_CLOSE_V1", "TECH_SMA20_V1", "TECH_SMA60_V1", "TECH_RSI14_V1"),
            source_checksums=("close_checksum", "sma20_checksum", "sma60_checksum", "rsi14_checksum"),
            calculation_id=context.calculation_id,
            policy_checksum="policy_checksum_001",
            evaluation_id=f"technical_eval_{artifact_id}",
            evaluation_checksum=f"evaluation_checksum_{artifact_id}",
            portfolio_id=portfolio_id,
            position_id=position_id,
            as_of_date=analysis_date,
            valuation_date=valuation_date,
        )
        result = TechnicalRiskProductionResult(
            produced_signal=produced_signal,
            risk_assessment=RiskAssessment.from_signals(
                portfolio_id=portfolio_id,
                symbol=symbol,
                signals=(signal,),
                assessment_date=analysis_date,
            ),
        )
        return TechnicalRiskArtifactAdapter().build(
            result=result,
            context=context,
            position=self.position(symbol=symbol),
            artifact_id=artifact_id,
            created_at=created_at or self.created_at(),
        )

    def index_record(self, **overrides):
        values = {
            "artifact_id": "artifact_001",
            "portfolio_id": "portfolio_001",
            "position_id": "position_001",
            "symbol": "2330.TW",
            "severity": RiskSeverity.LOW,
            "analysis_date": date(2026, 8, 15),
            "valuation_date": date(2026, 8, 14),
            "created_at": self.created_at(),
            "calculation_id": "risk_calc_001",
            "policy_id": "TECH_RISK_POLICY_V1",
            "policy_version": "v1",
            "policy_checksum": "policy_checksum_001",
            "evaluation_id": "technical_eval_001",
            "evaluation_checksum": "evaluation_checksum_001",
            "producer_version": "TECHNICAL_RISK_SIGNAL_PRODUCER_V1",
        }
        values.update(overrides)
        return TechnicalRiskArtifactIndexRecord(**values)

    def test_query_repository_protocol_structural_compatibility(self):
        repository = _TechnicalQueryRepositoryFake(())

        self.assertIsInstance(repository, TechnicalRiskArtifactQueryRepository)

    def test_query_repository_protocol_methods_exact(self):
        self.assertEqual(
            tuple(inspect.signature(TechnicalRiskArtifactQueryRepository.get_latest_by_position).parameters),
            ("self", "portfolio_id", "position_id"),
        )
        history_parameters = inspect.signature(
            TechnicalRiskArtifactQueryRepository.list_history_by_position
        ).parameters
        self.assertEqual(tuple(history_parameters), ("self", "portfolio_id", "position_id", "limit"))
        self.assertEqual(history_parameters["limit"].kind, inspect.Parameter.KEYWORD_ONLY)
        portfolio_parameters = inspect.signature(
            TechnicalRiskArtifactQueryRepository.list_latest_by_portfolio
        ).parameters
        self.assertEqual(tuple(portfolio_parameters), ("self", "portfolio_id", "severity"))
        self.assertEqual(portfolio_parameters["severity"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_query_repository_has_no_write_or_search_apis(self):
        repository = _TechnicalQueryRepositoryFake(())
        forbidden = (
            "save",
            "delete",
            "update",
            "save_index",
            "index_artifact",
            "rebuild_index",
            "search",
            "pagination",
            "offset",
            "cursor",
        )
        for name in forbidden:
            with self.subTest(name=name):
                self.assertFalse(hasattr(repository, name))

    def test_index_record_is_frozen(self):
        record = self.index_record()

        with self.assertRaises(FrozenInstanceError):
            record.position_id = "other"

    def test_low_medium_high_are_valid_index_severities(self):
        for severity in (RiskSeverity.LOW, RiskSeverity.MEDIUM, RiskSeverity.HIGH):
            with self.subTest(severity=severity):
                self.assertEqual(self.index_record(severity=severity).severity, severity)

    def test_critical_is_rejected_for_technical_v1_index_record(self):
        with self.assertRaisesRegex(RiskArtifactPersistenceError, "CRITICAL"):
            self.index_record(severity=RiskSeverity.CRITICAL)

    def test_index_record_rejects_invalid_text_fields(self):
        fields = (
            "artifact_id",
            "portfolio_id",
            "position_id",
            "symbol",
            "calculation_id",
            "policy_id",
            "policy_version",
            "policy_checksum",
            "evaluation_id",
            "evaluation_checksum",
            "producer_version",
        )
        for field_name in fields:
            with self.subTest(field_name=field_name):
                with self.assertRaises(RiskArtifactPersistenceError):
                    self.index_record(**{field_name: ""})

    def test_index_record_rejects_invalid_severity(self):
        with self.assertRaises(RiskArtifactPersistenceError):
            self.index_record(severity="UNKNOWN")

    def test_index_record_rejects_invalid_dates(self):
        for field_name in ("analysis_date", "valuation_date"):
            with self.subTest(field_name=field_name):
                with self.assertRaises(RiskArtifactPersistenceError):
                    self.index_record(**{field_name: self.created_at()})

    def test_index_record_rejects_naive_created_at(self):
        with self.assertRaises(RiskArtifactPersistenceError):
            self.index_record(created_at=datetime(2026, 8, 15, 12, 0))

    def test_from_artifact_extracts_technical_projection(self):
        artifact = self.artifact(severity=RiskSeverity.HIGH)

        record = TechnicalRiskArtifactIndexRecord.from_artifact(artifact)

        self.assertEqual(record.artifact_id, artifact.artifact_id)
        self.assertEqual(record.portfolio_id, "portfolio_001")
        self.assertEqual(record.position_id, "position_001")
        self.assertEqual(record.symbol, "2330.TW")
        self.assertEqual(record.severity, RiskSeverity.HIGH)
        self.assertEqual(record.analysis_date, date(2026, 8, 15))
        self.assertEqual(record.valuation_date, date(2026, 8, 14))
        self.assertEqual(record.calculation_id, artifact.calculation_metadata["calculation_id"])
        self.assertEqual(record.policy_id, "TECH_RISK_POLICY_V1")
        self.assertEqual(record.policy_version, "v1")
        self.assertEqual(record.policy_checksum, "policy_checksum_001")
        self.assertTrue(record.evaluation_id)
        self.assertTrue(record.evaluation_checksum)
        self.assertEqual(record.producer_version, "TECHNICAL_RISK_SIGNAL_PRODUCER_V1")

    def test_from_artifact_preserves_low(self):
        artifact = self.artifact(severity=RiskSeverity.LOW)

        record = TechnicalRiskArtifactIndexRecord.from_artifact(artifact)

        self.assertEqual(record.severity, RiskSeverity.LOW)

    def test_from_artifact_rejects_non_technical_signal(self):
        artifact = self.artifact()
        signal = replace(artifact.signals[0], category=RiskCategory.MARKET)
        assessment = RiskAssessment.from_signals(
            portfolio_id=artifact.risk_assessment.portfolio_id,
            symbol=artifact.risk_assessment.symbol,
            signals=(signal,),
            assessment_date=artifact.risk_assessment.assessment_date,
        )
        invalid = replace(artifact, signals=(signal,), risk_assessment=assessment)

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            TechnicalRiskArtifactIndexRecord.from_artifact(invalid)

    def test_from_artifact_rejects_multiple_technical_signals(self):
        artifact = self.artifact(severity=RiskSeverity.HIGH)
        second_signal = replace(
            artifact.signals[0],
            risk_id="TECHNICAL_DOWNSIDE_RISK_CONFIRMATION_V1",
            trigger_reason="MOMENTUM_WEAKNESS_CONFIRMATION",
        )
        signals = artifact.signals + (second_signal,)
        assessment = RiskAssessment.from_signals(
            portfolio_id=artifact.risk_assessment.portfolio_id,
            symbol=artifact.risk_assessment.symbol,
            signals=signals,
            assessment_date=artifact.risk_assessment.assessment_date,
        )
        invalid = replace(artifact, signals=signals, risk_assessment=assessment)

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            TechnicalRiskArtifactIndexRecord.from_artifact(invalid)

    def test_from_artifact_rejects_critical_projection(self):
        artifact = self.artifact()
        signal = replace(artifact.signals[0], severity=RiskSeverity.CRITICAL)
        assessment = RiskAssessment.from_signals(
            portfolio_id=artifact.risk_assessment.portfolio_id,
            symbol=artifact.risk_assessment.symbol,
            signals=(signal,),
            assessment_date=artifact.risk_assessment.assessment_date,
        )
        invalid = replace(artifact, signals=(signal,), risk_assessment=assessment)

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            TechnicalRiskArtifactIndexRecord.from_artifact(invalid)

    def test_from_artifact_rejects_missing_technical_metadata(self):
        artifact = self.artifact()
        metadata = dict(artifact.calculation_metadata)
        metadata.pop("technical_position_id")
        invalid = replace(artifact, calculation_metadata=metadata)

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            TechnicalRiskArtifactIndexRecord.from_artifact(invalid)

    def test_from_artifact_rejects_portfolio_mismatch(self):
        artifact = self.artifact()
        invalid = replace(
            artifact,
            calculation_metadata={**artifact.calculation_metadata, "portfolio_id": "other_portfolio"},
        )

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            TechnicalRiskArtifactIndexRecord.from_artifact(invalid)

    def test_from_artifact_rejects_symbol_mismatch(self):
        artifact = self.artifact()
        invalid = replace(
            artifact,
            calculation_metadata={**artifact.calculation_metadata, "symbol": "2317.TW"},
        )

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            TechnicalRiskArtifactIndexRecord.from_artifact(invalid)

    def test_from_artifact_rejects_as_of_date_mismatch(self):
        artifact = self.artifact()
        invalid = replace(
            artifact,
            calculation_metadata={**artifact.calculation_metadata, "technical_as_of_date": "2026-08-14"},
        )

        with self.assertRaises(RiskArtifactIndexCorruptionError):
            TechnicalRiskArtifactIndexRecord.from_artifact(invalid)

    def test_same_symbol_different_positions_are_distinct(self):
        first = self.artifact(artifact_id="artifact_a", position_id="position_a", symbol="SAME")
        second = self.artifact(artifact_id="artifact_b", position_id="position_b", symbol="SAME")

        records = tuple(TechnicalRiskArtifactIndexRecord.from_artifact(item) for item in (first, second))

        self.assertEqual(tuple(record.symbol for record in records), ("SAME", "SAME"))
        self.assertEqual(tuple(record.position_id for record in records), ("position_a", "position_b"))

    def test_cross_portfolio_same_position_id_is_distinct(self):
        first = self.artifact(artifact_id="artifact_a", portfolio_id="portfolio_a", position_id="position_shared")
        second = self.artifact(artifact_id="artifact_b", portfolio_id="portfolio_b", position_id="position_shared")

        records = tuple(TechnicalRiskArtifactIndexRecord.from_artifact(item) for item in (first, second))

        self.assertEqual(
            tuple((record.portfolio_id, record.position_id) for record in records),
            (("portfolio_a", "position_shared"), ("portfolio_b", "position_shared")),
        )

    def test_latest_by_position_uses_deterministic_ordering(self):
        older = self.artifact(
            artifact_id="artifact_old",
            position_id="position_001",
            analysis_date=date(2026, 8, 14),
            created_at=self.created_at(14, 12),
        )
        newest = self.artifact(
            artifact_id="artifact_new",
            position_id="position_001",
            analysis_date=date(2026, 8, 15),
            created_at=self.created_at(15, 12),
        )
        tie = self.artifact(
            artifact_id="artifact_z",
            position_id="position_001",
            analysis_date=date(2026, 8, 15),
            created_at=self.created_at(15, 12),
        )
        repository = _TechnicalQueryRepositoryFake((older, newest, tie))

        self.assertEqual(repository.get_latest_by_position("portfolio_001", "position_001").artifact_id, "artifact_z")

    def test_history_by_position_newest_first_and_limit(self):
        artifacts = (
            self.artifact(artifact_id="artifact_old", position_id="position_001", analysis_date=date(2026, 8, 13)),
            self.artifact(artifact_id="artifact_mid", position_id="position_001", analysis_date=date(2026, 8, 14)),
            self.artifact(artifact_id="artifact_new", position_id="position_001", analysis_date=date(2026, 8, 15)),
        )
        repository = _TechnicalQueryRepositoryFake(artifacts)

        self.assertEqual(
            tuple(artifact.artifact_id for artifact in repository.list_history_by_position("portfolio_001", "position_001")),
            ("artifact_new", "artifact_mid", "artifact_old"),
        )
        self.assertEqual(
            tuple(artifact.artifact_id for artifact in repository.list_history_by_position("portfolio_001", "position_001", limit=2)),
            ("artifact_new", "artifact_mid"),
        )

    def test_limit_validation(self):
        repository = _TechnicalQueryRepositoryFake(())
        for limit in (0, -1, True, "2"):
            with self.subTest(limit=limit):
                with self.assertRaises(RiskArtifactPersistenceError):
                    repository.list_history_by_position("portfolio_001", "position_001", limit=limit)

    def test_portfolio_latest_returns_one_artifact_per_position(self):
        old_high = self.artifact(
            artifact_id="artifact_position_a_old",
            position_id="position_a",
            symbol="SAME",
            severity=RiskSeverity.HIGH,
            analysis_date=date(2026, 8, 14),
        )
        latest_low = self.artifact(
            artifact_id="artifact_position_a_latest",
            position_id="position_a",
            severity=RiskSeverity.LOW,
            analysis_date=date(2026, 8, 15),
        )
        position_b = self.artifact(
            artifact_id="artifact_position_b_latest",
            position_id="position_b",
            severity=RiskSeverity.MEDIUM,
            analysis_date=date(2026, 8, 15),
        )
        repository = _TechnicalQueryRepositoryFake((old_high, latest_low, position_b))

        self.assertEqual(
            tuple(artifact.artifact_id for artifact in repository.list_latest_by_portfolio("portfolio_001")),
            ("artifact_position_a_latest", "artifact_position_b_latest"),
        )

    def test_severity_filter_applies_after_latest_selection(self):
        old_high = self.artifact(
            artifact_id="artifact_position_a_old",
            position_id="position_a",
            severity=RiskSeverity.HIGH,
            analysis_date=date(2026, 8, 14),
        )
        latest_low = self.artifact(
            artifact_id="artifact_position_a_latest",
            position_id="position_a",
            symbol="SAME",
            severity=RiskSeverity.LOW,
            analysis_date=date(2026, 8, 15),
        )
        latest_high = self.artifact(
            artifact_id="artifact_position_b_latest",
            position_id="position_b",
            symbol="SAME",
            severity=RiskSeverity.HIGH,
            analysis_date=date(2026, 8, 15),
        )
        repository = _TechnicalQueryRepositoryFake((latest_high, latest_low, old_high))

        self.assertEqual(
            tuple(artifact.artifact_id for artifact in repository.list_latest_by_portfolio("portfolio_001", severity=RiskSeverity.HIGH)),
            ("artifact_position_b_latest",),
        )
        self.assertEqual(
            tuple(artifact.artifact_id for artifact in repository.list_latest_by_portfolio("portfolio_001", severity=RiskSeverity.LOW)),
            ("artifact_position_a_latest",),
        )

    def test_invalid_query_identifiers_fail_closed(self):
        repository = _TechnicalQueryRepositoryFake(())
        invalid_pairs = (("", "position_001"), ("portfolio_001", ""), (None, "position_001"))
        for portfolio_id, position_id in invalid_pairs:
            with self.subTest(portfolio_id=portfolio_id, position_id=position_id):
                with self.assertRaises(RiskArtifactPersistenceError):
                    repository.get_latest_by_position(portfolio_id, position_id)

    def test_invalid_severity_filter_fails_closed(self):
        repository = _TechnicalQueryRepositoryFake(())

        with self.assertRaises(RiskArtifactPersistenceError):
            repository.list_latest_by_portfolio("portfolio_001", severity="HIGH")

    def test_index_corruption_error_hierarchy(self):
        error = RiskArtifactIndexCorruptionError("artifact_001")

        self.assertIsInstance(error, RiskArtifactIndexCorruptionError)
        self.assertEqual(error.artifact_id, "artifact_001")

    def test_public_exports(self):
        import risk_persistence

        self.assertIs(risk_persistence.TechnicalRiskArtifactQueryRepository, TechnicalRiskArtifactQueryRepository)
        self.assertIs(risk_persistence.TechnicalRiskArtifactIndexRecord, TechnicalRiskArtifactIndexRecord)
        self.assertIs(risk_persistence.RiskArtifactIndexCorruptionError, RiskArtifactIndexCorruptionError)

    def test_contract_source_has_no_sqlite_or_runtime_dependencies(self):
        source = (SRC_PATH / "risk_persistence" / "technical_query_contracts.py").read_text()
        forbidden = (
            "sqlite3",
            "CREATE TABLE",
            "ALTER TABLE",
            "PRAGMA",
            "portfolio_generation",
            "risk_evaluation",
            "risk_oos",
            "risk_integration",
            "dashboard",
            "datetime.now",
            "datetime.utcnow",
            "time.time",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, source)

    def test_existing_risk_artifact_repository_protocol_unchanged(self):
        self.assertEqual(
            tuple(inspect.signature(RiskArtifactRepository.save).parameters),
            ("self", "artifact"),
        )
        self.assertEqual(
            tuple(inspect.signature(RiskArtifactRepository.get_by_artifact_id).parameters),
            ("self", "artifact_id"),
        )

    def test_sqlite_repository_still_has_no_query_apis_or_technical_projection_logic(self):
        source = (SRC_PATH / "risk_persistence" / "sqlite_repository.py").read_text()
        forbidden = (
            "TechnicalRiskArtifactQueryRepository",
            "list_latest_by_portfolio",
            "list_history_by_position",
            "get_latest_by_position",
            "TechnicalRiskArtifactIndexRecord",
            "technical_position_id",
            "technical_policy_id",
            "technical_evaluation_id",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, source)


if __name__ == "__main__":
    unittest.main()
