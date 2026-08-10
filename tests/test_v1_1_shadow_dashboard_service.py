import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import OutcomeEvaluationStatus
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL
from v1_1_shadow_dashboard_service import build_official_v1_1_shadow_dashboard_view
from v1_1_shadow_dashboard_service import build_v1_1_shadow_dashboard_view
from v1_1_shadow_comparison_service import VOLUME_CONDITION_ID


class V11ShadowDashboardServiceTestCase(unittest.TestCase):

    def outcome(self, status):
        return SimpleNamespace(status=status, signal_date=date(2025, 1, 1))

    def source_observation(self, status, volume):
        return SimpleNamespace(
            status=status,
            diagnostic_observation=SimpleNamespace(
                source_snapshot=SimpleNamespace(volume_ratio_20=volume),
            ),
        )

    def shadow_observation(self, *, shared, status=OutcomeEvaluationStatus.HIT, volume=1.20):
        source = self.source_observation(status, volume)
        outcome = self.outcome(status)
        return SimpleNamespace(
            symbol="2330.TW",
            trading_date=date(2025, 1, 1),
            v1_qualified=shared,
            v1_1_qualified=True,
            v1_outcome=outcome if shared else None,
            v1_1_outcome=outcome,
            source_observation=source,
            is_shared_observation=shared,
            is_v1_1_only_observation=not shared,
        )

    def shadow_result(self):
        observations = []
        observations.extend(self.shadow_observation(shared=True, status=OutcomeEvaluationStatus.HIT, volume=1.20) for _ in range(1567))
        observations.extend(self.shadow_observation(shared=True, status=OutcomeEvaluationStatus.MISS, volume=1.30) for _ in range(254))
        observations.extend(self.shadow_observation(shared=False, status=OutcomeEvaluationStatus.HIT, volume=1.100186) for _ in range(201))
        observations.extend(self.shadow_observation(shared=False, status=OutcomeEvaluationStatus.MISS, volume=1.199675) for _ in range(50))
        return SimpleNamespace(
            production_signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
            experimental_signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1_1_EXPERIMENTAL,
            observations=tuple(observations),
            summary=SimpleNamespace(
                v1_observation_count=1821,
                v1_1_observation_count=2072,
                added_observation_count=251,
                shared_observation_count=1821,
            ),
        )

    def robustness_result(self):
        return SimpleNamespace(
            overlap_reduced_summaries=(
                SimpleNamespace(threshold=1.10, overlap_reduced_observation_count=800, overlap_reduced_hit_rate=0.8750),
                SimpleNamespace(threshold=1.20, overlap_reduced_observation_count=771, overlap_reduced_hit_rate=0.8768),
            )
        )

    def time_robustness_result(self):
        periods = (
            SimpleNamespace(name="PERIOD_A"),
            SimpleNamespace(name="PERIOD_B"),
            SimpleNamespace(name="PERIOD_C"),
            SimpleNamespace(name="PERIOD_D"),
        )
        period_summaries = []
        for period in periods:
            period_summaries.append(
                SimpleNamespace(
                    period_name=period.name,
                    threshold_summary=SimpleNamespace(threshold=1.10, historical_hit_rate=0.85),
                )
            )
            period_summaries.append(
                SimpleNamespace(
                    period_name=period.name,
                    threshold_summary=SimpleNamespace(threshold=1.20, historical_hit_rate=0.86),
                )
            )
        return SimpleNamespace(
            periods=periods,
            event_summaries=(
                SimpleNamespace(threshold=1.10, first_qualification_event_count=1458, event_hit_rate=0.8635),
                SimpleNamespace(threshold=1.20, first_qualification_event_count=1327, event_hit_rate=0.8666),
            ),
            period_summaries=tuple(period_summaries),
        )

    def view(self):
        return build_v1_1_shadow_dashboard_view(
            self.shadow_result(),
            robustness_result=self.robustness_result(),
            time_robustness_result=self.time_robustness_result(),
        )

    def test_side_by_side_identity_counts_and_badges(self):
        view = self.view()

        self.assertEqual(view.production_card["Definition ID"], "technical_example_v1")
        self.assertEqual(view.experimental_card["Definition ID"], "technical_example_v1_1_experimental")
        self.assertIn("正式 V1", view.production_card["Status"])
        self.assertIn("實驗版", view.experimental_card["Status"])
        self.assertEqual(view.production_card["Volume Threshold"], "volume_ratio_20 >= 1.20")
        self.assertEqual(view.experimental_card["Volume Threshold"], "volume_ratio_20 >= 1.10")
        self.assertEqual(view.production_card["Observation Count"], 1821)
        self.assertEqual(view.experimental_card["Observation Count"], 2072)
        self.assertEqual(view.production_card["Historical Hit Rate Display"], "86.05%")
        self.assertEqual(view.experimental_card["Historical Hit Rate Display"], "85.33%")

    def test_delta_arithmetic_and_shared_incremental_counts(self):
        rows = {row["Metric"]: row for row in self.view().delta_rows}

        self.assertEqual(rows["共同樣本"]["Value"], 1821)
        self.assertEqual(rows["V1.1 新增樣本"]["Value"], 251)
        self.assertEqual(rows["Observation increase"]["Display"], "13.78%")
        self.assertEqual(rows["HHR difference"]["Display"], "-0.72 pp")

    def test_definition_rows_mark_only_volume_as_different(self):
        rows = self.view().definition_rows

        self.assertEqual(sum(row["Status"] == "唯一差異" for row in rows), 1)
        volume = next(row for row in rows if row["Condition"] == "Volume ratio")
        self.assertEqual(volume["Production V1"], "volume_ratio_20 >= 1.20")
        self.assertEqual(volume["V1.1 Experimental"], "volume_ratio_20 >= 1.10")

    def test_evidence_rows_include_daily_reduced_event_and_time_periods(self):
        view = self.view()
        evidence = {row["Evidence"]: row for row in view.evidence_rows}

        self.assertEqual(evidence["Daily"]["V1 n"], 1821)
        self.assertEqual(evidence["Daily"]["V1.1 n"], 2072)
        self.assertEqual(evidence["20-bar reduced"]["V1 n"], 771)
        self.assertEqual(evidence["20-bar reduced"]["V1.1 n"], 800)
        self.assertEqual(evidence["First-event"]["V1 n"], 1327)
        self.assertEqual(evidence["First-event"]["V1.1 n"], 1458)
        self.assertEqual([row["Period"] for row in view.time_robustness_rows], ["2018–2020", "2021–2023", "2024", "2025"])

    def test_incremental_table_fields_and_forbidden_fields(self):
        rows = self.view().incremental_rows
        forbidden = ("recommendation", "confidence", "rank", "score")

        self.assertEqual(len(rows), 251)
        self.assertEqual(rows[0]["signal_definition_id"], "technical_example_v1_1_experimental")
        self.assertGreaterEqual(rows[0][VOLUME_CONDITION_ID], 1.10)
        self.assertLess(rows[-1][VOLUME_CONDITION_ID], 1.20)
        for row in rows:
            for forbidden_name in forbidden:
                self.assertFalse(any(forbidden_name in field for field in row))

    def test_official_builder_reuses_canonical_shadow_service(self):
        with patch("v1_1_shadow_dashboard_service._build_official_comparison_result", return_value=(object(), {}, ("2330.TW",))):
            with patch("v1_1_shadow_dashboard_service.compare_v1_v1_1_shadow_definitions", return_value=self.shadow_result()) as shadow:
                with patch("v1_1_shadow_dashboard_service.analyze_volume_threshold_robustness", return_value=self.robustness_result()):
                    with patch("v1_1_shadow_dashboard_service.analyze_volume_threshold_time_robustness", return_value=self.time_robustness_result()):
                        view = build_official_v1_1_shadow_dashboard_view()

        shadow.assert_called_once()
        self.assertEqual(view.experimental_card["Observation Count"], 2072)


if __name__ == "__main__":
    unittest.main()
