import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import OutcomeEvaluationStatus
from models import OverlappingSignalPolicy
from models import SignalEvaluationStatus
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from ui_terminology import format_condition_labels
from ui_terminology import get_outcome_definition_label
from ui_terminology import get_outcome_status_label
from ui_terminology import get_overlap_policy_label
from ui_terminology import get_scan_mode_label
from ui_terminology import get_scan_status_label
from ui_terminology import get_signal_definition_label
from ui_terminology import get_signal_status_label
from ui_terminology import get_technical_metric_label
from walk_forward_replay_service import WalkForwardReplayFrequency


class UiTerminologyTestCase(unittest.TestCase):

    def test_scan_status_labels(self):
        self.assertEqual(get_scan_status_label("MATCH"), "符合條件")
        self.assertEqual(get_scan_status_label("NO_MATCH"), "不符合條件")
        self.assertEqual(get_scan_status_label("NOT_EVALUABLE"), "資料不足")
        self.assertEqual(get_scan_status_label("FAILED"), "掃描失敗")

    def test_metric_definition_and_policy_labels(self):
        self.assertEqual(get_technical_metric_label("volume_ratio_20"), "20 日成交量比率")
        self.assertEqual(get_technical_metric_label("distance_to_prior_60d_high"), "距離前 60 日高點")
        self.assertEqual(get_signal_definition_label("technical_example_v1"), "波段技術篩選 V1")
        self.assertEqual(get_outcome_definition_label("raw_high_breakout_60d_within_20d_v1"), "20 個交易日內突破前 60 日高點")
        self.assertEqual(get_overlap_policy_label("ALLOW_ALL"), "保留全部訊號")

    def test_scan_mode_labels(self):
        self.assertEqual(get_scan_mode_label("Historical Replay"), "歷史回放")
        self.assertEqual(get_scan_mode_label("Walk-Forward Replay"), "多日期歷史回放")
        self.assertEqual(get_scan_mode_label("Out-of-Sample Validation"), "樣本外驗證")

    def test_condition_labels_are_display_only(self):
        self.assertEqual(
            format_condition_labels(("volume_ratio_20", "distance_to_prior_60d_high")),
            "20 日成交量比率、距離前 60 日高點",
        )

    def test_domain_values_are_not_renamed(self):
        self.assertEqual(TECHNICAL_EXAMPLE_SIGNAL_V1.id, "technical_example_v1")
        self.assertEqual(RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1.id, "raw_high_breakout_60d_within_20d_v1")
        self.assertEqual(SignalEvaluationStatus.MATCH.value, "MATCH")
        self.assertEqual(get_signal_status_label(SignalEvaluationStatus.MATCH.value), "符合")
        self.assertEqual(OutcomeEvaluationStatus.HIT.value, "HIT")
        self.assertEqual(get_outcome_status_label(OutcomeEvaluationStatus.HIT.value), "達成研究目標（HIT）")
        self.assertEqual(WalkForwardReplayFrequency.MONTHLY.value, "MONTHLY")
        self.assertEqual(OverlappingSignalPolicy.ALLOW_ALL.value, "ALLOW_ALL")


if __name__ == "__main__":
    unittest.main()
