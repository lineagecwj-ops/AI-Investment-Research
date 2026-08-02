import json
import math
import re
import sys
import unittest
from dataclasses import replace
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
from research_context import ObservationEvidenceLink
from research_context import build_current_observation_link
from research_context import build_research_context
from research_context_selector import ResearchQuestionType
from research_context_selector import ResearchSelectionRequest
from research_context_selector import SelectionError
from research_context_selector import include_evidence_lineage
from research_context_selector import select_research_context
from research_context_selector import validate_selected_research_context
from research_service import ResearchObservation
from research_service import build_research_report


GENERATED_AT = datetime(2026, 8, 2, 8, 0, tzinfo=UTC)


class ResearchContextSelectorTestCase(unittest.TestCase):

    def stock(self):
        return Stock(
            symbol="2454.TW",
            company_name="MediaTek Inc.",
            currency="TWD",
            current_price=1200.0,
            market_cap=1_900_000_000_000,
            trailing_pe=30.0,
            forward_pe=20.0,
            trailing_eps=42.0,
            return_on_equity=0.28,
            company_summary="MediaTek designs semiconductor platforms.",
            gross_margin=0.48,
            operating_margin=0.22,
            net_margin=0.18,
            revenue_growth=-0.05,
            earnings_growth=-0.12,
            total_cash=150_000_000_000,
            total_debt=90_000_000_000,
            debt_to_equity=25.0,
            operating_cash_flow=110_000_000_000,
            free_cash_flow=80_000_000_000,
            price_to_book=4.5,
            fifty_two_week_high=1500.0,
            fifty_two_week_low=900.0,
            fifty_day_average=1180.0,
            two_hundred_day_average=1250.0,
            sector="Technology",
            industry="Semiconductors",
        )

    def series(self):
        return HistoricalFinancialSeries(
            symbol="2454.TW",
            currency="TWD",
            fetched_at=datetime(2026, 8, 2, 7, 0, tzinfo=UTC),
            periods=[
                self.period(2022, revenue=100.0, net_income=20.0, eps=10.0, gross_margin=0.45, operating_margin=0.2, net_margin=0.18, free_cash_flow=18.0, operating_cash_flow=25.0, total_assets=200.0, total_debt=40.0, total_equity=120.0, cash=60.0),
                self.period(2023, revenue=80.0, net_income=12.0, eps=6.0, gross_margin=0.42, operating_margin=0.15, net_margin=0.12, free_cash_flow=10.0, operating_cash_flow=18.0, total_assets=210.0, total_debt=45.0, total_equity=125.0, cash=55.0),
                self.period(2024, revenue=95.0, net_income=18.0, eps=8.0, gross_margin=0.44, operating_margin=0.18, net_margin=0.15, free_cash_flow=14.0, operating_cash_flow=21.0, total_assets=230.0, total_debt=50.0, total_equity=140.0, cash=65.0),
                self.period(2025, revenue=110.0, net_income=21.0, eps=None, gross_margin=0.46, operating_margin=0.19, net_margin=0.16, free_cash_flow=16.0, operating_cash_flow=24.0, total_assets=250.0, total_debt=52.0, total_equity=150.0, cash=70.0),
            ],
        )

    def period(
        self,
        year,
        revenue=None,
        net_income=None,
        eps=None,
        gross_margin=None,
        operating_margin=None,
        net_margin=None,
        free_cash_flow=None,
        operating_cash_flow=None,
        total_assets=None,
        total_debt=None,
        total_equity=None,
        cash=None,
    ):
        return HistoricalFinancialPeriod(
            symbol="2454.TW",
            period_end=date(year, 12, 31),
            period_year=year,
            currency="TWD",
            revenue=revenue,
            net_income=net_income,
            eps=eps,
            gross_margin=gross_margin,
            operating_margin=operating_margin,
            net_margin=net_margin,
            operating_cash_flow=operating_cash_flow,
            capital_expenditure=-5.0,
            free_cash_flow=free_cash_flow,
            total_assets=total_assets,
            total_debt=total_debt,
            total_equity=total_equity,
            cash_and_cash_equivalents=cash,
        )

    def context(self):
        stock = self.stock()
        series = self.series()
        return build_research_context(
            stock=stock,
            research_report=build_research_report(stock),
            historical_series=series,
            historical_research_report=build_historical_research_report(series),
            display_name=stock.company_name,
            generated_at=GENERATED_AT,
        )

    def selected_ids(self, selected):
        return {item.id for item in selected.selected_evidence}

    def test_question_type_values_are_stable_and_invalid_type_rejected(self):
        self.assertEqual(ResearchQuestionType.GROWTH.value, "growth")
        self.assertEqual(ResearchQuestionType.GENERAL_RESEARCH.value, "general_research")

        with self.assertRaisesRegex(SelectionError, "ResearchQuestionType"):
            select_research_context(
                self.context(),
                ResearchSelectionRequest(question_type="growth"),
            )

    def test_growth_selection_includes_growth_evidence_and_excludes_unrelated_values(self):
        selected = select_research_context(
            self.context(),
            ResearchSelectionRequest(ResearchQuestionType.GROWTH),
        )
        ids = self.selected_ids(selected)

        self.assertIn("current:revenue_growth", ids)
        self.assertIn("current:earnings_growth", ids)
        self.assertIn("historical:revenue:2025-12-31", ids)
        self.assertIn("derived:revenue_yoy:2025-12-31", ids)
        self.assertIn("historical:net_income:2025-12-31", ids)
        self.assertIn("historical:eps:2024-12-31", ids)
        self.assertNotIn("current:price_to_book", ids)
        self.assertNotIn("historical:total_assets:2025-12-31", ids)
        self.assertIn("missing:historical:eps:2025-12-31", [item.id for item in selected.selected_missing_data])

    def test_valuation_selection_keeps_valuation_and_limited_historical_context(self):
        selected = select_research_context(
            self.context(),
            ResearchSelectionRequest(ResearchQuestionType.VALUATION),
        )
        ids = self.selected_ids(selected)

        self.assertIn("current:trailing_pe", ids)
        self.assertIn("current:forward_pe", ids)
        self.assertIn("current:price_to_book", ids)
        self.assertIn("current:trailing_eps", ids)
        self.assertIn("current:earnings_growth", ids)
        self.assertIn("historical:eps:2024-12-31", ids)
        self.assertIn("historical:net_income:2025-12-31", ids)
        self.assertIn("historical:revenue:2025-12-31", ids)
        self.assertNotIn("historical:free_cash_flow:2025-12-31", ids)
        self.assertNotIn("historical:total_debt:2025-12-31", ids)
        self.assertTrue(any(link.metric == "forward_pe" for link in selected.selected_observation_links))

    def test_market_position_excludes_historical_fundamentals(self):
        selected = select_research_context(
            self.context(),
            ResearchSelectionRequest(ResearchQuestionType.MARKET_POSITION),
        )
        ids = self.selected_ids(selected)

        self.assertIn("current:current_price", ids)
        self.assertIn("current:fifty_two_week_high", ids)
        self.assertIn("current:fifty_two_week_low", ids)
        self.assertIn("current:fifty_day_average", ids)
        self.assertIn("current:two_hundred_day_average", ids)
        self.assertIn("derived:52_week_position", ids)
        self.assertFalse(any(item.startswith("historical:") for item in ids))

    def test_historical_specific_selection_preserves_all_period_ids(self):
        selected = select_research_context(
            self.context(),
            ResearchSelectionRequest(ResearchQuestionType.HISTORICAL_REVENUE),
        )
        ids = self.selected_ids(selected)

        self.assertIn("historical:revenue:2022-12-31", ids)
        self.assertIn("historical:revenue:2025-12-31", ids)
        self.assertIn("derived:revenue_yoy:2025-12-31", ids)
        self.assertNotIn("historical:eps:2024-12-31", ids)

    def test_derived_evidence_selection_closes_lineage_recursively(self):
        context = self.context()
        selected = select_research_context(
            context,
            ResearchSelectionRequest(ResearchQuestionType.HISTORICAL_REVENUE),
        )
        ids = self.selected_ids(selected)

        self.assertIn("historical:revenue:2024-12-31", ids)
        self.assertIn("historical:revenue:2025-12-31", ids)

        first = EvidenceItem(
            id="derived:first",
            category="test",
            metric="test",
            value=1.0,
            unit=None,
            currency=None,
            period_end=None,
            period_year=None,
            source="test",
            source_type="derived",
            derived_from=("derived:second",),
        )
        second = replace(first, id="derived:second", derived_from=("derived:first",))
        with self.assertRaisesRegex(SelectionError, "Circular"):
            include_evidence_lineage({"derived:first"}, {"derived:first": first, "derived:second": second})

    def test_observation_link_id_is_stable_when_index_changes(self):
        observation = ResearchObservation(
            category="Growth（成長性）",
            title="Revenue Growth（營收成長率）為負值",
            metric="revenue_growth",
            what_happened="x",
            why_it_matters="x",
            what_to_check=["x"],
        )
        first = build_current_observation_link(0, observation, {"current:revenue_growth"}, set())
        second = build_current_observation_link(7, observation, {"current:revenue_growth"}, set())

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.observation_index, 0)
        self.assertEqual(second.observation_index, 7)

    def test_missing_data_is_relevant_and_denoised(self):
        selected = select_research_context(
            self.context(),
            ResearchSelectionRequest(ResearchQuestionType.HISTORICAL_EARNINGS),
        )
        missing_ids = [item.id for item in selected.selected_missing_data]

        self.assertIn("missing:historical:eps:2025-12-31", missing_ids)
        self.assertNotIn("missing:historical:eps_yoy:2025-12-31", missing_ids)
        self.assertNotIn("missing:historical:free_cash_flow:2025-12-31", missing_ids)

    def test_limitation_selection_excludes_irrelevant_global_limitations_for_market_position(self):
        selected = select_research_context(
            self.context(),
            ResearchSelectionRequest(ResearchQuestionType.MARKET_POSITION),
        )
        limitation_ids = {item.id for item in selected.selected_limitations}

        self.assertNotIn("global:annual_historical_data_only", limitation_ids)
        self.assertNotIn("global:no_quarterly_or_ttm", limitation_ids)

    def test_evidence_budget_keeps_atomic_lineage_and_serializes(self):
        selected = select_research_context(
            self.context(),
            ResearchSelectionRequest(ResearchQuestionType.GROWTH, max_evidence=6),
        )
        ids = self.selected_ids(selected)

        self.assertLessEqual(len(selected.selected_evidence), 6)
        for item in selected.selected_evidence:
            self.assertTrue(set(item.derived_from).issubset(ids))

        encoded = json.dumps(selected.to_dict(), ensure_ascii=False)
        self.assertIn('"question_type": "growth"', encoded)

    def test_general_research_is_subset_with_multi_category_coverage(self):
        context = self.context()
        selected = select_research_context(
            context,
            ResearchSelectionRequest(ResearchQuestionType.GENERAL_RESEARCH),
        )
        metrics = {item.metric for item in selected.selected_evidence}

        self.assertLess(len(selected.selected_evidence), len(context.evidence))
        self.assertIn("sector", metrics)
        self.assertIn("return_on_equity", metrics)
        self.assertIn("revenue_yoy", metrics)
        self.assertIn("trailing_pe", metrics)
        self.assertIn("free_cash_flow", metrics)
        self.assertIn("fifty_two_week_position", metrics)

    def test_validation_rejects_broken_links_duplicates_and_non_finite_values(self):
        selected = select_research_context(
            self.context(),
            ResearchSelectionRequest(ResearchQuestionType.GROWTH),
        )
        duplicate = replace(selected, selected_evidence=selected.selected_evidence + [selected.selected_evidence[0]])
        with self.assertRaisesRegex(SelectionError, "unique"):
            validate_selected_research_context(duplicate)

        broken_link = ObservationEvidenceLink(
            id="broken",
            observation_scope="current",
            observation_index=0,
            category="broken",
            metric="broken",
            evidence_ids=("current:not_found",),
        )
        broken = replace(selected, selected_observation_links=[broken_link])
        with self.assertRaisesRegex(SelectionError, "missing evidence"):
            validate_selected_research_context(broken)

        bad_evidence = replace(
            selected.selected_evidence[0],
            value=math.inf,
        )
        non_finite = replace(selected, selected_evidence=[bad_evidence])
        with self.assertRaisesRegex(SelectionError, "non-finite"):
            validate_selected_research_context(non_finite)

    def test_selector_adds_no_recommendation_language(self):
        selected = select_research_context(
            self.context(),
            ResearchSelectionRequest(ResearchQuestionType.GENERAL_RESEARCH),
        ).to_dict()
        combined_text = json.dumps(selected, ensure_ascii=False).lower()

        for term in ["buy", "sell", "hold", "score", "rating", "recommendation"]:
            self.assertIsNone(re.search(rf"\b{term}\b", combined_text))
        self.assertNotIn("target price", combined_text)


if __name__ == "__main__":
    unittest.main()
