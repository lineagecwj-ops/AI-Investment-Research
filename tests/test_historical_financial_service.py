import sys
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from datetime import date
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from historical_financial_service import build_historical_financial_series
from historical_financial_service import calculate_free_cash_flow
from historical_financial_service import calculate_margin
from historical_financial_service import fetch_historical_financials_from_yahoo
from historical_financial_service import find_statement_row
from historical_financial_service import get_historical_financials
from historical_financial_service import normalize_period_end
from historical_financial_service import optional_number
from historical_financial_service import statement_value
from database import save_historical_financials
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries


class HistoricalFinancialParsingTestCase(unittest.TestCase):

    def income_statement(self):
        return pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): [
                    1200.0,
                    600.0,
                    360.0,
                    240.0,
                    2.4,
                    2.3,
                ],
                pd.Timestamp("2024-12-31"): [
                    1000.0,
                    450.0,
                    250.0,
                    180.0,
                    1.8,
                    1.7,
                ],
            },
            index=[
                "Total Revenue",
                "Gross Profit",
                "Operating Income",
                "Net Income Common Stockholders",
                "Diluted EPS",
                "Basic EPS",
            ],
        )

    def cashflow_statement(self, include_direct_fcf=True):
        index = ["Operating Cash Flow", "Capital Expenditure"]
        data_2025 = [300.0, -80.0]
        data_2024 = [220.0, -70.0]
        if include_direct_fcf:
            index.append("Free Cash Flow")
            data_2025.append(210.0)
            data_2024.append(150.0)

        return pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): data_2025,
                pd.Timestamp("2024-12-31"): data_2024,
            },
            index=index,
        )

    def balance_sheet(self):
        return pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): [3000.0, 500.0, 1800.0, 700.0],
                pd.Timestamp("2024-12-31"): [2600.0, 450.0, 1600.0, 650.0],
            },
            index=[
                "Total Assets",
                "Total Debt",
                "Total Equity Gross Minority Interest",
                "Cash And Cash Equivalents",
            ],
        )

    def test_parses_income_cashflow_and_balance_sheet_oldest_to_newest(self):
        series = build_historical_financial_series(
            symbol="TEST",
            currency="USD",
            income_stmt=self.income_statement(),
            cashflow=self.cashflow_statement(),
            balance_sheet=self.balance_sheet(),
        )

        self.assertEqual([period.fiscal_year for period in series.periods], [2024, 2025])

        latest = series.periods[-1]
        self.assertEqual(latest.revenue, 1200.0)
        self.assertEqual(latest.net_income, 240.0)
        self.assertEqual(latest.eps, 2.4)
        self.assertEqual(latest.operating_cash_flow, 300.0)
        self.assertEqual(latest.capital_expenditure, -80.0)
        self.assertEqual(latest.free_cash_flow, 210.0)
        self.assertEqual(latest.total_debt, 500.0)

    def test_alias_priority_uses_first_matching_alias(self):
        statement = pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [111.0, 222.0]},
            index=["Net Income", "Net Income Common Stockholders"],
        )

        self.assertEqual(statement_value(statement, "net_income", date(2025, 12, 31)), 111.0)

    def test_eps_falls_back_to_basic_eps_when_diluted_missing(self):
        statement = pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [1.23]},
            index=["Basic EPS"],
        )

        self.assertEqual(statement_value(statement, "eps", date(2025, 12, 31)), 1.23)

    def test_missing_row_and_empty_dataframe_return_none_or_empty_series(self):
        statement = pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [100.0]},
            index=["Total Revenue"],
        )
        self.assertIsNone(statement_value(statement, "gross_profit", date(2025, 12, 31)))

        series = build_historical_financial_series(
            symbol="EMPTY",
            currency="USD",
            income_stmt=pd.DataFrame(),
            cashflow=pd.DataFrame(),
            balance_sheet=pd.DataFrame(),
        )
        self.assertEqual(series.periods, [])

    def test_nan_and_non_numeric_values_become_none(self):
        self.assertIsNone(optional_number(float("nan")))
        self.assertIsNone(optional_number(float("inf")))
        self.assertIsNone(optional_number("100"))
        self.assertIsNone(optional_number(True))

    def test_margin_calculation_safely_handles_missing_and_zero_revenue(self):
        self.assertEqual(calculate_margin(25.0, 100.0), 0.25)
        self.assertIsNone(calculate_margin(None, 100.0))
        self.assertIsNone(calculate_margin(25.0, None))
        self.assertIsNone(calculate_margin(25.0, 0.0))

    def test_margins_are_calculated_from_historical_statement_values(self):
        series = build_historical_financial_series(
            symbol="TEST",
            currency="USD",
            income_stmt=self.income_statement(),
            cashflow=self.cashflow_statement(),
            balance_sheet=self.balance_sheet(),
        )

        latest = series.periods[-1]
        self.assertEqual(latest.gross_margin, 0.5)
        self.assertEqual(latest.operating_margin, 0.3)
        self.assertEqual(latest.net_margin, 0.2)

    def test_direct_yahoo_free_cash_flow_is_used_when_available(self):
        series = build_historical_financial_series(
            symbol="TEST",
            currency="USD",
            income_stmt=self.income_statement(),
            cashflow=self.cashflow_statement(include_direct_fcf=True),
            balance_sheet=self.balance_sheet(),
        )

        self.assertEqual(series.periods[-1].free_cash_flow, 210.0)

    def test_derived_free_cash_flow_adds_negative_capex(self):
        self.assertEqual(calculate_free_cash_flow(300.0, -80.0), 220.0)

        series = build_historical_financial_series(
            symbol="TEST",
            currency="USD",
            income_stmt=self.income_statement(),
            cashflow=self.cashflow_statement(include_direct_fcf=False),
            balance_sheet=self.balance_sheet(),
        )

        self.assertEqual(series.periods[-1].free_cash_flow, 220.0)

    def test_missing_ocf_or_capex_cannot_derive_free_cash_flow(self):
        self.assertIsNone(calculate_free_cash_flow(None, -80.0))
        self.assertIsNone(calculate_free_cash_flow(300.0, None))

    def test_period_normalization_and_duplicate_period_handling(self):
        self.assertEqual(normalize_period_end(pd.Timestamp("2025-12-31")), date(2025, 12, 31))
        self.assertEqual(normalize_period_end("2025-12-31"), date(2025, 12, 31))

        statement = pd.DataFrame(
            [[100.0, 200.0]],
            columns=[pd.Timestamp("2025-12-31"), pd.Timestamp("2025-12-31")],
            index=["Total Revenue"],
        )
        series = build_historical_financial_series(
            symbol="DUP",
            currency="USD",
            income_stmt=statement,
        )

        self.assertEqual(len(series.periods), 1)

    def test_partial_data_keeps_period_when_cashflow_or_balance_sheet_missing(self):
        series = build_historical_financial_series(
            symbol="PARTIAL",
            currency="USD",
            income_stmt=self.income_statement(),
            cashflow=pd.DataFrame(),
            balance_sheet=pd.DataFrame(),
        )

        latest = series.periods[-1]
        self.assertEqual(latest.revenue, 1200.0)
        self.assertIsNone(latest.operating_cash_flow)
        self.assertIsNone(latest.total_assets)

    def test_period_with_no_modeled_values_is_filtered_out(self):
        statement = pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [123.0]},
            index=["Unmodeled Yahoo Row"],
        )

        series = build_historical_financial_series(
            symbol="EMPTY_PERIOD",
            currency="USD",
            income_stmt=statement,
        )

        self.assertEqual(series.periods, [])

    def test_find_statement_row_is_case_insensitive_and_priority_ordered(self):
        statement = pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [1.0, 2.0]},
            index=["basic eps", "Diluted EPS"],
        )

        self.assertEqual(
            find_statement_row(statement, ["Diluted EPS", "Basic EPS"]),
            "Diluted EPS",
        )


class HistoricalFinancialYahooFetchTestCase(unittest.TestCase):

    @patch("historical_financial_service.yf.Ticker")
    def test_fetch_from_yahoo_uses_annual_statement_objects(self, mock_ticker):
        yahoo_ticker = Mock()
        yahoo_ticker.info = {"currency": "USD", "financialCurrency": "USD"}
        yahoo_ticker.income_stmt = pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [100.0]},
            index=["Total Revenue"],
        )
        yahoo_ticker.cashflow = pd.DataFrame()
        yahoo_ticker.balance_sheet = pd.DataFrame()
        mock_ticker.return_value = yahoo_ticker

        series = fetch_historical_financials_from_yahoo("TEST")

        mock_ticker.assert_called_once_with("TEST")
        self.assertEqual(series.currency, "USD")
        self.assertEqual(series.periods[0].revenue, 100.0)


class HistoricalFinancialServiceCacheTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        self.now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    def tearDown(self):
        self.temp_dir.cleanup()

    def sample_series(self, revenue=100.0):
        return HistoricalFinancialSeries(
            symbol="TEST",
            currency="USD",
            periods=[
                HistoricalFinancialPeriod(
                    symbol="TEST",
                    period_end=date(2025, 12, 31),
                    fiscal_year=2025,
                    currency="USD",
                    revenue=revenue,
                )
            ],
        )

    def test_fresh_historical_cache_does_not_query_yahoo(self):
        save_historical_financials(
            self.sample_series(revenue=100.0),
            self.db_path,
            fetched_at=self.now,
        )

        with patch("database.utc_now", return_value=self.now + timedelta(days=1)):
            with patch(
                "historical_financial_service.fetch_historical_financials_from_yahoo"
            ) as mock_fetch:
                series = get_historical_financials("TEST", db_path=self.db_path)

        mock_fetch.assert_not_called()
        self.assertEqual(series.periods[0].revenue, 100.0)

    def test_expired_historical_cache_refreshes_from_yahoo(self):
        save_historical_financials(
            self.sample_series(revenue=100.0),
            self.db_path,
            fetched_at=self.now - timedelta(days=8),
        )
        refreshed = self.sample_series(revenue=200.0)

        with patch("database.utc_now", return_value=self.now):
            with patch(
                "historical_financial_service.fetch_historical_financials_from_yahoo",
                return_value=refreshed,
            ) as mock_fetch:
                series = get_historical_financials("TEST", db_path=self.db_path)

        mock_fetch.assert_called_once_with("TEST")
        self.assertEqual(series.periods[0].revenue, 200.0)

    def test_provider_failure_returns_stale_cache_when_available(self):
        save_historical_financials(
            self.sample_series(revenue=100.0),
            self.db_path,
            fetched_at=self.now - timedelta(days=8),
        )

        with patch("database.utc_now", return_value=self.now):
            with patch(
                "historical_financial_service.fetch_historical_financials_from_yahoo",
                side_effect=OSError("network"),
            ):
                with self.assertLogs(level="WARNING"):
                    series = get_historical_financials("TEST", db_path=self.db_path)

        self.assertTrue(series.is_stale)
        self.assertEqual(series.periods[0].revenue, 100.0)


if __name__ == "__main__":
    unittest.main()
