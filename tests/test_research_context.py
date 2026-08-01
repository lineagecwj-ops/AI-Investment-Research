import json
import math
import re
import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from historical_research_service import build_historical_research_report
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries
from models import Stock
from research_context import EvidenceItem
from research_context import ResearchContextError
from research_context import build_research_context
from research_context import ensure_no_non_finite
from research_context import validate_evidence
from research_service import build_research_report


GENERATED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


class ResearchContextTestCase(unittest.TestCase):

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

    def partial_stock(self):
        return Stock(
            symbol="PARTIAL",
            company_name="Partial Inc.",
            currency="USD",
            current_price=10.0,
            fifty_two_week_high=20.0,
        )

    def sample_series(self):
        return HistoricalFinancialSeries(
            symbol="NVDA",
            currency="USD",
            fetched_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            periods=[
                self.period(
                    2024,
                    revenue=100.0,
                    gross_profit=75.0,
                    operating_income=60.0,
                    net_income=50.0,
                    eps=2.5,
                    gross_margin=0.75,
                    operating_margin=0.6,
                    net_margin=0.5,
                    operating_cash_flow=55.0,
                    capital_expenditure=-10.0,
                    free_cash_flow=45.0,
                    total_assets=200.0,
                    total_debt=20.0,
                    total_equity=150.0,
                    cash=70.0,
                    month=1,
                    day=31,
                ),
                self.period(
                    2025,
                    revenue=140.0,
                    gross_profit=100.0,
                    operating_income=80.0,
                    net_income=65.0,
                    eps=3.0,
                    gross_margin=0.714,
                    operating_margin=0.571,
                    net_margin=0.464,
                    operating_cash_flow=75.0,
                    capital_expenditure=-15.0,
                    free_cash_flow=60.0,
                    total_assets=260.0,
                    total_debt=30.0,
                    total_equity=190.0,
                    cash=90.0,
                    month=1,
                    day=31,
                ),
            ],
        )

    def recovery_series(self):
        return HistoricalFinancialSeries(
            symbol="NVDA",
            currency="USD",
            periods=[
                self.period(2022, revenue=100.0),
                self.period(2023, revenue=79.0),
                self.period(2024, revenue=96.704),
                self.period(2025, revenue=108.617),
            ],
        )

    def eps_missing_series(self):
        return HistoricalFinancialSeries(
            symbol="NVDA",
            currency="USD",
            periods=[
                self.period(2024, revenue=100.0, eps=2.5),
                self.period(2025, revenue=120.0, eps=None),
            ],
        )

    def period(
        self,
        year,
        revenue=None,
        gross_profit=None,
        operating_income=None,
        net_income=None,
        eps=None,
        gross_margin=None,
        operating_margin=None,
        net_margin=None,
        operating_cash_flow=None,
        capital_expenditure=None,
        free_cash_flow=None,
        total_assets=None,
        total_debt=None,
        total_equity=None,
        cash=None,
        month=12,
        day=31,
    ):
        return HistoricalFinancialPeriod(
            symbol="NVDA",
            period_end=date(year, month, day),
            period_year=year,
            currency="USD",
            revenue=revenue,
            gross_profit=gross_profit,
            operating_income=operating_income,
            net_income=net_income,
            eps=eps,
            gross_margin=gross_margin,
            operating_margin=operating_margin,
            net_margin=net_margin,
            operating_cash_flow=operating_cash_flow,
            capital_expenditure=capital_expenditure,
            free_cash_flow=free_cash_flow,
            total_assets=total_assets,
            total_debt=total_debt,
            total_equity=total_equity,
            cash_and_cash_equivalents=cash,
        )

    def build_context(self, stock=None, series=None, historical_report=None, generated_at=GENERATED_AT):
        resolved_stock = stock or self.sample_stock()
        research_report = build_research_report(resolved_stock)
        resolved_historical_report = historical_report
        if series is not None and resolved_historical_report is None:
            resolved_historical_report = build_historical_research_report(series)
        return build_research_context(
            stock=resolved_stock,
            research_report=research_report,
            historical_series=series,
            historical_research_report=resolved_historical_report,
            display_name=resolved_stock.company_name,
            generated_at=generated_at,
        )

    def evidence_by_id(self, context):
        return {item.id: item for item in context.evidence}

    def missing_by_id(self, context):
        return {item.id: item for item in context.missing_data}

    def test_minimal_context_without_historical_series_is_valid(self):
        context = self.build_context()

        self.assertEqual(context.symbol, "NVDA")
        self.assertIsNone(context.historical_financials)
        self.assertIsNone(context.historical_research)
        self.assertIn("context:no_historical_series", [item.id for item in context.limitations])
        self.assertIn("missing:historical:series", [item.id for item in context.missing_data])

    def test_full_context_groups_raw_values_and_historical_periods(self):
        context = self.build_context(series=self.sample_series())

        self.assertEqual(context.current_snapshot.market.current_price, 150.0)
        self.assertEqual(context.current_snapshot.profitability.return_on_equity, 0.45)
        self.assertEqual(context.current_snapshot.growth.revenue_growth, 0.2)
        self.assertEqual(context.current_snapshot.financial_health.total_cash, 50_000_000_000)
        self.assertEqual(context.current_snapshot.valuation.trailing_pe, 50.0)
        self.assertEqual(context.historical_financials.fetched_at, datetime(2026, 8, 1, 9, 0, tzinfo=UTC))
        self.assertEqual(context.historical_financials.periods[0].period_end, date(2024, 1, 31))

    def test_partial_context_records_missing_current_fields(self):
        stock = self.partial_stock()
        context = self.build_context(stock=stock)

        missing_ids = {item.id for item in context.missing_data}
        self.assertIn("missing:current:return_on_equity", missing_ids)
        self.assertIn("missing:current:fifty_two_week_low", missing_ids)
        self.assertIn("context:missing_critical_research_fields", [item.id for item in context.limitations])

    def test_pure_builder_requires_reports_and_does_not_accept_resolver(self):
        stock = self.sample_stock()
        report = build_research_report(stock)

        with self.assertRaises(TypeError):
            build_research_context(stock=stock)

        with self.assertRaises(TypeError):
            build_research_context(
                stock=stock,
                research_report=report,
                display_name_resolver=lambda _stock: "resolver",
            )

    def test_symbol_mismatch_validation(self):
        stock = self.sample_stock()
        report_stock = self.sample_stock()
        report_stock.symbol = "AAPL"
        report = build_research_report(report_stock)

        with self.assertRaisesRegex(ResearchContextError, "Stock symbol mismatch"):
            build_research_context(stock=stock, research_report=report, generated_at=GENERATED_AT)

    def test_historical_series_symbol_mismatch_validation(self):
        stock = self.sample_stock()
        report = build_research_report(stock)
        series = self.sample_series()
        series.symbol = "AAPL"

        with self.assertRaisesRegex(ResearchContextError, "Historical series symbol mismatch"):
            build_research_context(
                stock=stock,
                research_report=report,
                historical_series=series,
                generated_at=GENERATED_AT,
            )

    def test_historical_report_symbol_mismatch_validation(self):
        stock = self.sample_stock()
        report = build_research_report(stock)
        series = self.sample_series()
        report_series = self.sample_series()
        report_series.symbol = "AAPL"
        historical_report = build_historical_research_report(report_series)

        with self.assertRaisesRegex(ResearchContextError, "Historical research report symbol mismatch"):
            build_research_context(
                stock=stock,
                research_report=report,
                historical_series=series,
                historical_research_report=historical_report,
                generated_at=GENERATED_AT,
            )

    def test_currency_same_and_mismatch_limitation(self):
        same_context = self.build_context(series=self.sample_series())
        self.assertNotIn("context:currency_mismatch", [item.id for item in same_context.limitations])

        series = self.sample_series()
        series.currency = "TWD"
        context = self.build_context(series=series)

        limitation = next(item for item in context.limitations if item.id == "context:currency_mismatch")
        self.assertIn("USD", limitation.message)
        self.assertIn("TWD", limitation.message)

    def test_current_per_metric_evidence(self):
        context = self.build_context()
        evidence = self.evidence_by_id(context)

        self.assertEqual(evidence["current:return_on_equity"].metric, "return_on_equity")
        self.assertEqual(evidence["current:return_on_equity"].value, 0.45)
        self.assertEqual(evidence["current:return_on_equity"].unit, "ratio")
        self.assertEqual(evidence["current:current_price"].currency, "USD")
        self.assertEqual(evidence["current:sector"].value, "Technology")

    def test_historical_per_metric_evidence_uses_period_end_id(self):
        context = self.build_context(series=self.sample_series())
        evidence = self.evidence_by_id(context)

        revenue = evidence["historical:revenue:2024-01-31"]
        eps = evidence["historical:eps:2025-01-31"]
        self.assertEqual(revenue.value, 100.0)
        self.assertEqual(revenue.period_end, date(2024, 1, 31))
        self.assertEqual(revenue.period_year, 2024)
        self.assertEqual(revenue.currency, "USD")
        self.assertEqual(eps.value, 3.0)

    def test_no_raw_evidence_for_missing_historical_field(self):
        context = self.build_context(series=self.eps_missing_series())
        evidence_ids = {item.id for item in context.evidence}

        self.assertNotIn("historical:eps:2025-12-31", evidence_ids)
        self.assertIn("missing:historical:eps:2025-12-31", [item.id for item in context.missing_data])

    def test_evidence_ids_are_unique_and_deterministic(self):
        first = self.build_context(series=self.sample_series())
        second = self.build_context(series=self.sample_series())

        first_ids = [item.id for item in first.evidence]
        second_ids = [item.id for item in second.evidence]
        self.assertEqual(len(first_ids), len(set(first_ids)))
        self.assertEqual(first_ids, second_ids)

    def test_derived_52_week_position_evidence(self):
        context = self.build_context()
        item = self.evidence_by_id(context)["derived:52_week_position"]

        self.assertEqual(item.value, 0.5)
        self.assertEqual(item.source_type, "derived")
        self.assertEqual(
            item.derived_from,
            (
                "current:current_price",
                "current:fifty_two_week_low",
                "current:fifty_two_week_high",
            ),
        )

    def test_revenue_yoy_and_eps_yoy_derived_evidence(self):
        context = self.build_context(series=self.sample_series())
        evidence = self.evidence_by_id(context)

        revenue_yoy = evidence["derived:revenue_yoy:2025-01-31"]
        eps_yoy = evidence["derived:eps_yoy:2025-01-31"]
        self.assertAlmostEqual(revenue_yoy.value, 0.4)
        self.assertAlmostEqual(eps_yoy.value, 0.2)
        self.assertEqual(
            revenue_yoy.derived_from,
            (
                "historical:revenue:2024-01-31",
                "historical:revenue:2025-01-31",
            ),
        )

    def test_non_consecutive_year_no_revenue_yoy(self):
        series = HistoricalFinancialSeries(
            symbol="NVDA",
            currency="USD",
            periods=[
                self.period(2023, revenue=100.0),
                self.period(2025, revenue=120.0),
            ],
        )
        context = self.build_context(series=series)

        self.assertNotIn("derived:revenue_yoy:2025-12-31", self.evidence_by_id(context))
        self.assertIn("missing:historical:revenue_yoy:2025-12-31", self.missing_by_id(context))

    def test_previous_eps_less_than_or_equal_zero_no_eps_yoy(self):
        series = HistoricalFinancialSeries(
            symbol="NVDA",
            currency="USD",
            periods=[
                self.period(2024, eps=0.0),
                self.period(2025, eps=2.0),
            ],
        )
        context = self.build_context(series=series)
        missing = self.missing_by_id(context)["missing:historical:eps_yoy:2025-12-31"]

        self.assertNotIn("derived:eps_yoy:2025-12-31", self.evidence_by_id(context))
        self.assertIn("less than or equal to zero", missing.reason)

    def test_broken_derived_reference_raises(self):
        with self.assertRaisesRegex(ResearchContextError, "references missing derived_from"):
            validate_evidence([
                EvidenceItem(
                    id="derived:broken",
                    category="derived",
                    metric="broken",
                    value=1.0,
                    unit=None,
                    currency=None,
                    period_end=None,
                    period_year=None,
                    source="test",
                    source_type="derived",
                    derived_from=("current:not_exists",),
                )
            ])

    def test_duplicate_evidence_id_raises(self):
        item = EvidenceItem(
            id="current:roe",
            category="current",
            metric="return_on_equity",
            value=0.1,
            unit="ratio",
            currency=None,
            period_end=None,
            period_year=None,
            source="test",
            source_type="source",
        )
        with self.assertRaisesRegex(ResearchContextError, "Duplicate evidence ID"):
            validate_evidence([item, item])

    def test_current_observation_traceability(self):
        stock = self.sample_stock()
        stock.revenue_growth = -0.1
        stock.earnings_growth = -0.2
        stock.total_debt = 60_000_000_000
        stock.current_price = 130.0
        context = self.build_context(stock=stock)

        links = {(item.observation_scope, item.metric): item for item in context.observation_links}
        self.assertEqual(links[("current", "forward_pe")].evidence_ids, ("current:trailing_pe", "current:forward_pe"))
        self.assertEqual(links[("current", "revenue_growth")].evidence_ids, ("current:revenue_growth",))
        self.assertEqual(
            links[("current", "earnings_growth")].evidence_ids,
            ("current:earnings_growth", "current:revenue_growth"),
        )
        self.assertEqual(links[("current", "total_debt")].evidence_ids, ("current:total_debt", "current:total_cash"))
        self.assertEqual(
            links[("current", "two_hundred_day_average")].evidence_ids,
            ("current:current_price", "current:two_hundred_day_average"),
        )

    def test_historical_revenue_recovery_traceability(self):
        series = self.recovery_series()
        context = self.build_context(series=series)
        recovery_link = next(
            item
            for item in context.observation_links
            if item.observation_scope == "historical"
            and item.metric == "revenue"
            and "derived:revenue_yoy:2023-12-31" in item.evidence_ids
        )

        self.assertIn("derived:revenue_yoy:2024-12-31", recovery_link.evidence_ids)
        self.assertIn("derived:revenue_yoy:2025-12-31", recovery_link.evidence_ids)
        evidence = self.evidence_by_id(context)
        self.assertEqual(
            evidence["derived:revenue_yoy:2025-12-31"].derived_from,
            (
                "historical:revenue:2024-12-31",
                "historical:revenue:2025-12-31",
            ),
        )

    def test_missing_eps_observation_links_to_missing_data(self):
        context = self.build_context(series=self.eps_missing_series())
        link = next(
            item
            for item in context.observation_links
            if item.observation_scope == "historical"
            and item.metric == "eps"
            and item.missing_data_ids
        )

        self.assertIn("missing:historical:eps:2025-12-31", link.missing_data_ids)
        missing = self.missing_by_id(context)["missing:historical:eps:2025-12-31"]
        self.assertEqual(missing.period_end, date(2025, 12, 31))
        self.assertIn("EPS YoY", missing.impact)

    def test_missing_data_has_structured_reason_impact_and_deterministic_id(self):
        context = self.build_context(series=self.eps_missing_series())
        current_missing = self.missing_by_id(self.build_context(stock=self.partial_stock()))[
            "missing:current:return_on_equity"
        ]
        historical_missing = self.missing_by_id(context)["missing:historical:eps:2025-12-31"]

        self.assertEqual(current_missing.metric, "return_on_equity")
        self.assertEqual(current_missing.reason, "Yahoo current snapshot value unavailable")
        self.assertIn("Profitability", current_missing.impact)
        self.assertEqual(historical_missing.metric, "eps")
        self.assertEqual(historical_missing.period_year, 2025)
        self.assertEqual(historical_missing.reason, "Yahoo Finance annual statement value unavailable")

    def test_limitations_include_global_no_history_stale_and_currency(self):
        no_history = self.build_context()
        self.assertIn("global:annual_historical_data_only", [item.id for item in no_history.limitations])
        self.assertIn("global:no_quarterly_or_ttm", [item.id for item in no_history.limitations])
        self.assertIn("global:no_fx_conversion", [item.id for item in no_history.limitations])

        series = self.sample_series()
        series.is_stale = True
        stale = self.build_context(series=series)
        self.assertIn("context:stale_historical_data", [item.id for item in stale.limitations])

    def test_serialization_is_json_safe_with_iso_dates_and_none(self):
        context = self.build_context(series=self.eps_missing_series())
        payload = context.to_dict()
        encoded = json.dumps(payload, ensure_ascii=False)

        self.assertIn('"generated_at": "2026-08-01T10:00:00+00:00"', encoded)
        self.assertIn('"period_end": "2025-12-31"', encoded)
        self.assertIn('"fetched_at": null', encoded)
        self.assertNotIn("HistoricalFinancialPeriod(", encoded)

    def test_same_generated_at_serialized_context_is_stable(self):
        first = self.build_context(series=self.sample_series()).to_dict()
        second = self.build_context(series=self.sample_series()).to_dict()

        self.assertEqual(first, second)

    def test_different_generated_at_keeps_ids_and_links_stable(self):
        first = self.build_context(series=self.sample_series(), generated_at=GENERATED_AT)
        second = self.build_context(
            series=self.sample_series(),
            generated_at=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
        )

        self.assertNotEqual(first.to_dict()["generated_at"], second.to_dict()["generated_at"])
        self.assertEqual([item.id for item in first.evidence], [item.id for item in second.evidence])
        self.assertEqual([item.id for item in first.missing_data], [item.id for item in second.missing_data])
        self.assertEqual(first.observation_links, second.observation_links)

    def test_non_finite_current_historical_and_evidence_raise(self):
        stock = self.sample_stock()
        stock.return_on_equity = math.nan
        with self.assertRaisesRegex(ResearchContextError, "Non-finite numeric"):
            self.build_context(stock=stock)

        series = self.sample_series()
        series.periods[0].revenue = math.inf
        with self.assertRaisesRegex(ResearchContextError, "Non-finite numeric"):
            self.build_context(series=series)

        with self.assertRaisesRegex(ResearchContextError, "Non-finite numeric"):
            ensure_no_non_finite(
                EvidenceItem(
                    id="current:bad",
                    category="current",
                    metric="bad",
                    value=math.inf,
                    unit=None,
                    currency=None,
                    period_end=None,
                    period_year=None,
                    source="test",
                    source_type="source",
                )
            )

    def test_no_recommendation_language_introduced_by_context_builder(self):
        context = self.build_context(series=self.sample_series()).to_dict()
        combined_text = json.dumps(context, ensure_ascii=False).lower()

        for term in ["buy", "sell", "hold", "score", "rating", "recommendation"]:
            self.assertIsNone(re.search(rf"\b{term}\b", combined_text))
        self.assertNotIn("target price", combined_text)


if __name__ == "__main__":
    unittest.main()
