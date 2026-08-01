import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import Stock
from research_service import build_research_report
from research_service import build_research_next_steps
from research_service import build_risk_signals
from research_service import build_valuation_observations
from research_service import is_forward_pe_meaningfully_lower


class ResearchServiceTestCase(unittest.TestCase):

    def sample_stock(self):
        return Stock(
            symbol="NVDA",
            company_name="NVIDIA Corporation",
            currency="USD",
            current_price=150.0,
            market_cap=3_000_000_000_000,
            trailing_pe=50.0,
            forward_pe=35.0,
            trailing_eps=3.2,
            return_on_equity=0.45,
            company_summary="NVIDIA builds accelerated computing platforms.",
            gross_margin=0.74,
            operating_margin=0.62,
            net_margin=0.55,
            revenue_growth=0.2,
            earnings_growth=0.3,
            total_cash=50_000_000_000,
            total_debt=10_000_000_000,
            debt_to_equity=35.2,
            operating_cash_flow=60_000_000_000,
            free_cash_flow=45_000_000_000,
            price_to_book=20.0,
            fifty_two_week_high=200.0,
            fifty_two_week_low=100.0,
            fifty_day_average=145.0,
            two_hundred_day_average=140.0,
            sector="Technology",
            industry="Semiconductors",
        )

    def test_profitability_presentation_values_can_be_missing(self):
        stock = self.sample_stock()
        stock.gross_margin = None
        stock.net_margin = None

        report = build_research_report(stock)

        self.assertIn("Gross Margin（毛利率）", report.missing_critical_fields)
        self.assertIn("Net Margin（淨利率）", report.missing_critical_fields)
        self.assertIsNotNone(report)

    def test_growth_positive_negative_and_missing(self):
        positive_stock = self.sample_stock()
        self.assertFalse(
            any(signal.metric == "revenue_growth" for signal in build_risk_signals(positive_stock))
        )

        negative_stock = self.sample_stock()
        negative_stock.revenue_growth = -0.05
        negative_stock.earnings_growth = -0.1
        signals = build_risk_signals(negative_stock)

        self.assertIn("revenue_growth", [signal.metric for signal in signals])
        self.assertIn("earnings_growth", [signal.metric for signal in signals])

        missing_stock = self.sample_stock()
        missing_stock.revenue_growth = None
        report = build_research_report(missing_stock)
        self.assertIn("Revenue Growth（營收成長率）", report.missing_critical_fields)

    def test_valuation_observation_when_forward_pe_is_lower(self):
        stock = self.sample_stock()

        observations = build_valuation_observations(stock)

        self.assertTrue(is_forward_pe_meaningfully_lower(50.0, 35.0))
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].metric, "forward_pe")
        self.assertIn("可能反映市場預期未來盈餘較過去改善", observations[0].message)

    def test_missing_pe_does_not_create_valuation_observation(self):
        self.assertFalse(is_forward_pe_meaningfully_lower(None, 35.0))
        self.assertFalse(is_forward_pe_meaningfully_lower(50.0, None))

        stock = self.sample_stock()
        stock.forward_pe = None

        self.assertEqual(build_valuation_observations(stock), [])

    def test_market_position_normal_below_above_and_missing(self):
        stock = self.sample_stock()
        self.assertEqual(build_research_report(stock).fifty_two_week_position, 0.5)

        below_stock = self.sample_stock()
        below_stock.current_price = 90.0
        below_report = build_research_report(below_stock)
        self.assertLess(below_report.fifty_two_week_position, 0)
        self.assertIn("低於資料中的 52-week low", below_report.market_position_note)

        above_stock = self.sample_stock()
        above_stock.current_price = 210.0
        above_report = build_research_report(above_stock)
        self.assertGreater(above_report.fifty_two_week_position, 1)
        self.assertIn("高於資料中的 52-week high", above_report.market_position_note)

        missing_stock = self.sample_stock()
        missing_stock.fifty_two_week_high = None
        missing_report = build_research_report(missing_stock)
        self.assertIsNone(missing_report.fifty_two_week_position)

    def test_risk_signals_cover_required_conditions(self):
        stock = self.sample_stock()
        stock.revenue_growth = -0.01
        stock.earnings_growth = -0.02
        stock.free_cash_flow = -1
        stock.operating_cash_flow = -2
        stock.total_debt = 60_000_000_000
        stock.current_price = 130.0
        stock.two_hundred_day_average = 140.0

        signals = build_risk_signals(stock)
        metrics = [signal.metric for signal in signals]

        self.assertIn("revenue_growth", metrics)
        self.assertIn("earnings_growth", metrics)
        self.assertIn("free_cash_flow", metrics)
        self.assertIn("operating_cash_flow", metrics)
        self.assertIn("total_debt", metrics)
        self.assertIn("two_hundred_day_average", metrics)

    def test_risk_signal_for_significantly_above_52_week_range(self):
        stock = self.sample_stock()
        stock.current_price = 206.0

        signals = build_risk_signals(stock)

        self.assertIn("fifty_two_week_position", [signal.metric for signal in signals])

    def test_risk_signal_for_missing_data(self):
        stock = self.sample_stock()
        stock.company_summary = None

        signals = build_risk_signals(stock)

        self.assertIn("missing_fields", [signal.metric for signal in signals])

    def test_next_steps_are_deterministic_and_not_recommendations(self):
        stock = self.sample_stock()
        stock.revenue_growth = -0.05
        stock.free_cash_flow = -1

        first = build_research_next_steps(stock)
        second = build_research_next_steps(stock)
        combined_text = " ".join(step.question for step in first).lower()

        self.assertEqual(first, second)
        self.assertNotIn("buy", combined_text)
        self.assertNotIn("sell", combined_text)
        self.assertNotIn("hold", combined_text)
        self.assertNotIn("買", combined_text)
        self.assertNotIn("賣", combined_text)
        self.assertNotIn("持有", combined_text)

    def test_partial_stock_research_summary_still_builds(self):
        report = build_research_report(
            Stock(symbol="PARTIAL", company_name="Partial Inc.", current_price=10.0)
        )

        self.assertEqual(report.stock.symbol, "PARTIAL")
        self.assertIsNone(report.fifty_two_week_position)
        self.assertTrue(report.missing_critical_fields)
        self.assertTrue(report.risk_signals)
        self.assertTrue(report.next_steps)


if __name__ == "__main__":
    unittest.main()
