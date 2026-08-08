import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dashboard import build_comparison_rows
from dashboard import build_historical_chart_rows
from dashboard import build_historical_overview
from dashboard import build_historical_table_rows
from dashboard import build_historical_trend_display
from dashboard import format_currency_value
from dashboard import format_debt_to_equity
from dashboard import format_decimal
from dashboard import format_eps
from dashboard import format_chart_period_label
from dashboard import format_integer
from dashboard import format_industry
from dashboard import format_market_cap
from dashboard import format_missing
from dashboard import format_na
from dashboard import format_period_end
from dashboard import format_percentage
from dashboard import format_price
from dashboard import format_ratio
from dashboard import format_sector
from dashboard import format_yoy
from dashboard import has_enough_historical_data
from dashboard import historical_cache_status_text
from dashboard import historical_metric_help
from dashboard import historical_stale_warning_text
from dashboard import indicator_help
from dashboard import indicator_label
from dashboard import INDUSTRY_TRANSLATIONS
from dashboard import INDICATOR_HELP_TEXT
from dashboard import INDICATOR_LABELS
from dashboard import query_stock_batch
from dashboard import SECTOR_TRANSLATIONS
from dashboard import stock_display_data
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries
from models import Stock
from stock_service import StockDataError


class DashboardFormattingTestCase(unittest.TestCase):

    def sample_stock(self):
        return Stock(
            symbol="NVDA",
            company_name="NVIDIA Corporation",
            current_price=200.756,
            currency="USD",
            market_cap=4879000000000,
            trailing_pe=57.681,
            forward_pe=44.3,
            trailing_eps=3.485,
            return_on_equity=0.285,
            sector="Technology",
            industry="Semiconductors",
        )

    def test_na_formatting(self):
        self.assertEqual(format_na(None), "N/A")
        self.assertEqual(format_na(""), "N/A")
        self.assertEqual(format_na("NVDA"), "NVDA")

    def test_market_cap_formatting(self):
        self.assertEqual(format_market_cap(2_500_000_000, "USD"), "USD 2.50B")
        self.assertEqual(format_market_cap(5_674_171_891_712, "TWD"), "TWD 5.67T")
        self.assertEqual(format_market_cap(850_200_000, None), "850.20M")
        self.assertEqual(format_market_cap(None, "USD"), "N/A")

    def test_currency_value_formatting_keeps_currency_context(self):
        self.assertEqual(format_currency_value(1_250_000_000_000, "TWD"), "TWD 1.25T")
        self.assertEqual(format_currency_value(85_400_000_000, "USD"), "USD 85.40B")
        self.assertEqual(format_currency_value(None, "USD"), "N/A")

    def test_integer_formatting_remains_available(self):
        self.assertEqual(format_integer(2500000000), "2,500,000,000")
        self.assertEqual(format_integer(None), "N/A")

    def test_decimal_formatting(self):
        self.assertEqual(format_decimal(25.345), "25.34")
        self.assertEqual(format_decimal(None), "N/A")

    def test_price_and_ratio_formatting(self):
        self.assertEqual(format_price(123.456, "USD"), "USD 123.46")
        self.assertEqual(format_price(None, "USD"), "N/A")
        self.assertEqual(format_ratio(35.2), "35.20")
        self.assertEqual(format_ratio(None), "N/A")

    def test_debt_to_equity_display_uses_yahoo_percent_scale(self):
        self.assertEqual(format_debt_to_equity(15.174), "15.17%")
        self.assertEqual(format_debt_to_equity(3.952), "3.95%")
        self.assertEqual(format_debt_to_equity(None), "N/A")
        self.assertNotEqual(format_debt_to_equity(15.174), "1,517.40%")

    def test_research_page_uses_debt_to_equity_formatter(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("from dashboard import format_debt_to_equity", app_source)
        self.assertIn(
            '(indicator_label("debt_to_equity"), format_debt_to_equity(stock.debt_to_equity), indicator_help("debt_to_equity"))',
            app_source,
        )

    def test_roe_percentage_formatting(self):
        self.assertEqual(format_percentage(0.285), "28.50%")
        self.assertEqual(format_percentage(None), "N/A")

    def test_historical_formatters_use_friendly_na_and_period_end(self):
        self.assertEqual(format_missing(None), "N/A")
        self.assertEqual(format_eps(12.345), "12.35")
        self.assertEqual(format_eps(None), "N/A")
        self.assertEqual(format_yoy(0.125), "12.50%")
        self.assertEqual(format_yoy(None), "N/A")
        self.assertEqual(format_period_end(date(2026, 1, 31)), "FY ending 2026-01-31")
        self.assertEqual(format_period_end(date(2025, 9, 30)), "FY ending 2025-09-30")
        self.assertEqual(format_chart_period_label(date(2026, 1, 31), 2026), "FY 2026")
        self.assertEqual(format_chart_period_label(date(2025, 9, 30), 2025), "FY 2025")

    def test_historical_page_renders_interpretation_before_full_table(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("from historical_research_service import build_historical_research_report", app_source)
        self.assertIn("def render_historical_interpretation(series)", app_source)
        self.assertLess(
            app_source.index("render_historical_interpretation(series)"),
            app_source.index('st.markdown("### Historical Table（完整年度資料）")'),
        )

    def test_historical_cases_tab_uses_explicit_session_result(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn('"Historical Cases"', app_source)
        self.assertIn("def render_historical_cases() -> None:", app_source)
        self.assertIn('st.session_state.setdefault("historical_case_result", None)', app_source)
        self.assertIn('submitted = st.form_submit_button("建立歷史案例")', app_source)
        self.assertIn('if submitted:', app_source)
        self.assertIn('if st.button("清除案例結果"):', app_source)
        self.assertIn("build_historical_case_result(", app_source)

    def test_historical_cases_tab_does_not_use_scanner_ranking_language(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        case_page_source = app_source[
            app_source.index("def render_historical_cases() -> None:"):
            app_source.index("def read_watchlist_for_ui(")
        ]

        self.assertNotIn("Research Priority", case_page_source)
        self.assertNotIn("Buy Point", case_page_source)
        self.assertNotIn("Sell Point", case_page_source)

    def test_swing_research_tab_uses_explicit_session_result(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        universe_source = (SRC_PATH / "universe_dashboard.py").read_text(encoding="utf-8")

        self.assertIn('"Swing Research"', app_source)
        self.assertIn('"Historical Cases"', app_source)
        self.assertIn("def render_swing_research() -> None:", app_source)
        self.assertIn('st.session_state.setdefault("swing_research_result", None)', app_source)
        self.assertIn('st.session_state.setdefault("swing_research_config_fingerprint", None)', app_source)
        self.assertIn('st.session_state.setdefault("swing_research_last_error", None)', app_source)
        self.assertIn('st.session_state.setdefault("swing_research_price_series_by_symbol", {})', app_source)
        self.assertIn('st.session_state.setdefault("swing_research_source_context", None)', app_source)
        self.assertIn('"執行波段掃描"', app_source)
        self.assertIn('"執行 Replay Scan"', app_source)
        self.assertIn('"執行 Walk-Forward Replay"', app_source)
        self.assertIn('if submitted:', app_source)
        self.assertIn('if st.button("清除掃描結果"):', app_source)
        self.assertIn("build_swing_research_scan_result(", app_source)
        self.assertIn("build_swing_research_replay_result(", app_source)
        self.assertIn("build_swing_research_walk_forward_result(", app_source)
        self.assertIn('st.session_state.setdefault("swing_research_result_mode", None)', app_source)
        self.assertIn('st.session_state.setdefault("swing_research_replay_date", None)', app_source)
        self.assertIn("Symbol Source", app_source)
        self.assertIn("Historical Replay", app_source)
        self.assertIn("Walk-Forward Replay", app_source)
        self.assertIn("Replay Date", app_source)
        self.assertIn("Frequency", app_source)
        self.assertIn("Manual Input", universe_source)
        self.assertIn("Saved Universe", universe_source)

    def test_universe_management_tab_exists(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        universe_source = (SRC_PATH / "universe_dashboard.py").read_text(encoding="utf-8")

        self.assertIn('"Universes"', app_source)
        self.assertIn("def render_universe_management() -> None:", app_source)
        self.assertIn("建立股票池", app_source)
        self.assertIn("儲存變更", app_source)
        self.assertIn("刪除股票池", app_source)
        self.assertIn("我確認要刪除此股票池", app_source)
        self.assertIn("股票池只是研究標的集合，不代表投資建議或預測。", universe_source)

    def test_swing_research_wording_preserves_research_semantics(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        helper_source = (SRC_PATH / "swing_research_dashboard.py").read_text(encoding="utf-8")
        universe_source = (SRC_PATH / "universe_dashboard.py").read_text(encoding="utf-8")
        swing_page_source = app_source[
            app_source.index("def render_swing_research() -> None:"):
            app_source.index("def build_historical_case_result(")
        ]

        self.assertIn("Historical Hit Rate", swing_page_source)
        self.assertIn("Historical Hit Rate (As Of)", swing_page_source)
        self.assertIn("Post-Replay Outcome", swing_page_source)
        self.assertIn("Replay Periods", helper_source)
        self.assertIn("Candidate Occurrences", helper_source)
        self.assertIn("Replay Outcome Case Chart", swing_page_source)
        self.assertIn("signal date 之後資料只用於歷史事後驗證", swing_page_source)
        self.assertIn("Resolved Samples", swing_page_source)
        self.assertIn("Research Priority", swing_page_source)
        self.assertIn("swing_research_price_series_by_symbol", swing_page_source)
        combined_source = swing_page_source + helper_source + universe_source
        self.assertNotIn("Prediction Result", combined_source)
        self.assertNotIn("Replay Probability", combined_source)
        self.assertNotIn("Walk-Forward Probability", combined_source)
        self.assertNotIn("Prediction Accuracy", combined_source)
        self.assertNotIn("Win Rate", combined_source)
        self.assertNotIn("Buy Rank", combined_source)
        self.assertNotIn("Opportunity Score", combined_source)
        self.assertNotIn("上漲機率", combined_source)
        self.assertNotIn("推薦池", combined_source)
        self.assertNotIn("高勝率", combined_source)

    def test_oos_validation_dashboard_ui_exists_and_preserves_semantics(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        helper_source = (SRC_PATH / "oos_validation_dashboard.py").read_text(encoding="utf-8")
        oos_page_source = app_source[
            app_source.index("def render_swing_research() -> None:"):
            app_source.index("def render_swing_research_result(")
        ]

        self.assertIn("Out-of-Sample Validation", oos_page_source)
        self.assertIn("Development", oos_page_source)
        self.assertIn("Validation", oos_page_source)
        self.assertIn("Holdout", oos_page_source)
        self.assertIn("Historical Hit Rate", oos_page_source)
        self.assertIn("Resolved n", oos_page_source)
        self.assertIn("Candidate Period Share", oos_page_source)
        self.assertIn("Research Specification Fingerprint", oos_page_source)
        self.assertIn('st.session_state.setdefault("oos_validation_result", None)', app_source)
        self.assertIn('st.session_state.setdefault("oos_validation_fingerprint", None)', app_source)
        self.assertIn('st.session_state.setdefault("oos_validation_last_error", None)', app_source)
        self.assertIn('st.session_state.setdefault("oos_validation_source_context", None)', app_source)
        self.assertIn('"執行樣本外驗證"', oos_page_source)
        self.assertIn('"清除樣本外驗證結果"', oos_page_source)

        combined_source = oos_page_source + helper_source
        self.assertNotIn("Validation Score", combined_source)
        self.assertNotIn("Prediction Accuracy", combined_source)
        self.assertNotIn("Win Rate", combined_source)
        self.assertNotIn("Future Probability", combined_source)
        self.assertNotIn("Buy ", combined_source)
        self.assertNotIn("Sell ", combined_source)

    def test_known_sector_translation(self):
        self.assertEqual(format_sector("Technology"), "Technology（科技）")
        self.assertEqual(format_sector("Financial Services"), "Financial Services（金融服務）")

    def test_known_industry_translation(self):
        self.assertEqual(format_industry("Semiconductors"), "Semiconductors（半導體）")

    def test_unknown_classification_falls_back_to_english(self):
        self.assertEqual(format_sector("Specialty Business Services"), "Specialty Business Services")
        self.assertEqual(format_industry("Unknown Industry"), "Unknown Industry")

    def test_missing_classification_formats_as_na(self):
        self.assertEqual(format_sector(None), "N/A")
        self.assertEqual(format_industry(None), "N/A")

    def test_translation_mappings_cover_required_values(self):
        required_sectors = [
            "Technology",
            "Healthcare",
            "Financial Services",
            "Consumer Cyclical",
            "Consumer Defensive",
            "Industrials",
            "Energy",
            "Basic Materials",
            "Communication Services",
            "Real Estate",
            "Utilities",
        ]

        for sector in required_sectors:
            self.assertIn(sector, SECTOR_TRANSLATIONS)

        self.assertIn("Semiconductors", INDUSTRY_TRANSLATIONS)

    def test_stock_display_data_formats_all_fields(self):
        with patch("dashboard.get_display_company_name", return_value="NVIDIA Corporation") as mock_name:
            display_data = stock_display_data(self.sample_stock())

        self.assertEqual(display_data["Company Name"], "NVIDIA Corporation")
        mock_name.assert_called_once()
        self.assertEqual(display_data["Symbol"], "NVDA")
        self.assertEqual(display_data["Current Price"], "200.76")
        self.assertEqual(display_data["Market Cap"], "USD 4.88T")
        self.assertEqual(display_data["Trailing PE"], "57.68")
        self.assertEqual(display_data["EPS"], "3.48")
        self.assertEqual(display_data["ROE"], "28.50%")
        self.assertEqual(display_data["Sector"], "Technology（科技）")
        self.assertEqual(display_data["Industry"], "Semiconductors（半導體）")

    def test_bilingual_indicator_labels(self):
        self.assertEqual(indicator_label("current_price"), "Current Price（目前股價）")
        self.assertEqual(indicator_label("market_cap"), "Market Cap（市值）")
        self.assertEqual(indicator_label("return_on_equity"), "ROE（股東權益報酬率）")
        self.assertEqual(indicator_label("trailing_pe"), "Trailing P/E（歷史本益比）")
        self.assertEqual(indicator_label("forward_pe"), "Forward P/E（預估本益比）")

    def test_required_help_text_registry(self):
        required_indicators = [
            "current_price",
            "market_cap",
            "trailing_pe",
            "forward_pe",
            "trailing_eps",
            "return_on_equity",
            "sector",
            "industry",
        ]

        for indicator in required_indicators:
            self.assertIn(indicator, INDICATOR_LABELS)
            self.assertIn(indicator, INDICATOR_HELP_TEXT)
            self.assertTrue(indicator_help(indicator))

    def test_comparison_rows_use_display_ready_values(self):
        with patch("dashboard.get_display_company_name", return_value="NVIDIA Corporation"):
            rows = build_comparison_rows([self.sample_stock()])

        self.assertEqual(
            rows,
            [
                {
                    "Symbol（股票代號）": "NVDA",
                    "Company Name（公司名稱）": "NVIDIA Corporation",
                    "Current Price（目前股價）": "200.76",
                    "Currency（交易幣別）": "USD",
                    "Market Cap（市值）": "USD 4.88T",
                    "Trailing P/E（歷史本益比）": "57.68",
                    "Forward P/E（預估本益比）": "44.30",
                    "EPS（每股盈餘）": "3.48",
                    "ROE（股東權益報酬率）": "28.50%",
                    "Sector（產業類別）": "Technology（科技）",
                    "Industry（細分產業）": "Semiconductors（半導體）",
                }
            ],
        )

    def test_dashboard_uses_localized_name_helper(self):
        stock = Stock(
            symbol="2330.TW",
            company_name="Taiwan Semiconductor Manufacturing Company Limited",
        )

        with patch("dashboard.get_display_company_name", return_value="台積電") as mock_name:
            display_data = stock_display_data(stock)

        mock_name.assert_called_once_with(stock)
        self.assertEqual(display_data["Company Name"], "台積電")

    def test_comparison_uses_localized_name_helper(self):
        stock = Stock(
            symbol="2330.TW",
            company_name="Taiwan Semiconductor Manufacturing Company Limited",
        )

        with patch("dashboard.get_display_company_name", return_value="台積電") as mock_name:
            rows = build_comparison_rows([stock])

        mock_name.assert_called_once_with(stock)
        self.assertEqual(rows[0]["Company Name（公司名稱）"], "台積電")


class DashboardQueryTestCase(unittest.TestCase):

    def test_partial_query_failure_keeps_successful_stocks(self):
        nvda_stock = Stock(symbol="NVDA", company_name="NVIDIA Corporation")
        aapl_stock = Stock(symbol="AAPL", company_name="Apple Inc.")

        def fake_lookup(symbol):
            if symbol == "INVALID":
                raise StockDataError("Yahoo Finance 回傳資料缺少目前價格。")
            if symbol == "NVDA":
                return nvda_stock
            return aapl_stock

        stocks, failures = query_stock_batch(["NVDA", "INVALID", "AAPL"], fake_lookup)

        self.assertEqual(stocks, [nvda_stock, aapl_stock])
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].symbol, "INVALID")
        self.assertEqual(failures[0].message, "Yahoo Finance 回傳資料缺少目前價格。")


class HistoricalTrendDashboardTestCase(unittest.TestCase):

    def sample_series(self, is_stale=False):
        return HistoricalFinancialSeries(
            symbol="TEST",
            currency="USD",
            fetched_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
            is_stale=is_stale,
            periods=[
                HistoricalFinancialPeriod(
                    symbol="TEST",
                    period_end=date(2022, 12, 31),
                    period_year=2022,
                    currency="USD",
                    revenue=100.0,
                    gross_profit=40.0,
                    operating_income=25.0,
                    net_income=20.0,
                    eps=1.0,
                    gross_margin=0.4,
                    operating_margin=0.25,
                    net_margin=0.2,
                    operating_cash_flow=30.0,
                    capital_expenditure=-10.0,
                    free_cash_flow=20.0,
                    total_assets=500.0,
                    total_debt=80.0,
                    total_equity=300.0,
                    cash_and_cash_equivalents=50.0,
                ),
                HistoricalFinancialPeriod(
                    symbol="TEST",
                    period_end=date(2024, 12, 31),
                    period_year=2024,
                    currency="USD",
                    revenue=140.0,
                    gross_profit=70.0,
                    operating_income=35.0,
                    net_income=28.0,
                    eps=1.4,
                    gross_margin=0.5,
                    operating_margin=0.25,
                    net_margin=0.2,
                    operating_cash_flow=42.0,
                    capital_expenditure=-12.0,
                    free_cash_flow=30.0,
                    total_assets=650.0,
                    total_debt=None,
                    total_equity=360.0,
                    cash_and_cash_equivalents=None,
                ),
                HistoricalFinancialPeriod(
                    symbol="TEST",
                    period_end=date(2025, 12, 31),
                    period_year=2025,
                    currency="USD",
                    revenue=210.0,
                    gross_profit=None,
                    operating_income=52.5,
                    net_income=42.0,
                    eps=None,
                    gross_margin=None,
                    operating_margin=0.25,
                    net_margin=0.2,
                    operating_cash_flow=60.0,
                    capital_expenditure=-15.0,
                    free_cash_flow=45.0,
                    total_assets=800.0,
                    total_debt=110.0,
                    total_equity=420.0,
                    cash_and_cash_equivalents=90.0,
                ),
            ],
        )

    def test_historical_overview_includes_range_currency_and_cache_status(self):
        stock = Stock(symbol="TEST", company_name="Test Co", currency="USD")

        with patch("dashboard.get_display_company_name", return_value="Test Co"):
            overview = build_historical_overview(self.sample_series(), stock)

        self.assertEqual(overview.symbol, "TEST")
        self.assertEqual(overview.company_name, "Test Co")
        self.assertEqual(overview.currency, "USD")
        self.assertEqual(overview.annual_periods, "2022–2025")
        self.assertEqual(overview.available_periods, "3")
        self.assertIn("FY ending 2022-12-31", overview.period_range)
        self.assertIn("7 天內快取", overview.cache_status)
        self.assertIsNone(overview.stale_warning)

    def test_stale_cache_presentation_uses_warning_without_traceback(self):
        series = self.sample_series(is_stale=True)

        self.assertEqual(historical_cache_status_text(series), "歷史資料：顯示本機較舊快取")
        self.assertEqual(
            historical_stale_warning_text(series),
            "目前 Yahoo Finance 查詢失敗，顯示本機較舊的歷史資料。",
        )
        self.assertNotIn("Traceback", historical_stale_warning_text(series))

    def test_revenue_values_and_yoy_keep_gap_as_na(self):
        display = build_historical_trend_display(self.sample_series())

        self.assertEqual(display.revenue_rows[0]["Revenue"], "USD 100")
        self.assertEqual(display.revenue_rows[0]["YoY"], "N/A")
        self.assertEqual(display.revenue_rows[1]["YoY"], "N/A")
        self.assertEqual(display.revenue_rows[2]["YoY"], "50.00%")

    def test_eps_missing_existing_and_yoy_presentation(self):
        display = build_historical_trend_display(self.sample_series())

        self.assertEqual(display.earnings_rows[0]["EPS"], "1.00")
        self.assertEqual(display.earnings_rows[1]["EPS YoY"], "N/A")
        self.assertEqual(display.earnings_rows[2]["EPS"], "N/A")
        self.assertIn("Yahoo Finance 目前未提供此期 EPS", display.missing_data_notes[0])

    def test_margin_percentage_partial_data(self):
        display = build_historical_trend_display(self.sample_series())

        self.assertEqual(display.margin_rows[0]["Gross Margin"], "40.00%")
        self.assertEqual(display.margin_rows[1]["Operating Margin"], "25.00%")
        self.assertEqual(display.margin_rows[2]["Gross Margin"], "N/A")

    def test_cash_flow_displays_negative_capex_and_explanation_exists(self):
        display = build_historical_trend_display(self.sample_series())

        self.assertEqual(display.cash_flow_rows[0]["Operating Cash Flow"], "USD 30")
        self.assertEqual(display.cash_flow_rows[0]["Capital Expenditure"], "USD -10")
        self.assertEqual(display.cash_flow_rows[0]["Free Cash Flow"], "USD 20")
        self.assertIn("負數表示 cash outflow", historical_metric_help("capital_expenditure"))

    def test_financial_position_currency_and_missing_values(self):
        display = build_historical_trend_display(self.sample_series())

        self.assertEqual(display.financial_position_rows[1]["Total Debt"], "N/A")
        self.assertEqual(display.financial_position_rows[1]["Cash"], "N/A")
        self.assertEqual(display.financial_position_rows[2]["Total Equity"], "USD 420")

    def test_period_semantics_for_nvda_and_aapl_like_dates(self):
        nvda = HistoricalFinancialSeries(
            symbol="NVDA",
            currency="USD",
            periods=[
                HistoricalFinancialPeriod(
                    symbol="NVDA",
                    period_end=date(2026, 1, 31),
                    period_year=2026,
                    revenue=1.0,
                )
            ],
        )
        aapl = HistoricalFinancialSeries(
            symbol="AAPL",
            currency="USD",
            periods=[
                HistoricalFinancialPeriod(
                    symbol="AAPL",
                    period_end=date(2025, 9, 30),
                    period_year=2025,
                    revenue=1.0,
                )
            ],
        )

        self.assertEqual(build_historical_table_rows(nvda)[0]["Period End"], "FY ending 2026-01-31")
        self.assertEqual(build_historical_table_rows(aapl)[0]["Period End"], "FY ending 2025-09-30")

    def test_full_table_uses_oldest_to_newest_and_no_nan_visible(self):
        rows = build_historical_table_rows(self.sample_series())

        self.assertEqual(
            [row["Period End"] for row in rows],
            [
                "FY ending 2022-12-31",
                "FY ending 2024-12-31",
                "FY ending 2025-12-31",
            ],
        )
        all_values = [value for row in rows for value in row.values()]
        self.assertNotIn("None", all_values)
        self.assertNotIn("nan", [value.lower() for value in all_values])
        self.assertIn("N/A", all_values)

    def test_chart_rows_use_compact_period_labels_and_keep_exact_period_end(self):
        rows = build_historical_chart_rows(self.sample_series(), ["revenue", "eps"])

        self.assertEqual(rows[0]["Period"], "FY 2022")
        self.assertEqual(rows[0]["Period End"], "FY ending 2022-12-31")
        self.assertEqual(rows[2]["Period"], "FY 2025")
        self.assertEqual(rows[2]["Period End"], "FY ending 2025-12-31")

    def test_chart_rows_keep_raw_numeric_values_and_missing_eps(self):
        rows = build_historical_chart_rows(self.sample_series(), ["revenue", "eps"])

        self.assertEqual(rows[0]["Revenue"], 100.0)
        self.assertEqual(rows[2]["Revenue"], 210.0)
        self.assertIsNone(rows[2]["EPS"])
        self.assertNotEqual(rows[2]["Revenue"], "USD 210")
        self.assertNotEqual(rows[2]["EPS"], 0)

    def test_tables_keep_exact_fy_ending_labels(self):
        display = build_historical_trend_display(self.sample_series())

        self.assertEqual(display.revenue_rows[0]["Period End"], "FY ending 2022-12-31")
        self.assertEqual(display.historical_table_rows[2]["Period End"], "FY ending 2025-12-31")

    def test_historical_renderer_uses_separate_earnings_charts_and_formats_axes(self):
        app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn('st.markdown("#### Net Income Trend")', app_source)
        self.assertIn('render_historical_chart(series, ["net_income"], value_format="currency")', app_source)
        self.assertIn('st.markdown("#### EPS Trend")', app_source)
        self.assertIn('render_historical_chart(series, ["eps"], value_format="eps")', app_source)
        self.assertNotIn('render_historical_chart(series, ["net_income", "eps"])', app_source)
        self.assertIn('value_format="percentage"', app_source)
        self.assertIn('alt.Axis(format=".0%", title="Percentage")', app_source)
        self.assertIn('alt.Axis(format="~s"', app_source)
        self.assertIn('axis=alt.Axis(labelAngle=0)', app_source)

    def test_insufficient_series_detection(self):
        series = HistoricalFinancialSeries(
            symbol="PARTIAL",
            periods=[
                HistoricalFinancialPeriod(
                    symbol="PARTIAL",
                    period_end=date(2025, 12, 31),
                    period_year=2025,
                    revenue=100.0,
                )
            ],
        )

        self.assertFalse(has_enough_historical_data(series, ["revenue"]))
        self.assertIn(
            "目前可取得的歷史資料不足",
            build_historical_trend_display(HistoricalFinancialSeries(symbol="EMPTY")).missing_data_notes[0],
        )


if __name__ == "__main__":
    unittest.main()
