import inspect
import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskOOSSplitSpec
from risk_oos import TechnicalRiskTemporalSplitMethodologyError
from risk_oos import TechnicalRiskV1TemporalSplitMethodology
from risk_oos import build_technical_risk_v1_temporal_split_methodology
from risk_oos import build_technical_risk_v1_temporal_split_specs


class TechnicalRiskTemporalSplitMethodologyTestCase(unittest.TestCase):
    def methodology(self) -> TechnicalRiskV1TemporalSplitMethodology:
        return build_technical_risk_v1_temporal_split_methodology()

    def specs_by_role(self):
        return self.methodology().split_specs_by_role

    def test_methodology_version_is_exact(self):
        methodology = self.methodology()

        self.assertEqual(methodology.methodology_version, TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1)
        self.assertTrue(methodology.methodology_id.startswith("technical_risk_v1_temporal_split_"))
        self.assertEqual(len(methodology.methodology_checksum), 64)

    def test_development_dates_are_exact(self):
        split = self.specs_by_role()[TechnicalRiskOOSSplitRole.DEVELOPMENT]

        self.assertEqual(split.split_id, "technical_risk_v1_development_2018_2021")
        self.assertEqual(split.start_date, date(2018, 1, 1))
        self.assertEqual(split.end_date, date(2021, 12, 31))

    def test_validation_dates_are_exact(self):
        split = self.specs_by_role()[TechnicalRiskOOSSplitRole.VALIDATION]

        self.assertEqual(split.split_id, "technical_risk_v1_validation_2022_2023")
        self.assertEqual(split.start_date, date(2022, 1, 1))
        self.assertEqual(split.end_date, date(2023, 12, 31))

    def test_holdout_dates_are_exact(self):
        split = self.specs_by_role()[TechnicalRiskOOSSplitRole.HOLDOUT]

        self.assertEqual(split.split_id, "technical_risk_v1_holdout_2024_2025")
        self.assertEqual(split.start_date, date(2024, 1, 1))
        self.assertEqual(split.end_date, date(2025, 12, 31))

    def test_split_roles_are_exact_and_existing_specs_are_reused(self):
        specs = build_technical_risk_v1_temporal_split_specs()

        self.assertEqual(
            tuple(spec.split_role for spec in specs),
            (
                TechnicalRiskOOSSplitRole.DEVELOPMENT,
                TechnicalRiskOOSSplitRole.VALIDATION,
                TechnicalRiskOOSSplitRole.HOLDOUT,
            ),
        )
        self.assertTrue(all(isinstance(spec, TechnicalRiskOOSSplitSpec) for spec in specs))

    def test_methodology_is_immutable(self):
        methodology = self.methodology()

        with self.assertRaises(FrozenInstanceError):
            methodology.methodology_version = "changed"

    def test_methodology_identity_and_checksum_are_deterministic(self):
        first = self.methodology()
        second = self.methodology()

        self.assertEqual(first.split_specs, second.split_specs)
        self.assertEqual(first.methodology_id, second.methodology_id)
        self.assertEqual(first.methodology_checksum, second.methodology_checksum)

    def test_mismatched_identity_or_checksum_fails_closed(self):
        good = self.methodology()

        with self.assertRaisesRegex(TechnicalRiskTemporalSplitMethodologyError, "methodology_id"):
            TechnicalRiskV1TemporalSplitMethodology(
                methodology_id="wrong_id",
                methodology_version=TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1,
                split_specs=good.split_specs,
            )
        with self.assertRaisesRegex(TechnicalRiskTemporalSplitMethodologyError, "methodology_checksum"):
            TechnicalRiskV1TemporalSplitMethodology(
                methodology_id=None,
                methodology_version=TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1,
                split_specs=good.split_specs,
                methodology_checksum="wrong_checksum",
            )

    def test_split_periods_are_chronological_and_non_overlapping(self):
        specs = self.methodology().split_specs

        self.assertLess(specs[0].end_date, specs[1].start_date)
        self.assertLess(specs[1].end_date, specs[2].start_date)

    def test_existing_split_boundary_semantics_are_inclusive_dates(self):
        development = self.specs_by_role()[TechnicalRiskOOSSplitRole.DEVELOPMENT]

        self.assertLessEqual(development.start_date, date(2018, 1, 1))
        self.assertLessEqual(date(2021, 12, 31), development.end_date)

    def test_role_eligibility_rules_are_exact(self):
        methodology = self.methodology()

        self.assertEqual(methodology.threshold_axis_evidence_eligible_roles, (TechnicalRiskOOSSplitRole.DEVELOPMENT,))
        self.assertEqual(methodology.validation_selection_eligible_roles, (TechnicalRiskOOSSplitRole.VALIDATION,))
        self.assertEqual(methodology.holdout_confirmation_eligible_roles, (TechnicalRiskOOSSplitRole.HOLDOUT,))

    def test_threshold_axis_evidence_excludes_validation_and_holdout_roles(self):
        roles = self.methodology().threshold_axis_evidence_eligible_roles

        self.assertNotIn(TechnicalRiskOOSSplitRole.VALIDATION, roles)
        self.assertNotIn(TechnicalRiskOOSSplitRole.HOLDOUT, roles)

    def test_validation_selection_excludes_development_and_holdout_roles(self):
        roles = self.methodology().validation_selection_eligible_roles

        self.assertNotIn(TechnicalRiskOOSSplitRole.DEVELOPMENT, roles)
        self.assertNotIn(TechnicalRiskOOSSplitRole.HOLDOUT, roles)

    def test_holdout_confirmation_excludes_development_and_validation_roles(self):
        roles = self.methodology().holdout_confirmation_eligible_roles

        self.assertNotIn(TechnicalRiskOOSSplitRole.DEVELOPMENT, roles)
        self.assertNotIn(TechnicalRiskOOSSplitRole.VALIDATION, roles)

    def test_invalid_version_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskTemporalSplitMethodologyError, "methodology_version"):
            TechnicalRiskV1TemporalSplitMethodology(
                methodology_id=None,
                methodology_version="TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V2",
                split_specs=build_technical_risk_v1_temporal_split_specs(),
            )

    def test_alternate_dates_fail_closed(self):
        changed = (
            TechnicalRiskOOSSplitSpec(
                split_id="technical_risk_v1_development_2018_2022",
                split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT,
                start_date=date(2018, 1, 1),
                end_date=date(2022, 12, 31),
            ),
            *build_technical_risk_v1_temporal_split_specs()[1:],
        )

        with self.assertRaisesRegex(TechnicalRiskTemporalSplitMethodologyError, "do not match"):
            TechnicalRiskV1TemporalSplitMethodology(
                methodology_id=None,
                methodology_version=TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1,
                split_specs=changed,
            )

    def test_no_current_date_dependency(self):
        import risk_oos.temporal_split_methodology as methodology_module

        source = inspect.getsource(methodology_module)
        forbidden_tokens = ("today(", "now(")
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_no_research_db_dependency(self):
        import risk_oos.temporal_split_methodology as methodology_module

        source = inspect.getsource(methodology_module)
        forbidden_tokens = ("ResearchDataStore", "sqlite", "connect")
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_no_mae_candidate_or_outcome_dependency(self):
        import risk_oos.temporal_split_methodology as methodology_module

        source = inspect.getsource(methodology_module)
        forbidden_tokens = (
            "MAE",
            "Target",
            "TECH_POLICY_CANDIDATE_A",
            "TECH_POLICY_CANDIDATE_B",
            "TECH_POLICY_CANDIDATE_C",
            "TECH_POLICY_CANDIDATE_D",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_no_production_or_network_dependency(self):
        import risk_oos.temporal_split_methodology as methodology_module

        source = inspect.getsource(methodology_module)
        forbidden_tokens = ("production_runtime", "data/production", "Yahoo", "yfinance", "requests")
        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
