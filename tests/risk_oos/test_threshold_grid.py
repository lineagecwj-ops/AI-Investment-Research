import inspect
import sys
import unittest
from dataclasses import fields
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos import TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1
from risk_oos import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos import TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1
from risk_oos import TECH_RISK_THRESHOLD_GRID_RESULT_V1
from risk_oos import TECH_RISK_THRESHOLD_GRID_SPEC_V1
from risk_oos import TechnicalRiskCandidateFamily
from risk_oos import TechnicalRiskThresholdDimensionId
from risk_oos import TechnicalRiskThresholdGridError
from risk_oos import TechnicalRiskThresholdGridMaterializer
from risk_oos import TechnicalRiskThresholdGridResult
from risk_oos import TechnicalRiskThresholdGridSpec
from risk_oos import TechnicalRiskThresholdOperator
from risk_oos import TechnicalRiskThresholdSet
from risk_oos import ThresholdCandidateGenerationContract


class TechnicalRiskThresholdGridTestCase(unittest.TestCase):
    def spec(self, **overrides):
        values = {
            "grid_spec_id": None,
            "grid_spec_version": TECH_RISK_THRESHOLD_GRID_SPEC_V1,
            "generation_method_id": TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1,
            "generation_method_version": "test_method_v1",
            "source_spec_version": "test_only_threshold_grid_spec_v1",
            "candidate_family": TechnicalRiskCandidateFamily.MEDIUM_TERM_TREND_CENTRIC,
            "compatible_candidate_families": tuple(TechnicalRiskCandidateFamily),
            "close_vs_sma20_values": ("-0.01", "-0.02"),
            "close_vs_sma60_values": ("-0.03", "-0.04"),
            "relative_sma_spread_values": ("-0.005",),
            "rsi14_values": ("35", "40"),
        }
        values.update(overrides)
        return TechnicalRiskThresholdGridSpec(**values)

    def materialize(self, **overrides):
        return TechnicalRiskThresholdGridMaterializer().materialize(self.spec(**overrides))

    def test_explicit_four_axis_grid_materializes_cartesian_threshold_sets(self):
        result = self.materialize()

        self.assertEqual(len(result.threshold_sets), 8)
        self.assertTrue(all(isinstance(threshold_set, TechnicalRiskThresholdSet) for threshold_set in result.threshold_sets))
        self.assertIsInstance(result.generation_contract, ThresholdCandidateGenerationContract)
        self.assertEqual(result.generation_contract.generation_version, TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1)
        self.assertEqual(result.grid_result_version, TECH_RISK_THRESHOLD_GRID_RESULT_V1)

    def test_dimensions_and_operator_are_exact(self):
        result = self.materialize()

        for threshold_set in result.threshold_sets:
            dimensions = threshold_set.dimensions_by_id
            self.assertEqual(set(dimensions), set(TechnicalRiskThresholdDimensionId))
            self.assertEqual(
                tuple(sorted(dimension.dimension_id.value for dimension in threshold_set.dimensions)),
                tuple(sorted(dimension.value for dimension in TechnicalRiskThresholdDimensionId)),
            )
            self.assertTrue(all(dimension.operator == TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL for dimension in threshold_set.dimensions))

    def test_threshold_ids_checksums_and_grid_identity_are_deterministic(self):
        first = self.materialize()
        second = self.materialize()

        self.assertEqual(tuple(item.threshold_set_id for item in first.threshold_sets), tuple(item.threshold_set_id for item in second.threshold_sets))
        self.assertEqual(
            tuple(item.threshold_set_checksum for item in first.threshold_sets),
            tuple(item.threshold_set_checksum for item in second.threshold_sets),
        )
        self.assertEqual(first.generation_contract.generation_id, second.generation_contract.generation_id)
        self.assertEqual(first.generation_contract.generation_checksum, second.generation_contract.generation_checksum)
        self.assertEqual(first.grid_result_id, second.grid_result_id)
        self.assertEqual(first.grid_result_checksum, second.grid_result_checksum)

    def test_input_axis_order_does_not_change_semantic_identity(self):
        first = self.materialize(
            close_vs_sma20_values=("-0.02", "-0.01"),
            close_vs_sma60_values=("-0.04", "-0.03"),
            rsi14_values=("40", "35"),
        )
        second = self.materialize()

        self.assertEqual(first.grid_result_id, second.grid_result_id)
        self.assertEqual(first.grid_result_checksum, second.grid_result_checksum)
        self.assertEqual(first.generation_contract.generated_threshold_set_ids, second.generation_contract.generated_threshold_set_ids)

    def test_decimal_canonicalization_preserves_semantic_identity(self):
        first = self.materialize(close_vs_sma20_values=(Decimal("-0.0100"), "-0.0200"), rsi14_values=("35.0", "40.00"))
        second = self.materialize()

        self.assertEqual(first.grid_result_id, second.grid_result_id)
        self.assertEqual(first.generation_contract.generation_checksum, second.generation_contract.generation_checksum)

    def test_empty_axis_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskThresholdGridError, "must not be empty"):
            self.spec(rsi14_values=())

    def test_duplicate_axis_values_fail_closed_after_canonicalization(self):
        with self.assertRaisesRegex(TechnicalRiskThresholdGridError, "Duplicate"):
            self.spec(close_vs_sma20_values=("-0.020", "-0.02"))

    def test_invalid_numeric_values_fail_closed(self):
        with self.assertRaisesRegex(TechnicalRiskThresholdGridError, "Invalid"):
            self.spec(rsi14_values=("NaN",))
        with self.assertRaisesRegex(TechnicalRiskThresholdGridError, "Invalid"):
            self.spec(rsi14_values=(True,))

    def test_unsupported_numeric_versions_fail_closed(self):
        with self.assertRaisesRegex(TechnicalRiskThresholdGridError, "numeric_representation_version"):
            self.spec(numeric_representation_version="float_v1")
        with self.assertRaisesRegex(TechnicalRiskThresholdGridError, "numeric_context_version"):
            self.spec(numeric_context_version="context_v2")

    def test_generation_contract_matches_materialized_threshold_identities(self):
        result = self.materialize()

        self.assertEqual(
            result.generation_contract.generated_threshold_set_ids,
            tuple(threshold.threshold_set_id for threshold in result.threshold_sets),
        )
        self.assertEqual(
            result.generation_contract.generated_threshold_set_checksums,
            tuple(threshold.threshold_set_checksum for threshold in result.threshold_sets),
        )
        self.assertEqual(result.generation_contract.numeric_representation_version, TECH_RISK_NUMERIC_REPRESENTATION_V1)
        self.assertEqual(result.generation_contract.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1)

    def test_generation_method_change_changes_grid_identity(self):
        first = self.materialize(generation_method_version="test_method_v1")
        second = self.materialize(generation_method_version="test_method_v2")

        self.assertNotEqual(first.generation_contract.generation_id, second.generation_contract.generation_id)
        self.assertNotEqual(first.grid_result_id, second.grid_result_id)

    def test_result_rejects_mismatched_generation_contract(self):
        result = self.materialize()
        bad_contract = ThresholdCandidateGenerationContract(
            generation_id=None,
            generation_version=TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1,
            generation_method_id=result.generation_contract.generation_method_id,
            generation_method_version=result.generation_contract.generation_method_version,
            numeric_representation_version=TECH_RISK_NUMERIC_REPRESENTATION_V1,
            numeric_context_version=TECH_RISK_DECIMAL_CONTEXT_V1,
            candidate_family=result.generation_contract.candidate_family,
            source_spec_version=result.generation_contract.source_spec_version,
            generated_threshold_set_ids=result.generation_contract.generated_threshold_set_ids[:-1],
            generated_threshold_set_checksums=result.generation_contract.generated_threshold_set_checksums[:-1],
        )

        with self.assertRaisesRegex(TechnicalRiskThresholdGridError, "do not match"):
            TechnicalRiskThresholdGridResult(
                grid_result_id=None,
                grid_result_version=TECH_RISK_THRESHOLD_GRID_RESULT_V1,
                grid_spec=result.grid_spec,
                threshold_sets=result.threshold_sets,
                generation_contract=bad_contract,
            )

    def test_no_default_threshold_axis_values(self):
        required_fields = {
            "close_vs_sma20_values",
            "close_vs_sma60_values",
            "relative_sma_spread_values",
            "rsi14_values",
        }
        fields_by_name = {field.name: field for field in fields(TechnicalRiskThresholdGridSpec)}

        self.assertTrue(required_fields.issubset(fields_by_name))
        for field_name in required_fields:
            self.assertEqual(fields_by_name[field_name].default.__class__.__name__, "_MISSING_TYPE")
            self.assertEqual(fields_by_name[field_name].default_factory.__class__.__name__, "_MISSING_TYPE")

    def test_no_candidate_selection_holdout_persistence_or_network_boundary(self):
        import risk_oos.threshold_grid as threshold_grid

        source = inspect.getsource(threshold_grid)
        forbidden_tokens = (
            "TECH_POLICY_CANDIDATE_A",
            "TECH_POLICY_CANDIDATE_B",
            "TECH_POLICY_CANDIDATE_C",
            "TECH_POLICY_CANDIDATE_D",
            "winner",
            "best_threshold",
            "selected_threshold",
            "holdout",
            "sqlite",
            "write_text",
            "open(",
            "production_runtime",
            "ProductionPolicyPin",
            "Streamlit",
            "app.py",
            "Yahoo",
            "yfinance",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
