import inspect
import sys
import unittest
from dataclasses import fields
from dataclasses import replace
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import DEVELOPMENT_SHORTLIST_ARTIFACT_V1
from risk_oos import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos import TECH_RISK_CANDIDATE_SET_CONTRACT_V1
from risk_oos import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos import TECH_RISK_DEVELOPMENT_EVALUATION_CONTEXT_V1
from risk_oos import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos import TECH_RISK_QUANTILE_NEAREST_RANK_V1
from risk_oos import TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1
from risk_oos import TECH_RISK_VALIDATION_SELECTION_ARTIFACT_V1
from risk_oos import TECH_RISK_VALIDATION_SELECTION_CRITERIA_V1
from risk_oos import TECH_RISK_VALIDATION_SELECTION_INPUT_V1
from risk_oos import AlignedTechnicalRiskOOSRow
from risk_oos import DevelopmentEvaluationContext
from risk_oos import DevelopmentShortlistArtifact
from risk_oos import DevelopmentShortlistEligiblePair
from risk_oos import TechnicalRiskCandidateEvaluator
from risk_oos import TechnicalRiskCandidateFamily
from risk_oos import TechnicalRiskCandidateIdentity
from risk_oos import TechnicalRiskCandidateEvaluationInput
from risk_oos import TechnicalRiskCandidateSet
from risk_oos import TechnicalRiskCoveragePreference
from risk_oos import TechnicalRiskEmptyBucketPolicy
from risk_oos import TechnicalRiskMedianSeparationPreference
from risk_oos import TechnicalRiskMethodologyWarningPolicy
from risk_oos import TechnicalRiskMonotonicityPreference
from risk_oos import TechnicalRiskOOSDatasetResult
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskThresholdDimension
from risk_oos import TechnicalRiskThresholdDimensionId
from risk_oos import TechnicalRiskThresholdIdentity
from risk_oos import TechnicalRiskThresholdOperator
from risk_oos import TechnicalRiskThresholdSet
from risk_oos import TechnicalRiskTiePolicy
from risk_oos import TechnicalRiskValidationCombinationOutcome
from risk_oos import TechnicalRiskValidationConsideredCombination
from risk_oos import TechnicalRiskValidationSelectionArtifact
from risk_oos import TechnicalRiskValidationSelectionCriteria
from risk_oos import TechnicalRiskValidationSelectionDecision
from risk_oos import TechnicalRiskValidationSelectionError
from risk_oos import TechnicalRiskValidationSelectionInput
from risk_oos import TechnicalRiskValidationSelectionReasonCode
from risk_oos import TechnicalRiskValidationSelectionStatus
from risk_oos import ThresholdCandidateGenerationContract
from risk_oos import technical_risk_candidate_a_spec
from risk_oos import technical_risk_candidate_b_spec


class TechnicalRiskValidationSelectionContractTestCase(unittest.TestCase):

    def row(self, row_id="row_001", split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT, **overrides):
        values = {
            "row_id": row_id,
            "observation_id": f"obs_{row_id}",
            "symbol": "2330.TW",
            "evaluation_date": date(2026, 5, 1),
            "as_of_close": 80.0,
            "sma20": 90.0,
            "sma60": 100.0,
            "rsi14": 35.0,
            "feature_observation_checksum": f"obs_checksum_{row_id}",
            "mae20_value": -0.08,
            "mae20_target_checksum": f"mae20_checksum_{row_id}",
            "mae20_calculation_id": f"mae20_calc_{row_id}",
            "mae20_target_start_date": date(2026, 5, 2),
            "mae20_target_end_date": date(2026, 5, 29),
            "mae60_value": -0.12,
            "mae60_target_checksum": f"mae60_checksum_{row_id}",
            "mae60_calculation_id": f"mae60_calc_{row_id}",
            "mae60_target_start_date": date(2026, 5, 2),
            "mae60_target_end_date": date(2026, 7, 30),
            "split_id": f"{split_role.value.lower()}_split",
            "split_role": split_role,
            "dataset_spec_id": "technical_risk_oos_dataset_v1",
            "dataset_spec_version": "v1",
        }
        values.update(overrides)
        return AlignedTechnicalRiskOOSRow(**values)

    def dataset(self, rows, dataset_checksum="dataset_checksum_001"):
        return TechnicalRiskOOSDatasetResult(
            included_rows=tuple(rows),
            excluded_records=(),
            dataset_id="technical_risk_oos_dataset_001",
            dataset_checksum=dataset_checksum,
            summary_counts={"included_rows": len(rows)},
        )

    def threshold_dimension(self, dimension_id, value):
        return TechnicalRiskThresholdDimension(
            dimension_id=dimension_id,
            operator=TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            canonical_value=value,
        )

    def threshold_set(self, threshold_set_id="threshold_set_001", close_vs_sma20="-0.05", **overrides):
        values = {
            "threshold_set_id": threshold_set_id,
            "threshold_set_version": "v1",
            "numeric_representation_version": TECH_RISK_NUMERIC_REPRESENTATION_V1,
            "dimensions": (
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, close_vs_sma20),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.05"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.05"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40"),
            ),
            "compatible_candidate_families": tuple(TechnicalRiskCandidateFamily),
        }
        values.update(overrides)
        return TechnicalRiskThresholdSet(**values)

    def threshold_generation(self, thresholds=None, **overrides):
        if thresholds is None:
            thresholds = (
                TechnicalRiskThresholdIdentity.from_threshold_set(self.threshold_set("threshold_set_001")),
                TechnicalRiskThresholdIdentity.from_threshold_set(self.threshold_set("threshold_set_002", close_vs_sma20="-0.06")),
            )
        values = {
            "generation_id": None,
            "generation_version": TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1,
            "generation_method_id": "TECH_RISK_FIXED_GRID_CANDIDATES",
            "generation_method_version": "v1",
            "numeric_representation_version": TECH_RISK_NUMERIC_REPRESENTATION_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
            "candidate_family": TechnicalRiskCandidateFamily.MEDIUM_TERM_TREND_CENTRIC,
            "source_spec_version": "technical_risk_rule_candidate_generation_spec_v1",
            "generated_threshold_set_ids": tuple(threshold.threshold_set_id for threshold in thresholds),
            "generated_threshold_set_checksums": tuple(threshold.threshold_set_checksum for threshold in thresholds),
        }
        values.update(overrides)
        return ThresholdCandidateGenerationContract(**values)

    def candidate_identities(self):
        return (
            TechnicalRiskCandidateIdentity.from_candidate_spec(technical_risk_candidate_a_spec()),
            TechnicalRiskCandidateIdentity.from_candidate_spec(technical_risk_candidate_b_spec()),
        )

    def candidate_set(self, generation=None, candidates=None, **overrides):
        generation = self.threshold_generation() if generation is None else generation
        candidates = self.candidate_identities() if candidates is None else candidates
        values = {
            "candidate_set_id": None,
            "candidate_set_version": TECH_RISK_CANDIDATE_SET_CONTRACT_V1,
            "dataset_checksum": "dataset_checksum_001",
            "generation_id": generation.generation_id,
            "candidate_ids": tuple(candidate.candidate_id for candidate in candidates),
            "candidate_structural_checksums": tuple(candidate.candidate_structural_checksum for candidate in candidates),
        }
        values.update(overrides)
        return TechnicalRiskCandidateSet(**values)

    def development_context(self, candidate_set=None, generation=None, **overrides):
        generation = self.threshold_generation() if generation is None else generation
        candidate_set = self.candidate_set(generation=generation) if candidate_set is None else candidate_set
        values = {
            "development_experiment_id": None,
            "dataset_id": "technical_risk_oos_dataset_001",
            "dataset_checksum": "dataset_checksum_001",
            "split_role": TechnicalRiskOOSSplitRole.DEVELOPMENT,
            "candidate_set_id": candidate_set.candidate_set_id,
            "threshold_candidate_set_id": generation.generation_id,
            "exploration_version": TECH_RISK_DEVELOPMENT_EVALUATION_CONTEXT_V1,
            "evaluator_version": TECH_RISK_CANDIDATE_EVALUATOR_V1,
            "metric_version": TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
        }
        values.update(overrides)
        return DevelopmentEvaluationContext(**values)

    def evaluation_input(self, dataset, candidate, threshold_set, roles=(TechnicalRiskOOSSplitRole.DEVELOPMENT,), **overrides):
        values = {
            "evaluation_input_version": "TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1",
            "dataset_id": dataset.dataset_id,
            "dataset_checksum": dataset.dataset_checksum,
            "candidate_id": candidate.policy_candidate_id,
            "candidate_version": candidate.candidate_version,
            "candidate_structural_checksum": candidate.candidate_structural_checksum,
            "threshold_set_id": threshold_set.threshold_set_id,
            "threshold_set_version": threshold_set.threshold_set_version,
            "threshold_set_checksum": threshold_set.threshold_set_checksum,
            "derived_evidence_version": TECH_RISK_DERIVED_EVIDENCE_V1,
            "evaluator_version": TECH_RISK_CANDIDATE_EVALUATOR_V1,
            "metric_version": TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
            "quantile_version": TECH_RISK_QUANTILE_NEAREST_RANK_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
            "allowed_split_roles": roles,
        }
        values.update(overrides)
        return TechnicalRiskCandidateEvaluationInput(**values)

    def evaluate(self, candidate=None, threshold_set=None, split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT, **overrides):
        candidate = technical_risk_candidate_a_spec() if candidate is None else candidate
        threshold_set = self.threshold_set() if threshold_set is None else threshold_set
        dataset = self.dataset((self.row(split_role=split_role),))
        return TechnicalRiskCandidateEvaluator().evaluate(
            dataset,
            candidate,
            threshold_set,
            self.evaluation_input(dataset, candidate, threshold_set, roles=(split_role,), **overrides),
        )

    def validation_evaluation(self, candidate=None, threshold_set=None, dataset=None, roles=(TechnicalRiskOOSSplitRole.VALIDATION,), **overrides):
        candidate = technical_risk_candidate_a_spec() if candidate is None else candidate
        threshold_set = self.threshold_set() if threshold_set is None else threshold_set
        dataset = self.validation_dataset() if dataset is None else dataset
        return TechnicalRiskCandidateEvaluator().evaluate(
            dataset,
            candidate,
            threshold_set,
            self.evaluation_input(dataset, candidate, threshold_set, roles=roles, **overrides),
        )

    def validation_dataset(self, dataset_checksum="validation_dataset_checksum_001"):
        return self.dataset((self.row(row_id="validation_row_001", split_role=TechnicalRiskOOSSplitRole.VALIDATION),), dataset_checksum)

    def shortlist(self, candidates=None, thresholds=None, evaluations=None, **overrides):
        generation = self.threshold_generation()
        candidate_set = self.candidate_set(generation=generation)
        context = self.development_context(candidate_set=candidate_set, generation=generation)
        thresholds = (
            TechnicalRiskThresholdIdentity(threshold_id, "v1", threshold_checksum)
            for threshold_id, threshold_checksum in zip(
                generation.generated_threshold_set_ids,
                generation.generated_threshold_set_checksums,
            )
        ) if thresholds is None else thresholds
        threshold_tuple = tuple(thresholds)
        candidates = self.candidate_identities() if candidates is None else candidates
        if evaluations is None:
            evaluations = (
                self.evaluate(candidate=technical_risk_candidate_a_spec(), threshold_set=self.threshold_set("threshold_set_001")),
                self.evaluate(candidate=technical_risk_candidate_b_spec(), threshold_set=self.threshold_set("threshold_set_002", close_vs_sma20="-0.06")),
            )
        return DevelopmentShortlistArtifact.from_development_contracts(
            development_context=context,
            candidate_set=candidate_set,
            threshold_generation=generation,
            eligible_candidates=tuple(candidates),
            eligible_threshold_sets=threshold_tuple,
            development_evaluation_results=tuple(evaluations),
            **overrides,
        )

    def criteria(self, **overrides):
        values = {
            "criteria_id": None,
            "criteria_version": TECH_RISK_VALIDATION_SELECTION_CRITERIA_V1,
            "monotonicity_preference": TechnicalRiskMonotonicityPreference.PREFER_PASS,
            "median_separation_preference": TechnicalRiskMedianSeparationPreference.COMPARE_MAE20_AND_MAE60_MEDIANS,
            "coverage_preference": TechnicalRiskCoveragePreference.PREFER_EVALUABLE_LOW_MEDIUM_HIGH_COVERAGE,
            "empty_bucket_policy": TechnicalRiskEmptyBucketPolicy.FLAG_METHOD_WARNING,
            "methodology_warning_policy": TechnicalRiskMethodologyWarningPolicy.RETAIN_STRUCTURED_WARNINGS,
            "tie_policy": TechnicalRiskTiePolicy.TIE_REQUIRES_METHOD_DECISION,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
            "metric_version": TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
            "quantile_version": TECH_RISK_QUANTILE_NEAREST_RANK_V1,
        }
        values.update(overrides)
        return TechnicalRiskValidationSelectionCriteria(**values)

    def validation_evaluations(self, dataset=None):
        dataset = self.validation_dataset() if dataset is None else dataset
        return (
            self.validation_evaluation(candidate=technical_risk_candidate_a_spec(), threshold_set=self.threshold_set("threshold_set_001"), dataset=dataset),
            self.validation_evaluation(
                candidate=technical_risk_candidate_b_spec(),
                threshold_set=self.threshold_set("threshold_set_002", close_vs_sma20="-0.06"),
                dataset=dataset,
            ),
        )

    def selection_input(self, dataset, shortlist, criteria, evaluations, **overrides):
        values = {
            "selection_input_version": TECH_RISK_VALIDATION_SELECTION_INPUT_V1,
            "validation_dataset_id": dataset.dataset_id,
            "validation_dataset_checksum": dataset.dataset_checksum,
            "development_shortlist_id": shortlist.shortlist_id,
            "development_shortlist_checksum": shortlist.shortlist_checksum,
            "selection_criteria_id": criteria.criteria_id,
            "selection_criteria_version": criteria.criteria_version,
            "selection_criteria_checksum": criteria.criteria_checksum,
            "validation_evaluation_ids": tuple(evaluation.evaluation_id for evaluation in evaluations),
            "validation_evaluation_checksums": tuple(evaluation.evaluation_checksum for evaluation in evaluations),
            "evaluator_version": TECH_RISK_CANDIDATE_EVALUATOR_V1,
            "metric_version": TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
            "quantile_version": TECH_RISK_QUANTILE_NEAREST_RANK_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
        }
        values.update(overrides)
        return TechnicalRiskValidationSelectionInput(**values)

    def considered(self, evaluations, outcomes=None, reason_codes=None):
        if outcomes is None:
            outcomes = (
                TechnicalRiskValidationCombinationOutcome.SELECTED,
                TechnicalRiskValidationCombinationOutcome.NOT_SELECTED,
            )
        if reason_codes is None:
            reason_codes = (
                (TechnicalRiskValidationSelectionReasonCode.SELECTED_METHOD_REVIEW,),
                (TechnicalRiskValidationSelectionReasonCode.NOT_SELECTED_METHOD_PREFERENCE,),
            )
        return tuple(
            TechnicalRiskValidationConsideredCombination.from_evaluation(
                evaluation=evaluation,
                selection_outcome=outcome,
                structured_reason_codes=reasons,
            )
            for evaluation, outcome, reasons in zip(evaluations, outcomes, reason_codes)
        )

    def decision(self, selected_evaluation=None, status=TechnicalRiskValidationSelectionStatus.SELECTED, **overrides):
        if status == TechnicalRiskValidationSelectionStatus.SELECTED:
            selected_evaluation = self.validation_evaluations()[0] if selected_evaluation is None else selected_evaluation
            values = {
                "selection_status": status,
                "selected_candidate_id": selected_evaluation.candidate_id,
                "selected_candidate_structural_checksum": selected_evaluation.candidate_structural_checksum,
                "selected_threshold_set_id": selected_evaluation.threshold_set_id,
                "selected_threshold_set_checksum": selected_evaluation.threshold_set_checksum,
                "accepted_validation_evaluation_id": selected_evaluation.evaluation_id,
                "accepted_validation_evaluation_checksum": selected_evaluation.evaluation_checksum,
                "structured_selection_reason_codes": (TechnicalRiskValidationSelectionReasonCode.SELECTED_METHOD_REVIEW,),
            }
        elif status == TechnicalRiskValidationSelectionStatus.NO_VALID_SELECTION:
            values = {
                "selection_status": status,
                "structured_selection_reason_codes": (TechnicalRiskValidationSelectionReasonCode.NO_VALID_SELECTION_EVIDENCE,),
            }
        else:
            values = {
                "selection_status": status,
                "structured_selection_reason_codes": (TechnicalRiskValidationSelectionReasonCode.TIE_REQUIRES_METHOD_DECISION,),
            }
        values.update(overrides)
        return TechnicalRiskValidationSelectionDecision(**values)

    def selection_artifact(self, dataset=None, shortlist=None, criteria=None, evaluations=None, decision=None, considered=None, **overrides):
        dataset = self.validation_dataset() if dataset is None else dataset
        shortlist = self.shortlist() if shortlist is None else shortlist
        criteria = self.criteria() if criteria is None else criteria
        evaluations = self.validation_evaluations(dataset) if evaluations is None else evaluations
        decision = self.decision(selected_evaluation=evaluations[0]) if decision is None else decision
        considered = self.considered(evaluations) if considered is None else considered
        return TechnicalRiskValidationSelectionArtifact.from_validation_contracts(
            validation_dataset=dataset,
            development_shortlist=shortlist,
            selection_criteria=criteria,
            selection_input=self.selection_input(dataset, shortlist, criteria, evaluations),
            validation_evaluations=tuple(evaluations),
            selection_decision=decision,
            considered_combinations=tuple(considered),
            **overrides,
        )

    def test_valid_development_shortlist(self):
        shortlist = self.shortlist()

        self.assertEqual(shortlist.shortlist_version, DEVELOPMENT_SHORTLIST_ARTIFACT_V1)
        self.assertTrue(shortlist.shortlist_id.startswith("technical_risk_development_shortlist_"))
        self.assertEqual(len(shortlist.eligible_pairs), 2)
        self.assertEqual(len(shortlist.eligible_candidates), 2)
        self.assertEqual(len(shortlist.eligible_threshold_sets), 2)
        self.assertEqual(len(shortlist.development_evaluations), 2)
        self.assertEqual(
            tuple((pair.candidate_id, pair.threshold_set_id) for pair in shortlist.eligible_pairs),
            (("TECH_POLICY_CANDIDATE_A", "threshold_set_001"), ("TECH_POLICY_CANDIDATE_B", "threshold_set_002")),
        )

    def test_same_semantic_shortlist_same_id_and_checksum(self):
        first = self.shortlist()
        second = self.shortlist()

        self.assertEqual(first.shortlist_id, second.shortlist_id)
        self.assertEqual(first.shortlist_checksum, second.shortlist_checksum)

    def test_candidate_threshold_and_evaluation_reorder_do_not_change_shortlist(self):
        first = self.shortlist()
        second = DevelopmentShortlistArtifact(
            shortlist_id=None,
            shortlist_version=first.shortlist_version,
            development_experiment_id=first.development_experiment_id,
            development_experiment_checksum=first.development_experiment_checksum,
            candidate_set_id=first.candidate_set_id,
            candidate_set_checksum=first.candidate_set_checksum,
            threshold_candidate_generation_id=first.threshold_candidate_generation_id,
            threshold_candidate_generation_checksum=first.threshold_candidate_generation_checksum,
            eligible_pairs=tuple(reversed(first.eligible_pairs)),
            eligible_candidates=tuple(reversed(first.eligible_candidates)),
            eligible_threshold_sets=tuple(reversed(first.eligible_threshold_sets)),
            development_evaluations=tuple(reversed(first.development_evaluations)),
        )

        self.assertEqual(first.shortlist_id, second.shortlist_id)
        self.assertEqual(first.shortlist_checksum, second.shortlist_checksum)

    def test_orphan_candidate_or_threshold_summary_rejected(self):
        base = self.shortlist()
        extra = TechnicalRiskCandidateIdentity("TECH_POLICY_CANDIDATE_EXTRA", "v1", "extra_candidate_checksum")
        generation = self.threshold_generation()
        candidate_set = self.candidate_set(generation=generation, candidates=(*self.candidate_identities(), extra))
        context = self.development_context(candidate_set=candidate_set, generation=generation)
        changed_candidate = TechnicalRiskCandidateIdentity(
            self.candidate_identities()[0].candidate_id,
            "v1",
            "changed_candidate_checksum",
        )

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "projection"):
            DevelopmentShortlistArtifact.from_development_contracts(
                development_context=context,
                candidate_set=candidate_set,
                threshold_generation=generation,
                eligible_candidates=(*self.candidate_identities(), extra),
                eligible_threshold_sets=base.eligible_threshold_sets,
                development_evaluation_results=(
                    self.evaluate(candidate=technical_risk_candidate_a_spec(), threshold_set=self.threshold_set("threshold_set_001")),
                ),
            )
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "projection"):
            self.shortlist(
                candidates=self.candidate_identities(),
                thresholds=base.eligible_threshold_sets,
                evaluations=(self.evaluate(candidate=technical_risk_candidate_a_spec(), threshold_set=self.threshold_set("threshold_set_001")),),
            )
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "outside candidate set"):
            self.shortlist(candidates=(changed_candidate, self.candidate_identities()[1]))

    def test_pair_added_removed_and_evidence_changed_changes_shortlist_checksum(self):
        base = self.shortlist()
        removed = self.shortlist(
            candidates=(self.candidate_identities()[0],),
            thresholds=(base.eligible_threshold_sets[0],),
            evaluations=(self.evaluate(candidate=technical_risk_candidate_a_spec(), threshold_set=self.threshold_set("threshold_set_001")),),
        )
        cross_threshold = self.threshold_set("threshold_set_002", close_vs_sma20="-0.06")
        added_cross_pair = self.shortlist(
            evaluations=(
                self.evaluate(candidate=technical_risk_candidate_a_spec(), threshold_set=self.threshold_set("threshold_set_001")),
                self.evaluate(candidate=technical_risk_candidate_b_spec(), threshold_set=cross_threshold),
                self.evaluate(candidate=technical_risk_candidate_a_spec(), threshold_set=cross_threshold),
            )
        )
        changed_evaluation = replace(
            self.evaluate(candidate=technical_risk_candidate_a_spec(), threshold_set=self.threshold_set("threshold_set_001")),
            evaluation_checksum="changed_evaluation_checksum",
        )
        changed_eval_shortlist = self.shortlist(
            candidates=(self.candidate_identities()[0],),
            thresholds=(base.eligible_threshold_sets[0],),
            evaluations=(changed_evaluation,),
        )

        self.assertNotEqual(base.shortlist_checksum, removed.shortlist_checksum)
        self.assertNotEqual(base.shortlist_checksum, added_cross_pair.shortlist_checksum)
        self.assertNotEqual(base.shortlist_checksum, changed_eval_shortlist.shortlist_checksum)

    def test_threshold_checksum_changed_rejected(self):
        base = self.shortlist()
        changed_threshold = TechnicalRiskThresholdIdentity(
            base.eligible_threshold_sets[0].threshold_set_id,
            "v1",
            "changed_threshold_checksum",
        )

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "outside threshold generation"):
            self.shortlist(thresholds=(changed_threshold, base.eligible_threshold_sets[1]))

    def test_invalid_development_evaluation_lineage_rejected(self):
        validation_evaluation = self.evaluate(split_role=TechnicalRiskOOSSplitRole.VALIDATION)
        holdout_evaluation = self.evaluate(split_role=TechnicalRiskOOSSplitRole.HOLDOUT)
        dataset_mismatch = replace(self.evaluate(), dataset_checksum="changed_dataset_checksum")
        numeric_mismatch = replace(self.evaluate(), numeric_context_version="OTHER_CONTEXT")

        for evaluation in (validation_evaluation, holdout_evaluation):
            with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "DEVELOPMENT only"):
                self.shortlist(evaluations=(evaluation,))
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "dataset_checksum"):
            self.shortlist(evaluations=(dataset_mismatch,))
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "numeric_context_version"):
            self.shortlist(evaluations=(numeric_mismatch,))

    def test_evaluation_candidate_and_threshold_mismatch_rejected(self):
        candidate_mismatch = replace(self.evaluate(), candidate_structural_checksum="changed_candidate_checksum")
        threshold_mismatch = replace(self.evaluate(), threshold_set_checksum="changed_threshold_checksum")

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "candidate"):
            self.shortlist(evaluations=(candidate_mismatch,))
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "threshold"):
            self.shortlist(evaluations=(threshold_mismatch,))

    def test_pair_checksum_mismatch_and_duplicate_conflicting_pair_rejected(self):
        base = self.shortlist()
        changed_pair_candidate = replace(
            base.eligible_pairs[0],
            candidate_structural_checksum="changed_candidate_checksum",
        )
        changed_pair_threshold = replace(
            base.eligible_pairs[0],
            threshold_set_checksum="changed_threshold_checksum",
        )
        duplicate_conflicting_pair = replace(
            base.eligible_pairs[0],
            development_evaluation_id="other_development_evaluation",
            development_evaluation_checksum="other_development_evaluation_checksum",
        )

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "candidate"):
            DevelopmentShortlistArtifact(
                shortlist_id=None,
                shortlist_version=base.shortlist_version,
                development_experiment_id=base.development_experiment_id,
                development_experiment_checksum=base.development_experiment_checksum,
                candidate_set_id=base.candidate_set_id,
                candidate_set_checksum=base.candidate_set_checksum,
                threshold_candidate_generation_id=base.threshold_candidate_generation_id,
                threshold_candidate_generation_checksum=base.threshold_candidate_generation_checksum,
                eligible_pairs=(changed_pair_candidate, *base.eligible_pairs[1:]),
                eligible_candidates=base.eligible_candidates,
                eligible_threshold_sets=base.eligible_threshold_sets,
                development_evaluations=base.development_evaluations,
            )
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "threshold"):
            DevelopmentShortlistArtifact(
                shortlist_id=None,
                shortlist_version=base.shortlist_version,
                development_experiment_id=base.development_experiment_id,
                development_experiment_checksum=base.development_experiment_checksum,
                candidate_set_id=base.candidate_set_id,
                candidate_set_checksum=base.candidate_set_checksum,
                threshold_candidate_generation_id=base.threshold_candidate_generation_id,
                threshold_candidate_generation_checksum=base.threshold_candidate_generation_checksum,
                eligible_pairs=(changed_pair_threshold, *base.eligible_pairs[1:]),
                eligible_candidates=base.eligible_candidates,
                eligible_threshold_sets=base.eligible_threshold_sets,
                development_evaluations=base.development_evaluations,
            )
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "Duplicate eligible"):
            DevelopmentShortlistArtifact(
                shortlist_id=None,
                shortlist_version=base.shortlist_version,
                development_experiment_id=base.development_experiment_id,
                development_experiment_checksum=base.development_experiment_checksum,
                candidate_set_id=base.candidate_set_id,
                candidate_set_checksum=base.candidate_set_checksum,
                threshold_candidate_generation_id=base.threshold_candidate_generation_id,
                threshold_candidate_generation_checksum=base.threshold_candidate_generation_checksum,
                eligible_pairs=(base.eligible_pairs[0], duplicate_conflicting_pair, base.eligible_pairs[1]),
                eligible_candidates=base.eligible_candidates,
                eligible_threshold_sets=base.eligible_threshold_sets,
                development_evaluations=base.development_evaluations,
            )

    def test_candidate_threshold_summaries_are_pair_projections(self):
        shortlist = self.shortlist()

        self.assertEqual(
            shortlist.eligible_candidates,
            tuple(
                TechnicalRiskCandidateIdentity(pair.candidate_id, pair.candidate_version, pair.candidate_structural_checksum)
                for pair in shortlist.eligible_pairs
            ),
        )
        self.assertEqual(
            shortlist.eligible_threshold_sets,
            tuple(
                TechnicalRiskThresholdIdentity(pair.threshold_set_id, pair.threshold_set_version, pair.threshold_set_checksum)
                for pair in shortlist.eligible_pairs
            ),
        )

    def test_timestamps_do_not_change_shortlist_checksum(self):
        first = self.shortlist(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), approved_by="Alice")
        second = self.shortlist(created_at=datetime(2026, 2, 1, tzinfo=timezone.utc), approved_by="Bob")

        self.assertEqual(first.shortlist_id, second.shortlist_id)
        self.assertEqual(first.shortlist_checksum, second.shortlist_checksum)

    def test_valid_selection_criteria_and_determinism(self):
        first = self.criteria()
        second = self.criteria()

        self.assertEqual(first.criteria_version, TECH_RISK_VALIDATION_SELECTION_CRITERIA_V1)
        self.assertEqual(first.criteria_id, second.criteria_id)
        self.assertEqual(first.criteria_checksum, second.criteria_checksum)
        self.assertEqual(first.tie_policy, TechnicalRiskTiePolicy.TIE_REQUIRES_METHOD_DECISION)

    def test_criteria_field_change_changes_checksum(self):
        first = self.criteria()
        second = self.criteria(monotonicity_preference=TechnicalRiskMonotonicityPreference.REQUIRE_EVALUABLE)

        self.assertNotEqual(first.criteria_id, second.criteria_id)
        self.assertNotEqual(first.criteria_checksum, second.criteria_checksum)

    def test_criteria_audit_metadata_does_not_change_checksum(self):
        first = self.criteria(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), approved_by="Alice", human_note="first")
        second = self.criteria(created_at=datetime(2026, 2, 1, tzinfo=timezone.utc), approved_by="Bob", human_note="second")

        self.assertEqual(first.criteria_id, second.criteria_id)
        self.assertEqual(first.criteria_checksum, second.criteria_checksum)

    def test_valid_selected_validation_selection_artifact(self):
        artifact = self.selection_artifact()

        self.assertEqual(artifact.selection_version, TECH_RISK_VALIDATION_SELECTION_ARTIFACT_V1)
        self.assertEqual(artifact.selection_status, TechnicalRiskValidationSelectionStatus.SELECTED)
        self.assertTrue(artifact.selection_id.startswith("technical_risk_validation_selection_"))
        self.assertEqual(len(artifact.considered_combinations), 2)
        self.assertEqual(
            tuple(combination.selection_outcome for combination in artifact.considered_combinations),
            (
                TechnicalRiskValidationCombinationOutcome.SELECTED,
                TechnicalRiskValidationCombinationOutcome.NOT_SELECTED,
            ),
        )

    def test_selected_requires_exactly_one_selected_combination(self):
        evaluations = self.validation_evaluations()
        selected_decision = self.decision(selected_evaluation=evaluations[0])
        two_selected = self.considered(
            evaluations,
            outcomes=(TechnicalRiskValidationCombinationOutcome.SELECTED, TechnicalRiskValidationCombinationOutcome.SELECTED),
            reason_codes=(
                (TechnicalRiskValidationSelectionReasonCode.SELECTED_METHOD_REVIEW,),
                (TechnicalRiskValidationSelectionReasonCode.SELECTED_METHOD_REVIEW,),
            ),
        )

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "exactly one selected"):
            self.selection_artifact(evaluations=evaluations, decision=selected_decision, considered=two_selected)

    def test_selected_pair_and_evaluation_must_match_considered_combination(self):
        evaluations = self.validation_evaluations()
        mismatch_decision = self.decision(
            selected_evaluation=evaluations[0],
            accepted_validation_evaluation_checksum="changed_validation_checksum",
        )

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "Selected fields"):
            self.selection_artifact(evaluations=evaluations, decision=mismatch_decision)

    def test_validation_universe_requires_exact_shortlist_coverage(self):
        evaluations = self.validation_evaluations()
        extra = self.validation_evaluation(
            candidate=technical_risk_candidate_a_spec(),
            threshold_set=self.threshold_set("threshold_set_002", close_vs_sma20="-0.06"),
        )
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "coverage"):
            self.selection_artifact(evaluations=(evaluations[0],))
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "outside Development shortlist"):
            self.selection_artifact(evaluations=(*evaluations, extra))

    def test_duplicate_validation_evaluation_same_pair_rejected(self):
        evaluations = self.validation_evaluations()
        duplicate = replace(evaluations[0], evaluation_id="other_validation_evaluation")

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "Duplicate Validation evaluation pair"):
            self.selection_artifact(evaluations=(evaluations[0], duplicate, evaluations[1]))

    def test_validation_split_must_be_validation_only(self):
        evaluation = self.validation_evaluations()[0]
        development = replace(evaluation, evaluated_split_roles=(TechnicalRiskOOSSplitRole.DEVELOPMENT,))
        holdout = replace(evaluation, evaluated_split_roles=(TechnicalRiskOOSSplitRole.HOLDOUT,))
        validation_holdout = replace(evaluation, evaluated_split_roles=(TechnicalRiskOOSSplitRole.VALIDATION, TechnicalRiskOOSSplitRole.HOLDOUT))

        for evaluation in (development, holdout, validation_holdout):
            with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "VALIDATION only"):
                self.selection_artifact(evaluations=(evaluation,))

    def test_validation_dataset_candidate_threshold_and_version_integrity(self):
        evaluations = self.validation_evaluations()
        cases = (
            (replace(evaluations[0], dataset_checksum="changed_dataset_checksum"), "dataset_checksum"),
            (replace(evaluations[0], candidate_structural_checksum="changed_candidate_checksum"), "outside Development shortlist"),
            (replace(evaluations[0], threshold_set_checksum="changed_threshold_checksum"), "outside Development shortlist"),
            (replace(evaluations[0], evaluator_version="OTHER_EVALUATOR"), "evaluator_version"),
            (replace(evaluations[0], metric_version="OTHER_METRIC"), "metric_version"),
            (replace(evaluations[0], quantile_version="OTHER_QUANTILE"), "quantile_version"),
            (replace(evaluations[0], numeric_context_version="OTHER_CONTEXT"), "numeric_context_version"),
        )

        for bad_evaluation, message in cases:
            with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, message):
                self.selection_artifact(evaluations=(bad_evaluation, evaluations[1]))

    def test_no_valid_selection_semantics(self):
        evaluations = self.validation_evaluations()
        artifact = self.selection_artifact(
            evaluations=evaluations,
            decision=self.decision(status=TechnicalRiskValidationSelectionStatus.NO_VALID_SELECTION),
            considered=self.considered(
                evaluations,
                outcomes=(TechnicalRiskValidationCombinationOutcome.NOT_SELECTED, TechnicalRiskValidationCombinationOutcome.NOT_SELECTED),
                reason_codes=(
                    (TechnicalRiskValidationSelectionReasonCode.NO_VALID_SELECTION_EVIDENCE,),
                    (TechnicalRiskValidationSelectionReasonCode.NO_VALID_SELECTION_EVIDENCE,),
                ),
            ),
        )

        self.assertEqual(artifact.selection_status, TechnicalRiskValidationSelectionStatus.NO_VALID_SELECTION)
        self.assertIsNone(artifact.selected_candidate_id)
        self.assertTrue(all(item.selection_outcome == TechnicalRiskValidationCombinationOutcome.NOT_SELECTED for item in artifact.considered_combinations))

    def test_no_valid_selection_cannot_have_selected_pair(self):
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "cannot include selected"):
            self.decision(
                status=TechnicalRiskValidationSelectionStatus.NO_VALID_SELECTION,
                selected_candidate_id="TECH_POLICY_CANDIDATE_A",
            )

    def test_tie_requires_at_least_two_unresolved_combinations_and_no_selected_pair(self):
        evaluations = self.validation_evaluations()
        tie_artifact = self.selection_artifact(
            evaluations=evaluations,
            decision=self.decision(status=TechnicalRiskValidationSelectionStatus.TIE_REQUIRES_METHOD_DECISION),
            considered=self.considered(
                evaluations,
                outcomes=(TechnicalRiskValidationCombinationOutcome.UNRESOLVED_TIE, TechnicalRiskValidationCombinationOutcome.UNRESOLVED_TIE),
                reason_codes=(
                    (TechnicalRiskValidationSelectionReasonCode.TIE_REQUIRES_METHOD_DECISION,),
                    (TechnicalRiskValidationSelectionReasonCode.TIE_REQUIRES_METHOD_DECISION,),
                ),
            ),
        )

        self.assertEqual(tie_artifact.selection_status, TechnicalRiskValidationSelectionStatus.TIE_REQUIRES_METHOD_DECISION)
        self.assertIsNone(tie_artifact.selected_candidate_id)
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "at least two"):
            self.selection_artifact(
                evaluations=evaluations,
                decision=self.decision(status=TechnicalRiskValidationSelectionStatus.TIE_REQUIRES_METHOD_DECISION),
                considered=self.considered(
                    evaluations,
                    outcomes=(TechnicalRiskValidationCombinationOutcome.UNRESOLVED_TIE, TechnicalRiskValidationCombinationOutcome.NOT_SELECTED),
                    reason_codes=(
                        (TechnicalRiskValidationSelectionReasonCode.TIE_REQUIRES_METHOD_DECISION,),
                        (TechnicalRiskValidationSelectionReasonCode.NOT_SELECTED_METHOD_PREFERENCE,),
                    ),
                ),
            )

    def test_considered_combinations_retain_every_validation_evaluation(self):
        evaluations = self.validation_evaluations()
        omitted = (self.considered(evaluations)[0],)
        changed = (
            replace(self.considered(evaluations)[0], validation_evaluation_checksum="changed_checksum"),
            self.considered(evaluations)[1],
        )

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "retain every Validation evaluation"):
            self.selection_artifact(evaluations=evaluations, considered=omitted)
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "retain every Validation evaluation"):
            self.selection_artifact(evaluations=evaluations, considered=changed)

    def test_selection_input_echo_mismatch_rejected(self):
        dataset = self.validation_dataset()
        shortlist = self.shortlist()
        criteria = self.criteria()
        evaluations = self.validation_evaluations(dataset)
        base_input = self.selection_input(dataset, shortlist, criteria, evaluations)
        cases = (
            replace(base_input, validation_dataset_checksum="changed_dataset_checksum"),
            replace(base_input, development_shortlist_checksum="changed_shortlist_checksum"),
            replace(base_input, selection_criteria_checksum="changed_criteria_checksum"),
            replace(base_input, validation_evaluation_checksums=("changed", evaluations[1].evaluation_checksum)),
        )

        for selection_input in cases:
            with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "echo mismatch"):
                TechnicalRiskValidationSelectionArtifact.from_validation_contracts(
                    validation_dataset=dataset,
                    development_shortlist=shortlist,
                    selection_criteria=criteria,
                    selection_input=selection_input,
                    validation_evaluations=evaluations,
                    selection_decision=self.decision(selected_evaluation=evaluations[0]),
                    considered_combinations=self.considered(evaluations),
                )

    def test_selection_artifact_determinism_reorder_and_audit_metadata(self):
        evaluations = self.validation_evaluations()
        first = self.selection_artifact(
            evaluations=evaluations,
            decision=self.decision(
                selected_evaluation=evaluations[0],
                approved_by="Alice",
                approved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                human_rationale="first rationale.",
            ),
        )
        second = self.selection_artifact(
            evaluations=tuple(reversed(evaluations)),
            considered=tuple(reversed(self.considered(evaluations))),
            decision=self.decision(
                selected_evaluation=evaluations[0],
                structured_selection_reason_codes=tuple(reversed((TechnicalRiskValidationSelectionReasonCode.SELECTED_METHOD_REVIEW,))),
                approved_by="Bob",
                approved_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                human_rationale="second rationale!",
            ),
        )

        self.assertEqual(first.selection_id, second.selection_id)
        self.assertEqual(first.selection_checksum, second.selection_checksum)

    def test_selection_semantic_changes_change_checksum(self):
        evaluations = self.validation_evaluations()
        first = self.selection_artifact(evaluations=evaluations)
        second = self.selection_artifact(
            evaluations=evaluations,
            decision=self.decision(selected_evaluation=evaluations[1]),
            considered=self.considered(
                evaluations,
                outcomes=(TechnicalRiskValidationCombinationOutcome.NOT_SELECTED, TechnicalRiskValidationCombinationOutcome.SELECTED),
                reason_codes=(
                    (TechnicalRiskValidationSelectionReasonCode.NOT_SELECTED_METHOD_PREFERENCE,),
                    (TechnicalRiskValidationSelectionReasonCode.SELECTED_METHOD_REVIEW,),
                ),
            ),
        )
        criteria_changed = self.selection_artifact(
            evaluations=evaluations,
            criteria=self.criteria(monotonicity_preference=TechnicalRiskMonotonicityPreference.REQUIRE_EVALUABLE),
        )

        self.assertNotEqual(first.selection_checksum, second.selection_checksum)
        self.assertNotEqual(first.selection_checksum, criteria_changed.selection_checksum)

    def test_reason_codes_are_controlled_non_duplicate_and_canonical(self):
        combination = TechnicalRiskValidationConsideredCombination.from_evaluation(
            evaluation=self.validation_evaluations()[0],
            selection_outcome=TechnicalRiskValidationCombinationOutcome.NOT_SELECTED,
            structured_reason_codes=(
                TechnicalRiskValidationSelectionReasonCode.NOT_SELECTED_SEPARATION_CONCERN,
                TechnicalRiskValidationSelectionReasonCode.NOT_SELECTED_METHOD_PREFERENCE,
            ),
        )

        self.assertEqual(
            combination.structured_reason_codes,
            (
                TechnicalRiskValidationSelectionReasonCode.NOT_SELECTED_METHOD_PREFERENCE,
                TechnicalRiskValidationSelectionReasonCode.NOT_SELECTED_SEPARATION_CONCERN,
            ),
        )
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "Duplicate structured reason"):
            replace(
                combination,
                structured_reason_codes=(
                    TechnicalRiskValidationSelectionReasonCode.NOT_SELECTED_METHOD_PREFERENCE,
                    TechnicalRiskValidationSelectionReasonCode.NOT_SELECTED_METHOD_PREFERENCE,
                ),
            )
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionError, "Unsupported structured reason code"):
            replace(combination, structured_reason_codes=("BEST_PROFIT",))

    def test_no_threshold_search_automatic_ranking_or_production_boundary(self):
        source = inspect.getsource(__import__("risk_oos.validation_selection", fromlist=[""]))
        forbidden_tokens = (
            "weighted",
            "cutoff",
            "profit",
            "def search",
            "def optimize",
            "def grid_search",
            "def find_best",
            "def evaluate_best",
            "select_best",
            "rank(",
            "generate_thresholds",
            "holdout_dataset_id",
            "holdout_evaluation_id",
            "RiskEvaluationPolicy",
            "RiskSignal",
            "TechnicalRiskSignalProducer",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_no_search_holdout_or_production_boundary(self):
        source = (SRC_PATH / "risk_oos" / "validation_selection.py").read_text(encoding="utf-8")
        forbidden_tokens = (
            "def search",
            "def optimize",
            "def grid_search",
            "def find_best",
            "def evaluate_best",
            "generate_thresholds",
            "holdout_dataset_id",
            "holdout_evaluation_id",
            "RiskEvaluationPolicy",
            "RiskSignal",
            "TechnicalRiskSignalProducer",
            "sqlite",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "scanner",
            "PDF",
            "open(",
            "Path(",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_no_holdout_or_freeze_public_api_exported(self):
        import risk_oos

        forbidden = {
            "HoldoutConfirmationArtifact",
            "TechnicalRiskPolicyFreezeArtifact",
        }
        self.assertTrue(forbidden.isdisjoint(set(risk_oos.__all__)))
        self.assertTrue(forbidden.isdisjoint({field.name for field in fields(DevelopmentShortlistArtifact)}))

    def test_b2_public_api_exports_only_selection_artifact_not_holdout_or_freeze(self):
        import risk_oos

        required = {
            "TechnicalRiskValidationSelectionInput",
            "TechnicalRiskValidationSelectionDecision",
            "TechnicalRiskValidationSelectionArtifact",
            "TechnicalRiskValidationSelectionStatus",
            "TechnicalRiskValidationCombinationOutcome",
            "TechnicalRiskValidationConsideredCombination",
            "TechnicalRiskValidationSelectionReasonCode",
        }
        forbidden = {
            "HoldoutConfirmationArtifact",
            "TechnicalRiskPolicyFreezeArtifact",
        }
        self.assertTrue(required.issubset(set(risk_oos.__all__)))
        self.assertTrue(forbidden.isdisjoint(set(risk_oos.__all__)))


if __name__ == "__main__":
    unittest.main()
