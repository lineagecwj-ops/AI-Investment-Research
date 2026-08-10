from __future__ import annotations


SCAN_MODE_LABELS = {
    "Current": "目前市場",
    "Historical Replay": "歷史回放",
    "Walk-Forward Replay": "多日期歷史回放",
    "Out-of-Sample Validation": "樣本外驗證",
}

SOURCE_LABELS = {
    "Manual Input": "手動輸入",
    "Watchlist": "觀察清單",
    "Saved Universe": "已儲存股票池",
    "Frozen TWSE Research Universe": "研究股票池（Frozen TWSE 218）",
}

SCAN_STATUS_LABELS = {
    "Scanned": "已掃描",
    "MATCH": "符合條件",
    "NO_MATCH": "不符合條件",
    "NOT_EVALUABLE": "資料不足",
    "FAILED": "掃描失敗",
}

SIGNAL_STATUS_LABELS = {
    "MATCH": "符合",
    "NO_MATCH": "不符合",
    "NOT_EVALUABLE": "資料不足，無法判斷",
    "FAILED": "計算失敗",
}

SIGNAL_DEFINITION_LABELS = {
    "technical_example_v1": "波段技術篩選 V1",
    "technical_example_v1_1_experimental": "波段技術篩選 V1.1 實驗版",
}

OUTCOME_DEFINITION_LABELS = {
    "raw_high_breakout_60d_within_20d_v1": "20 個交易日內突破前 60 日高點",
}

OVERLAP_POLICY_LABELS = {
    "ALLOW_ALL": "保留全部訊號",
    "COOLDOWN": "訊號間隔限制",
}

OUTCOME_STATUS_LABELS = {
    "HIT": "達成研究目標（HIT）",
    "MISS": "未達研究目標（MISS）",
    "INCOMPLETE": "觀察期間尚未完整",
    "NOT_EVALUABLE": "無法判定",
    "FAILED": "計算失敗",
}

FREQUENCY_LABELS = {
    "MONTHLY": "每月",
    "WEEKLY": "每週",
}

SAMPLE_STATUS_LABELS = {
    "NO_RESOLVED_SAMPLES": "尚無已解析歷史樣本",
    "BELOW_PREFERRED_MINIMUM": "低於偏好最低樣本數",
    "MEETS_PREFERRED_MINIMUM": "達到偏好最低樣本數",
}

TECHNICAL_METRIC_LABELS = {
    "analysis_close": "分析價格",
    "sma_5": "5 日均線",
    "sma_10": "10 日均線",
    "sma_20": "20 日均線",
    "sma_60": "60 日均線",
    "sma_120": "120 日均線",
    "sma_200": "200 日均線",
    "ema_12": "12 日指數移動平均線",
    "ema_26": "26 日指數移動平均線",
    "rsi_14": "RSI 14 日相對強弱指標",
    "macd": "MACD",
    "macd_signal": "MACD 訊號線",
    "macd_histogram": "MACD 柱狀差值",
    "atr_14": "ATR 14 日平均真實波幅",
    "atr_14_pct": "ATR 波動幅度比例",
    "atr_percent": "ATR 波動幅度比例",
    "volume_sma_20": "20 日平均成交量",
    "volume_ratio_20": "20 日成交量比率",
    "high_20d": "20 日高點",
    "high_60d": "60 日高點",
    "high_252d": "52 週高點",
    "low_20d": "20 日低點",
    "low_60d": "60 日低點",
    "prior_20d_high": "前 20 日高點",
    "prior_60d_high": "前 60 日高點",
    "prior_52_week_high": "前 52 週高點",
    "prior_20d_low": "前 20 日低點",
    "prior_60d_low": "前 60 日低點",
    "prior_high_20d": "前 20 日高點",
    "prior_high_60d": "前 60 日高點",
    "prior_high_252d": "前 52 週高點",
    "prior_low_20d": "前 20 日低點",
    "prior_low_60d": "前 60 日低點",
    "distance_to_prior_20d_high": "距離前 20 日高點",
    "distance_to_prior_60d_high": "距離前 60 日高點",
    "distance_to_prior_52_week_high": "距離前 52 週高點",
    "close_above_sma20": "價格高於 20 日均線",
    "close_above_sma60": "價格高於 60 日均線",
    "sma20_above_sma60": "20 日均線高於 60 日均線",
    "sma60_above_sma120": "60 日均線高於 120 日均線",
    "is_above_prior_20d_high": "突破前 20 日高點",
    "is_above_prior_60d_high": "突破前 60 日高點",
    "is_above_prior_52_week_high": "突破前 52 週高點",
    "return_5d": "5 日價格變化",
    "return_20d": "20 日價格變化",
    "return_60d": "60 日價格變化",
    "return_volatility_20d": "20 日價格變化波動度",
    "range_position_20d": "20 日區間位置",
    "range_position_60d": "60 日區間位置",
    "position_in_prior_60d_range": "前 60 日區間位置",
    "sma20_change_5d": "20 日均線 5 日變化",
    "sma60_change_5d": "60 日均線 5 日變化",
}

DIAGNOSTIC_LABELS = {
    "Historical Condition Diagnostics": "V1 歷史條件診斷",
    "Historical Outcome Comparison": "歷史後續結果比較",
    "Match Count Distribution": "歷史條件命中分布",
    "Matched Conditions": "符合條件數",
    "Condition Pass Rate": "單一條件通過率",
    "Missing Condition": "未符合條件",
    "Most Common Missing Condition": "最常缺少的條件",
    "Condition Combination": "條件組合",
    "4/5 Missing Condition Outcome": "4/5 案例：缺少條件與歷史後續結果",
    "V1 Historical Condition Dashboard Caption": "查看歷史上符合不同數量 V1 條件時，後續研究結果有何差異。",
    "V1 Condition Effectiveness Overview": "V1 條件有效性總覽",
    "Conditions Causing Differences": "哪些條件最常造成差異",
    "Hard-To-Pass V1 Conditions": "哪些 V1 條件本來就比較難符合？",
    "Advanced Research Information": "進階研究資訊",
    "Evaluated Observations": "可評估歷史樣本",
    "Not Evaluable": "無法評估",
    "Observation Count": "歷史樣本數",
    "Resolved Samples": "已解析歷史樣本數",
    "Historical Hit Rate": "歷史命中率",
    "Share": "占可評估樣本比例",
    "HIT": "達成研究目標",
    "MISS": "未達成研究目標",
    "INCOMPLETE": "後續資料尚不完整",
    "NOT_EVALUABLE": "無法評估",
    "Single Condition Contribution Analysis": "單一條件影響分析",
    "Original V1": "原始 V1",
    "Assume Condition Not Required": "假設不要求此條件",
    "Added Historical Observations": "新增歷史樣本數",
    "Added Resolved Historical Observations": "新增已解析歷史樣本數",
    "Added HIT": "新增 HIT",
    "Added MISS": "新增 MISS",
    "Observation Increase Rate": "樣本增加比例",
    "Historical Hit Rate Change": "歷史命中率變化",
    "Percentage Points": "百分點",
    "Daily Observations": "每日觀察樣本",
    "Overlap Possible": "樣本可能重疊",
    "Leave-One-Out": "Leave-One-Out（假設不要求單一條件）",
    "Volume Threshold Sensitivity Analysis": "成交量門檻變化測試",
    "Threshold Sensitivity": "門檻變化測試",
    "Volume Ratio Threshold": "成交量比率門檻",
    "Current V1 Threshold": "目前 V1 門檻",
    "Observation Count Change vs V1": "相對目前 V1 的樣本變化",
    "Historical Hit Rate Change vs V1": "相對目前 V1 的歷史命中率變化",
    "Lower Threshold": "門檻越低",
    "Higher Threshold": "門檻越高",
    "Volume Threshold Robustness Analysis": "成交量門檻穩健性分析",
    "Per-Symbol Robustness": "逐股票穩健性",
    "Per-Year Robustness": "逐年度穩健性",
    "Overlap-Reduced Samples": "降低樣本重疊",
    "Original Daily Samples": "原始每日樣本",
    "Reduced-Overlap Samples": "降低重疊後樣本",
    "Difference vs Formal V1": "相對正式 V1 差異",
    "Historical Hit Rate Difference": "歷史命中率差異",
    "Observation Count Difference": "樣本數差異",
    "20 Trading-Bar Spacing": "20 個交易日間隔",
    "Expanded Symbol Universe Validation": "擴大股票樣本驗證",
    "Symbol Universe": "股票樣本範圍",
    "Coverage Audit": "資料覆蓋檢查",
    "Included in Research": "納入研究",
    "Excluded from Research": "未納入研究",
    "Insufficient Data": "資料不足",
    "Per-Symbol Result": "逐股票結果",
    "Cross-Symbol Consistency": "跨股票一致性",
    "Effective Year Count": "有效年度數",
    "Sample Concentration": "樣本集中程度",
    "Original Five Benchmark": "原始五檔基準",
    "Expanded Sample Result": "擴大樣本結果",
    "Formal V1": "正式 V1",
    "V1.1 Experimental": "V1.1 實驗版",
    "V1.1 Shadow Comparison": "V1.1 實驗比較",
    "Shared Observations": "共同樣本",
    "Incremental V1.1 Observations": "新增樣本",
    "Experimental Comparison": "實驗比較",
    "V1.1 Added Observations": "V1.1 新增樣本",
    "Research Evidence": "研究證據",
    "Observation Count Label": "觀察數",
    "Historical Hit Rate Difference PP": "差異（百分點）",
}

DIAGNOSTIC_CONDITION_LABELS = {
    "analysis_close_vs_sma_20": "股價高於 20 日均線",
    "sma_20_vs_sma_60": "20 日均線高於 60 日均線",
    "volume_ratio_20": "20 日成交量比率",
    "rsi_14": "RSI 14 日相對強弱指標",
    "distance_to_prior_60d_high": "距離前 60 日高點",
}

DIAGNOSTIC_BEGINNER_EXPLANATIONS = {
    "Historical Condition Diagnostics": (
        "用歷史資料統計每個有效交易日符合 V1 五項技術條件中的幾項，"
        "協助了解 V1 為什麼容易或不容易出現完整符合案例。"
    ),
    "Match Count Distribution": (
        "統計歷史上每個可評估樣本，一共符合 V1 五項條件中的幾項。"
    ),
    "Condition Pass Rate": (
        "觀察每一項 V1 條件在歷史資料中有多少比例能夠符合。"
    ),
    "Most Common Missing Condition": (
        "只分析已符合四項條件的歷史樣本，找出最常缺少的最後一項條件。"
    ),
    "Condition Combination": (
        "統計歷史上哪些 V1 條件最常一起成立。"
    ),
    "Historical Outcome Comparison": (
        "比較歷史上符合不同數量 V1 條件的樣本，之後是否在既定 20 個交易日研究期間內突破當時的前 60 日高點。"
    ),
    "Historical Hit Rate": (
        "達成研究目標的已解析歷史樣本 ÷ 全部已解析歷史樣本。這是歷史統計，不代表未來發生機率。"
    ),
    "4/5 Missing Condition Outcome": (
        "比較只差一項 V1 條件的歷史樣本，了解不同缺失條件與後續歷史結果的差異。"
    ),
    "V1 Historical Condition Dashboard": (
        "這裡會比較歷史上符合不同數量 V1 技術條件的樣本，"
        "觀察之後 20 個交易日內，是否突破當時的前 60 日高點。"
    ),
    "V1 Historical Condition Safety Note": (
        "這是歷史樣本的描述性統計，不是未來上漲機率，也不是買進建議。"
    ),
    "Single Condition Contribution Analysis": (
        "單一條件影響分析是在固定其他 V1 條件下，觀察取消某一條件要求後，"
        "歷史樣本數與歷史結果如何變化。"
    ),
    "Historical Hit Rate Change": (
        "歷史命中率變化使用百分點差，這是歷史樣本的描述性統計，"
        "不是未來發生機率，也不是買進建議。"
    ),
    "Single Condition Contribution Safety Note": (
        "較高的歷史命中率不代表該條件應被移除；較低的歷史命中率也不代表該條件一定有效。"
    ),
    "Daily Observation Overlap Note": (
        "目前每日觀察樣本可能具有重疊的未來觀察區間，不能解讀成相同數量的獨立交易。"
    ),
    "Volume Threshold Sensitivity Analysis": (
        "成交量門檻變化測試會固定其他四項 V1 條件，只改變成交量比率門檻，"
        "比較不同門檻下的歷史樣本數與歷史後續結果。"
    ),
    "Volume Threshold Sensitivity Baseline Note": (
        "1.20 是目前 V1 正式門檻。本測試不會修改正式 V1。"
    ),
    "Volume Threshold Sensitivity Safety Note": (
        "歷史命中率變高或變低，不代表該門檻是最佳設定。"
    ),
    "Volume Threshold Sensitivity Sample Note": (
        "較低門檻通常會增加樣本，但是否保留足夠篩選效果，需要進一步研究。"
    ),
    "Volume Threshold Robustness Analysis": (
        "穩健性不是只看全部股票加總，而是檢查結果在不同股票與不同年份是否仍有類似現象。"
    ),
    "Overlap-Reduced Samples": (
        "因為連續交易日可能共用相似的未來 20 個交易日，"
        "所以另外用至少相隔 20 個交易日的樣本做比較。"
    ),
    "Historical Hit Rate Difference": (
        "與正式 V1 的 1.20 門檻相比，歷史樣本中的百分點差異。"
    ),
    "Overlap-Reduced Independence Warning": (
        "降低樣本重疊不代表完全獨立樣本；它只降低同一股票連續 observation 的 future-window overlap。"
    ),
    "Expanded Symbol Universe Validation": (
        "這一階段不是調整 V1，而是增加更多股票，檢查前面看到的成交量門檻現象是否只出現在少數股票。"
    ),
}


def get_scan_mode_label(value: str) -> str:
    return SCAN_MODE_LABELS.get(value, value)


def get_source_label(value: str) -> str:
    return SOURCE_LABELS.get(value, value)


def get_scan_status_label(value: str) -> str:
    return SCAN_STATUS_LABELS.get(value, value)


def get_signal_status_label(value: str) -> str:
    return SIGNAL_STATUS_LABELS.get(value, value)


def get_signal_definition_label(value: str) -> str:
    return SIGNAL_DEFINITION_LABELS.get(value, value)


def get_outcome_definition_label(value: str) -> str:
    return OUTCOME_DEFINITION_LABELS.get(value, value)


def get_overlap_policy_label(value: str) -> str:
    return OVERLAP_POLICY_LABELS.get(value, value)


def get_outcome_status_label(value: str) -> str:
    return OUTCOME_STATUS_LABELS.get(value, value)


def get_frequency_label(value: str) -> str:
    return FREQUENCY_LABELS.get(value, value)


def get_sample_status_label(value: str) -> str:
    return SAMPLE_STATUS_LABELS.get(value, value)


def get_technical_metric_label(value: str | None) -> str:
    if value is None:
        return "N/A"
    return TECHNICAL_METRIC_LABELS.get(value, value)


def get_diagnostic_label(value: str) -> str:
    return DIAGNOSTIC_LABELS.get(value, value)


def get_diagnostic_condition_label(value: str) -> str:
    return DIAGNOSTIC_CONDITION_LABELS.get(value, value)


def get_diagnostic_beginner_explanation(value: str) -> str:
    return DIAGNOSTIC_BEGINNER_EXPLANATIONS.get(value, value)


def format_condition_labels(values: tuple[str, ...] | list[str]) -> str:
    return "、".join(get_technical_metric_label(value) for value in values) or "N/A"


def format_diagnostic_condition_labels(values: tuple[str, ...] | list[str]) -> str:
    return "、".join(get_diagnostic_condition_label(value) for value in values) or "N/A"
