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
from ui_terminology import format_diagnostic_condition_labels
from ui_terminology import get_diagnostic_beginner_explanation
from ui_terminology import get_diagnostic_condition_label
from ui_terminology import get_diagnostic_label
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

    def test_diagnostic_labels_are_traditional_chinese(self):
        self.assertEqual(get_diagnostic_label("Historical Condition Diagnostics"), "V1 歷史條件診斷")
        self.assertEqual(get_diagnostic_label("Historical Outcome Comparison"), "歷史後續結果比較")
        self.assertEqual(get_diagnostic_label("Match Count Distribution"), "歷史條件命中分布")
        self.assertEqual(get_diagnostic_label("Matched Conditions"), "符合條件數")
        self.assertEqual(get_diagnostic_label("Condition Pass Rate"), "單一條件通過率")
        self.assertEqual(get_diagnostic_label("Missing Condition"), "未符合條件")
        self.assertEqual(get_diagnostic_label("Most Common Missing Condition"), "最常缺少的條件")
        self.assertEqual(get_diagnostic_label("Condition Combination"), "條件組合")
        self.assertEqual(get_diagnostic_label("4/5 Missing Condition Outcome"), "4/5 案例：缺少條件與歷史後續結果")
        self.assertEqual(get_diagnostic_label("Evaluated Observations"), "可評估歷史樣本")
        self.assertEqual(get_diagnostic_label("Not Evaluable"), "無法評估")
        self.assertEqual(get_diagnostic_label("Observation Count"), "歷史樣本數")
        self.assertEqual(get_diagnostic_label("Resolved Samples"), "已解析歷史樣本數")
        self.assertEqual(get_diagnostic_label("Historical Hit Rate"), "歷史命中率")
        self.assertEqual(get_diagnostic_label("Share"), "占可評估樣本比例")
        self.assertEqual(get_diagnostic_label("HIT"), "達成研究目標")
        self.assertEqual(get_diagnostic_label("MISS"), "未達成研究目標")
        self.assertEqual(get_diagnostic_label("INCOMPLETE"), "後續資料尚不完整")
        self.assertEqual(get_diagnostic_label("NOT_EVALUABLE"), "無法評估")

    def test_diagnostic_condition_primary_labels_hide_raw_metric_ids(self):
        labels = [
            get_diagnostic_condition_label("analysis_close_vs_sma_20"),
            get_diagnostic_condition_label("sma_20_vs_sma_60"),
            get_diagnostic_condition_label("volume_ratio_20"),
            get_diagnostic_condition_label("rsi_14"),
            get_diagnostic_condition_label("distance_to_prior_60d_high"),
        ]

        self.assertEqual(
            labels,
            [
                "股價高於 20 日均線",
                "20 日均線高於 60 日均線",
                "20 日成交量比率",
                "RSI 14 日相對強弱指標",
                "距離前 60 日高點",
            ],
        )
        self.assertFalse(any("_" in label for label in labels))
        self.assertFalse(any("analysis_close" in label for label in labels))
        self.assertFalse(any("distance_to_prior_60d_high" in label for label in labels))

    def test_diagnostic_matched_count_is_not_score(self):
        self.assertEqual(get_diagnostic_label("Matched Conditions"), "符合條件數")
        self.assertNotEqual(get_diagnostic_label("Matched Conditions"), "分數")

    def test_diagnostic_batch_one_labels_do_not_include_historical_hit_rate(self):
        labels = {
            get_diagnostic_label("Historical Condition Diagnostics"),
            get_diagnostic_label("Match Count Distribution"),
            get_diagnostic_label("Condition Pass Rate"),
            get_diagnostic_label("Condition Combination"),
        }

        self.assertFalse(any("Historical Hit Rate" in label for label in labels))
        self.assertFalse(any("歷史命中率" in label for label in labels))

    def test_diagnostic_beginner_explanations_are_centralized(self):
        self.assertIn(
            "統計每個有效交易日符合 V1 五項技術條件中的幾項",
            get_diagnostic_beginner_explanation("Historical Condition Diagnostics"),
        )
        self.assertIn(
            "既定 20 個交易日研究期間內突破當時的前 60 日高點",
            get_diagnostic_beginner_explanation("Historical Outcome Comparison"),
        )
        self.assertIn(
            "不代表未來發生機率",
            get_diagnostic_beginner_explanation("Historical Hit Rate"),
        )
        self.assertIn(
            "找出最常缺少的最後一項條件",
            get_diagnostic_beginner_explanation("Most Common Missing Condition"),
        )
        self.assertIn(
            "不同缺失條件與後續歷史結果的差異",
            get_diagnostic_beginner_explanation("4/5 Missing Condition Outcome"),
        )
        self.assertEqual(
            format_diagnostic_condition_labels(("volume_ratio_20", "rsi_14")),
            "20 日成交量比率、RSI 14 日相對強弱指標",
        )

    def test_condition_contribution_terminology_is_traditional_chinese_first(self):
        self.assertEqual(get_diagnostic_label("Single Condition Contribution Analysis"), "單一條件影響分析")
        self.assertEqual(get_diagnostic_label("Original V1"), "原始 V1")
        self.assertEqual(get_diagnostic_label("Assume Condition Not Required"), "假設不要求此條件")
        self.assertEqual(get_diagnostic_label("Added Historical Observations"), "新增歷史樣本數")
        self.assertEqual(get_diagnostic_label("Added Resolved Historical Observations"), "新增已解析歷史樣本數")
        self.assertEqual(get_diagnostic_label("Added HIT"), "新增 HIT")
        self.assertEqual(get_diagnostic_label("Added MISS"), "新增 MISS")
        self.assertEqual(get_diagnostic_label("Observation Increase Rate"), "樣本增加比例")
        self.assertEqual(get_diagnostic_label("Historical Hit Rate Change"), "歷史命中率變化")
        self.assertEqual(get_diagnostic_label("Percentage Points"), "百分點")
        self.assertEqual(get_diagnostic_label("Daily Observations"), "每日觀察樣本")
        self.assertEqual(get_diagnostic_label("Overlap Possible"), "樣本可能重疊")

        self.assertIn(
            "取消某一條件要求後",
            get_diagnostic_beginner_explanation("Single Condition Contribution Analysis"),
        )
        self.assertIn(
            "不是未來發生機率",
            get_diagnostic_beginner_explanation("Historical Hit Rate Change"),
        )
        self.assertIn(
            "不代表該條件應被移除",
            get_diagnostic_beginner_explanation("Single Condition Contribution Safety Note"),
        )
        self.assertIn(
            "不能解讀成相同數量的獨立交易",
            get_diagnostic_beginner_explanation("Daily Observation Overlap Note"),
        )

    def test_volume_threshold_sensitivity_terminology_is_traditional_chinese_first(self):
        self.assertEqual(get_diagnostic_label("Volume Threshold Sensitivity Analysis"), "成交量門檻變化測試")
        self.assertEqual(get_diagnostic_label("Threshold Sensitivity"), "門檻變化測試")
        self.assertEqual(get_diagnostic_label("Volume Ratio Threshold"), "成交量比率門檻")
        self.assertEqual(get_diagnostic_label("Current V1 Threshold"), "目前 V1 門檻")
        self.assertEqual(get_diagnostic_label("Observation Count"), "歷史樣本數")
        self.assertEqual(get_diagnostic_label("Resolved Samples"), "已解析歷史樣本數")
        self.assertEqual(get_diagnostic_label("Historical Hit Rate"), "歷史命中率")
        self.assertEqual(get_diagnostic_label("Observation Count Change vs V1"), "相對目前 V1 的樣本變化")
        self.assertEqual(get_diagnostic_label("Historical Hit Rate Change vs V1"), "相對目前 V1 的歷史命中率變化")
        self.assertEqual(get_diagnostic_label("Percentage Points"), "百分點")
        self.assertEqual(get_diagnostic_label("Lower Threshold"), "門檻越低")
        self.assertEqual(get_diagnostic_label("Higher Threshold"), "門檻越高")
        self.assertEqual(get_diagnostic_label("Daily Observations"), "每日觀察樣本")
        self.assertEqual(get_diagnostic_label("Overlap Possible"), "樣本可能重疊")

        self.assertIn(
            "固定其他四項 V1 條件",
            get_diagnostic_beginner_explanation("Volume Threshold Sensitivity Analysis"),
        )
        self.assertIn(
            "本測試不會修改正式 V1",
            get_diagnostic_beginner_explanation("Volume Threshold Sensitivity Baseline Note"),
        )
        self.assertIn(
            "不代表該門檻是最佳設定",
            get_diagnostic_beginner_explanation("Volume Threshold Sensitivity Safety Note"),
        )
        self.assertIn(
            "需要進一步研究",
            get_diagnostic_beginner_explanation("Volume Threshold Sensitivity Sample Note"),
        )

    def test_volume_threshold_robustness_terminology_is_traditional_chinese_first(self):
        self.assertEqual(get_diagnostic_label("Volume Threshold Robustness Analysis"), "成交量門檻穩健性分析")
        self.assertEqual(get_diagnostic_label("Per-Symbol Robustness"), "逐股票穩健性")
        self.assertEqual(get_diagnostic_label("Per-Year Robustness"), "逐年度穩健性")
        self.assertEqual(get_diagnostic_label("Overlap-Reduced Samples"), "降低樣本重疊")
        self.assertEqual(get_diagnostic_label("Original Daily Samples"), "原始每日樣本")
        self.assertEqual(get_diagnostic_label("Reduced-Overlap Samples"), "降低重疊後樣本")
        self.assertEqual(get_diagnostic_label("Difference vs Formal V1"), "相對正式 V1 差異")
        self.assertEqual(get_diagnostic_label("Historical Hit Rate Difference"), "歷史命中率差異")
        self.assertEqual(get_diagnostic_label("Observation Count Difference"), "樣本數差異")
        self.assertEqual(get_diagnostic_label("20 Trading-Bar Spacing"), "20 個交易日間隔")

        self.assertIn(
            "不同股票與不同年份",
            get_diagnostic_beginner_explanation("Volume Threshold Robustness Analysis"),
        )
        self.assertIn(
            "至少相隔 20 個交易日",
            get_diagnostic_beginner_explanation("Overlap-Reduced Samples"),
        )
        self.assertIn(
            "百分點差異",
            get_diagnostic_beginner_explanation("Historical Hit Rate Difference"),
        )
        self.assertIn(
            "不代表完全獨立樣本",
            get_diagnostic_beginner_explanation("Overlap-Reduced Independence Warning"),
        )


if __name__ == "__main__":
    unittest.main()
