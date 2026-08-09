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
    "Match Count Distribution": "歷史條件命中分布",
    "Matched Conditions": "符合條件數",
    "Condition Pass Rate": "單一條件通過率",
    "Missing Condition": "未符合條件",
    "Most Common Missing Condition": "最常缺少的條件",
    "Condition Combination": "條件組合",
    "Evaluated Observations": "可評估歷史樣本",
    "Not Evaluable": "無法評估",
    "Observation Count": "歷史樣本數",
    "Share": "占可評估樣本比例",
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
