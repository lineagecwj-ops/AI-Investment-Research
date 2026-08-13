import sys
import unittest
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY
from risk_oos import HISTORICAL_RISK_FEATURE_SET_V1
from risk_oos import HistoricalRiskFeatureExclusion
from risk_oos import HistoricalRiskFeatureObservation
from risk_oos import TARGET_MAE20
from risk_oos import TARGET_MAE60
from risk_oos import TECHNICAL_RISK_V1_FEATURE_SET_ID
from risk_oos import AlignedTechnicalRiskOOSRow
from risk_oos import TechnicalRiskOOSDatasetBuilder
from risk_oos import TechnicalRiskOOSDatasetError
from risk_oos import TechnicalRiskOOSDatasetSpec
from risk_oos import TechnicalRiskOOSExclusionReason
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskOOSSplitSpec
from targets import TARGET_ARTIFACT_SCHEMA_VERSION
from targets import TARGET_CHECKSUM_CONTRACT_VERSION
from targets import TargetArtifact
from targets import TargetWindowLineage


class AlignedRiskOOSDatasetTestCase(unittest.TestCase):

    def split_specs(self):
        return (
            TechnicalRiskOOSSplitSpec(
                "development_2026_h1",
                TechnicalRiskOOSSplitRole.DEVELOPMENT,
                date(2026, 1, 1),
                date(2026, 6, 30),
            ),
            TechnicalRiskOOSSplitSpec(
                "validation_2026_q3",
                TechnicalRiskOOSSplitRole.VALIDATION,
                date(2026, 7, 1),
                date(2026, 9, 30),
            ),
            TechnicalRiskOOSSplitSpec(
                "holdout_2026_q4",
                TechnicalRiskOOSSplitRole.HOLDOUT,
                date(2026, 10, 1),
                date(2026, 12, 31),
            ),
        )

    def spec(self, splits=None, **overrides):
        values = {
            "dataset_spec_id": "technical_risk_oos_dataset_v1",
            "dataset_spec_version": "v1",
            "feature_set_id": TECHNICAL_RISK_V1_FEATURE_SET_ID,
            "split_specs": self.split_specs() if splits is None else splits,
        }
        values.update(overrides)
        return TechnicalRiskOOSDatasetSpec(**values)

    def observation(self, evaluation_date=date(2026, 5, 1), symbol="2330.TW", checksum_suffix="001"):
        return HistoricalRiskFeatureObservation(
            observation_id=f"obs_{symbol}_{evaluation_date.isoformat()}_{checksum_suffix}",
            observation_checksum=f"obs_checksum_{checksum_suffix}",
            symbol=symbol,
            evaluation_date=evaluation_date,
            feature_set_id=TECHNICAL_RISK_V1_FEATURE_SET_ID,
            source_snapshot_id="frozen_snapshot_v1",
            source_snapshot_checksum="snapshot_checksum_001",
            calculation_id="feature_calc_001",
            feature_ids=HISTORICAL_RISK_FEATURE_SET_V1,
            feature_versions={feature_id: "v1" for feature_id in HISTORICAL_RISK_FEATURE_SET_V1},
            formula_versions={feature_id: f"{feature_id}_formula_v1" for feature_id in HISTORICAL_RISK_FEATURE_SET_V1},
            as_of_close=100.0,
            sma20=98.0,
            sma60=95.0,
            rsi14=45.0,
        )

    def target(
        self,
        target_id,
        reference_date=date(2026, 5, 1),
        symbol="2330.TW",
        target_value=-0.05,
        checksum_suffix="001",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 6, 15),
        observations_used=None,
        validation_status="PASS",
        checksum=None,
    ):
        window = 20 if target_id == TARGET_MAE20 else 60
        return TargetArtifact(
            target_id=target_id,
            target_version="v1",
            symbol=symbol,
            reference_date=reference_date,
            target_value=target_value,
            calculation_id=f"{target_id.lower()}_calc_{checksum_suffix}",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            checksum=f"{target_id.lower()}_checksum_{checksum_suffix}" if checksum is None else checksum,
            validation_status=validation_status,
            window_lineage=TargetWindowLineage(
                target_start_date=start_date,
                target_end_date=end_date,
                observations_used=window if observations_used is None else observations_used,
            ),
            schema_version=TARGET_ARTIFACT_SCHEMA_VERSION,
            checksum_contract_version=TARGET_CHECKSUM_CONTRACT_VERSION,
        )

    def build(self, observations, mae20=None, mae60=None, spec=None, upstream=()):
        return TechnicalRiskOOSDatasetBuilder().build(
            self.spec() if spec is None else spec,
            observations,
            () if mae20 is None else mae20,
            () if mae60 is None else mae60,
            upstream_feature_exclusions=upstream,
        )

    def reason(self, result):
        self.assertEqual(len(result.included_rows), 0)
        self.assertEqual(len(result.excluded_records), 1)
        return result.excluded_records[0].reason

    def test_development_row_with_mae20_and_mae60_inside_split_included(self):
        observation = self.observation()
        result = self.build(
            (observation,),
            mae20=(self.target(TARGET_MAE20, end_date=date(2026, 5, 29)),),
            mae60=(self.target(TARGET_MAE60, end_date=date(2026, 6, 30)),),
        )

        self.assertEqual(len(result.included_rows), 1)
        row = result.included_rows[0]
        self.assertEqual(row.split_role, TechnicalRiskOOSSplitRole.DEVELOPMENT)
        self.assertEqual(row.mae20_target_end_date, date(2026, 5, 29))
        self.assertEqual(row.mae60_target_end_date, date(2026, 6, 30))

    def test_mae60_crossing_development_end_excluded_even_when_mae20_inside(self):
        observation = self.observation()
        result = self.build(
            (observation,),
            mae20=(self.target(TARGET_MAE20, end_date=date(2026, 5, 29)),),
            mae60=(self.target(TARGET_MAE60, end_date=date(2026, 8, 15)),),
        )

        self.assertEqual(self.reason(result), TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_CROSSES_SPLIT_BOUNDARY)

    def test_validation_row_target_crossing_validation_end_excluded(self):
        observation = self.observation(evaluation_date=date(2026, 8, 1), checksum_suffix="val")
        result = self.build(
            (observation,),
            mae20=(self.target(TARGET_MAE20, reference_date=date(2026, 8, 1), start_date=date(2026, 8, 3), end_date=date(2026, 8, 31)),),
            mae60=(self.target(TARGET_MAE60, reference_date=date(2026, 8, 1), start_date=date(2026, 8, 3), end_date=date(2026, 10, 1)),),
        )

        self.assertEqual(self.reason(result), TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_CROSSES_SPLIT_BOUNDARY)

    def test_holdout_row_with_target_end_inside_holdout_included(self):
        observation = self.observation(evaluation_date=date(2026, 10, 1), checksum_suffix="hold")
        result = self.build(
            (observation,),
            mae20=(self.target(TARGET_MAE20, reference_date=date(2026, 10, 1), start_date=date(2026, 10, 2), end_date=date(2026, 10, 30)),),
            mae60=(self.target(TARGET_MAE60, reference_date=date(2026, 10, 1), start_date=date(2026, 10, 2), end_date=date(2026, 12, 30)),),
        )

        self.assertEqual(len(result.included_rows), 1)
        self.assertEqual(result.included_rows[0].split_role, TechnicalRiskOOSSplitRole.HOLDOUT)

    def test_feature_evaluation_date_mismatch_with_target_reference_date_excluded(self):
        observation = self.observation(evaluation_date=date(2026, 5, 1))
        result = self.build(
            (observation,),
            mae20=(self.target(TARGET_MAE20, reference_date=date(2026, 5, 2), end_date=date(2026, 5, 29)),),
            mae60=(self.target(TARGET_MAE60, end_date=date(2026, 6, 15)),),
        )

        self.assertEqual(self.reason(result), TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_ALIGNMENT_MISMATCH)

    def test_missing_mae20_excluded(self):
        observation = self.observation()
        result = self.build((observation,), mae60=(self.target(TARGET_MAE60),))

        self.assertEqual(self.reason(result), TechnicalRiskOOSExclusionReason.EXCLUDED_INCOMPLETE_MAE20)

    def test_missing_mae60_excluded(self):
        observation = self.observation()
        result = self.build((observation,), mae20=(self.target(TARGET_MAE20),))

        self.assertEqual(self.reason(result), TechnicalRiskOOSExclusionReason.EXCLUDED_INCOMPLETE_MAE60)

    def test_missing_target_never_becomes_zero(self):
        observation = self.observation()
        result = self.build((observation,), mae20=(self.target(TARGET_MAE20),))

        self.assertEqual(len(result.included_rows), 0)
        self.assertNotEqual(result.excluded_records[0].reason.value, "0")
        self.assertEqual(result.summary_counts["included_rows"], 0)

    def test_evaluation_date_outside_every_split_excluded(self):
        observation = self.observation(evaluation_date=date(2027, 1, 2), checksum_suffix="outside")
        result = self.build((observation,), mae20=(self.target(TARGET_MAE20, reference_date=date(2027, 1, 2)),), mae60=(self.target(TARGET_MAE60, reference_date=date(2027, 1, 2)),))

        self.assertEqual(self.reason(result), TechnicalRiskOOSExclusionReason.EXCLUDED_OUTSIDE_SPLIT)

    def test_overlapping_split_specs_fail_whole_build(self):
        overlapping = (
            TechnicalRiskOOSSplitSpec("a", TechnicalRiskOOSSplitRole.DEVELOPMENT, date(2026, 1, 1), date(2026, 6, 30)),
            TechnicalRiskOOSSplitSpec("b", TechnicalRiskOOSSplitRole.VALIDATION, date(2026, 6, 1), date(2026, 9, 30)),
        )

        with self.assertRaisesRegex(TechnicalRiskOOSDatasetError, "Overlapping"):
            self.spec(splits=overlapping)

    def test_feature_input_order_changed_same_rows_and_checksum(self):
        first = self.observation(date(2026, 5, 1), checksum_suffix="a")
        second = self.observation(date(2026, 10, 1), checksum_suffix="b")
        mae20 = (
            self.target(TARGET_MAE20, date(2026, 5, 1), end_date=date(2026, 5, 29), checksum_suffix="a"),
            self.target(TARGET_MAE20, date(2026, 10, 1), start_date=date(2026, 10, 2), end_date=date(2026, 10, 30), checksum_suffix="b"),
        )
        mae60 = (
            self.target(TARGET_MAE60, date(2026, 5, 1), end_date=date(2026, 6, 30), checksum_suffix="a"),
            self.target(TARGET_MAE60, date(2026, 10, 1), start_date=date(2026, 10, 2), end_date=date(2026, 12, 30), checksum_suffix="b"),
        )

        ordered = self.build((first, second), mae20=mae20, mae60=mae60)
        reversed_result = self.build((second, first), mae20=mae20, mae60=mae60)

        self.assertEqual(ordered.included_rows, reversed_result.included_rows)
        self.assertEqual(ordered.dataset_checksum, reversed_result.dataset_checksum)

    def test_mae20_input_order_changed_same_result(self):
        first = self.observation(date(2026, 5, 1), checksum_suffix="a")
        second = self.observation(date(2026, 10, 1), checksum_suffix="b")
        mae20 = (
            self.target(TARGET_MAE20, date(2026, 5, 1), end_date=date(2026, 5, 29), checksum_suffix="a"),
            self.target(TARGET_MAE20, date(2026, 10, 1), start_date=date(2026, 10, 2), end_date=date(2026, 10, 30), checksum_suffix="b"),
        )
        mae60 = (
            self.target(TARGET_MAE60, date(2026, 5, 1), end_date=date(2026, 6, 30), checksum_suffix="a"),
            self.target(TARGET_MAE60, date(2026, 10, 1), start_date=date(2026, 10, 2), end_date=date(2026, 12, 30), checksum_suffix="b"),
        )

        first_result = self.build((first, second), mae20=mae20, mae60=mae60)
        second_result = self.build((first, second), mae20=tuple(reversed(mae20)), mae60=mae60)

        self.assertEqual(first_result, second_result)

    def test_mae60_input_order_changed_same_result(self):
        first = self.observation(date(2026, 5, 1), checksum_suffix="a")
        second = self.observation(date(2026, 10, 1), checksum_suffix="b")
        mae20 = (
            self.target(TARGET_MAE20, date(2026, 5, 1), end_date=date(2026, 5, 29), checksum_suffix="a"),
            self.target(TARGET_MAE20, date(2026, 10, 1), start_date=date(2026, 10, 2), end_date=date(2026, 10, 30), checksum_suffix="b"),
        )
        mae60 = (
            self.target(TARGET_MAE60, date(2026, 5, 1), end_date=date(2026, 6, 30), checksum_suffix="a"),
            self.target(TARGET_MAE60, date(2026, 10, 1), start_date=date(2026, 10, 2), end_date=date(2026, 12, 30), checksum_suffix="b"),
        )

        first_result = self.build((first, second), mae20=mae20, mae60=mae60)
        second_result = self.build((first, second), mae20=mae20, mae60=tuple(reversed(mae60)))

        self.assertEqual(first_result, second_result)

    def test_split_input_order_changed_same_result(self):
        observation = self.observation()
        first = self.build(
            (observation,),
            mae20=(self.target(TARGET_MAE20, end_date=date(2026, 5, 29)),),
            mae60=(self.target(TARGET_MAE60, end_date=date(2026, 6, 15)),),
        )
        second = self.build(
            (observation,),
            mae20=(self.target(TARGET_MAE20, end_date=date(2026, 5, 29)),),
            mae60=(self.target(TARGET_MAE60, end_date=date(2026, 6, 15)),),
            spec=self.spec(splits=tuple(reversed(self.split_specs()))),
        )

        self.assertEqual(first, second)

    def test_same_inputs_same_dataset_id_and_checksum(self):
        observation = self.observation()
        first = self.build((observation,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60),))
        second = self.build((observation,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60),))

        self.assertEqual(first.dataset_id, second.dataset_id)
        self.assertEqual(first.dataset_checksum, second.dataset_checksum)

    def test_feature_checksum_changed_changes_dataset_checksum(self):
        observation = self.observation()
        changed = replace(observation, observation_checksum="obs_checksum_changed")

        first = self.build((observation,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60),))
        second = self.build((changed,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60),))

        self.assertNotEqual(first.dataset_checksum, second.dataset_checksum)

    def test_mae20_checksum_or_value_changed_changes_dataset_checksum(self):
        observation = self.observation()
        first = self.build((observation,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60),))
        second = self.build((observation,), mae20=(self.target(TARGET_MAE20, target_value=-0.07, checksum_suffix="changed"),), mae60=(self.target(TARGET_MAE60),))

        self.assertNotEqual(first.dataset_checksum, second.dataset_checksum)

    def test_mae60_target_end_date_changed_changes_dataset_checksum(self):
        observation = self.observation()
        first = self.build((observation,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60, end_date=date(2026, 6, 15)),))
        second = self.build((observation,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60, end_date=date(2026, 6, 16)),))

        self.assertNotEqual(first.dataset_checksum, second.dataset_checksum)

    def test_split_end_date_changed_changes_dataset_checksum(self):
        observation = self.observation()
        changed_splits = (
            TechnicalRiskOOSSplitSpec("development_2026_h1", TechnicalRiskOOSSplitRole.DEVELOPMENT, date(2026, 1, 1), date(2026, 6, 29)),
            self.split_specs()[1],
            self.split_specs()[2],
        )

        first = self.build((observation,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60),))
        second = self.build((observation,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60),), spec=self.spec(splits=changed_splits))

        self.assertNotEqual(first.dataset_checksum, second.dataset_checksum)

    def test_duplicate_conflicting_observation_deterministic_exclusion(self):
        observation = self.observation()
        duplicate = replace(observation, observation_checksum="obs_checksum_conflict", sma20=101.0)

        result = self.build((duplicate, observation), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60),))

        self.assertEqual(self.reason(result), TechnicalRiskOOSExclusionReason.EXCLUDED_DUPLICATE_OBSERVATION)

    def test_duplicate_conflicting_target_deterministic_exclusion(self):
        observation = self.observation()
        mae20_a = self.target(TARGET_MAE20, checksum_suffix="a")
        mae20_b = self.target(TARGET_MAE20, checksum_suffix="b", target_value=-0.08)

        result = self.build((observation,), mae20=(mae20_b, mae20_a), mae60=(self.target(TARGET_MAE60),))

        self.assertEqual(self.reason(result), TechnicalRiskOOSExclusionReason.EXCLUDED_DUPLICATE_TARGET)

    def test_row_does_not_materialize_derived_evidence_or_methodology(self):
        observation = self.observation()
        result = self.build((observation,), mae20=(self.target(TARGET_MAE20),), mae60=(self.target(TARGET_MAE60),))
        row = result.included_rows[0]

        self.assertIsInstance(row, AlignedTechnicalRiskOOSRow)
        forbidden = (
            "close_vs_sma20",
            "close_vs_sma60",
            "relative_sma_spread",
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
            "candidate",
            "threshold",
        )
        row_text = repr(row)
        for term in forbidden:
            self.assertNotIn(term, row_text)

    def test_upstream_feature_exclusion_accounting_preserved(self):
        upstream = HistoricalRiskFeatureExclusion(
            exclusion_id="historical_feature_exclusion_001",
            symbol="2330.TW",
            evaluation_date=date(2026, 4, 1),
            feature_set_id=TECHNICAL_RISK_V1_FEATURE_SET_ID,
            source_snapshot_id="frozen_snapshot_v1",
            source_snapshot_checksum="snapshot_checksum_001",
            calculation_id="feature_calc_001",
            reason=EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY,
            feature_id="TECH_SMA60_V1",
        )

        result = self.build((), upstream=(upstream,))

        self.assertEqual(len(result.excluded_records), 1)
        self.assertEqual(result.excluded_records[0].reason, TechnicalRiskOOSExclusionReason.UPSTREAM_FEATURE_EXCLUSION)
        self.assertEqual(result.excluded_records[0].upstream_reason, EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY)
        self.assertEqual(result.summary_counts["excluded_upstream_feature_exclusion"], 1)

    def test_invalid_split_date_order_fails_configuration(self):
        with self.assertRaisesRegex(TechnicalRiskOOSDatasetError, "start_date"):
            TechnicalRiskOOSSplitSpec("bad", TechnicalRiskOOSSplitRole.DEVELOPMENT, date(2026, 2, 1), date(2026, 1, 1))

    def test_duplicate_split_id_fails_configuration(self):
        splits = (
            TechnicalRiskOOSSplitSpec("same", TechnicalRiskOOSSplitRole.DEVELOPMENT, date(2026, 1, 1), date(2026, 1, 31)),
            TechnicalRiskOOSSplitSpec("same", TechnicalRiskOOSSplitRole.VALIDATION, date(2026, 2, 1), date(2026, 2, 28)),
        )

        with self.assertRaisesRegex(TechnicalRiskOOSDatasetError, "Duplicate split_id"):
            self.spec(splits=splits)

    def test_unsupported_feature_set_fails_configuration(self):
        with self.assertRaisesRegex(TechnicalRiskOOSDatasetError, "exact feature set"):
            self.spec(required_feature_ids=(*HISTORICAL_RISK_FEATURE_SET_V1, "TECH_VOLUME_RATIO_V1"))

    def test_unsupported_target_definition_fails_configuration(self):
        observation = self.observation()
        wrong = self.target("TARGET_RETURN_20D_REG_V1")

        with self.assertRaisesRegex(TechnicalRiskOOSDatasetError, "Unsupported target"):
            self.build((observation,), mae20=(wrong,), mae60=(self.target(TARGET_MAE60),))

    def test_invalid_target_contract_excluded_without_artifact_recalculation(self):
        observation = self.observation()
        invalid = replace(self.target(TARGET_MAE20), checksum=None)

        result = self.build((observation,), mae20=(invalid,), mae60=(self.target(TARGET_MAE60),))

        self.assertEqual(self.reason(result), TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_ALIGNMENT_MISMATCH)
        self.assertEqual(result.excluded_records[0].detail_code, "TARGET_CHECKSUM_MISSING")

    def test_target_window_lineage_is_first_class_source(self):
        observation = self.observation()
        mae20 = self.target(TARGET_MAE20, start_date=date(2026, 5, 5), end_date=date(2026, 5, 30))
        mae60 = self.target(TARGET_MAE60, start_date=date(2026, 5, 5), end_date=date(2026, 6, 29))

        row = self.build((observation,), mae20=(mae20,), mae60=(mae60,)).included_rows[0]

        self.assertEqual(row.mae20_target_start_date, mae20.window_lineage.target_start_date)
        self.assertEqual(row.mae20_target_end_date, mae20.window_lineage.target_end_date)
        self.assertEqual(row.mae60_target_start_date, mae60.window_lineage.target_start_date)
        self.assertEqual(row.mae60_target_end_date, mae60.window_lineage.target_end_date)

    def test_no_db_yfinance_policy_threshold_or_producer_boundary(self):
        source = (SRC_PATH / "risk_oos" / "aligned_dataset.py").read_text()

        forbidden = (
            "sqlite",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "scanner",
            "pdf",
            "open(",
            "read_text",
            "write_text",
            "TargetGenerationOutput",
            "TechnicalRiskSignalProducer",
            "RiskSeverity",
            "candidate policy",
            "threshold",
        )
        for term in forbidden:
            self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
