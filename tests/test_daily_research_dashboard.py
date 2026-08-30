import sys
import inspect
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pyarrow as pa
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from forward_research_observation_service import ForwardResearchObservationError
from historical_price_service import HistoricalPriceError


def daily_dashboard_app():
    from types import SimpleNamespace
    from unittest.mock import patch
    import app as app_module

    frozen = SimpleNamespace(
        universe_version="test-frozen-v1",
        symbols=("2330.TW", "2454.TW"),
    )
    with patch("app.list_watchlist", return_value=["2330.TW"]), patch(
        "app.list_universes",
        return_value=[],
    ), patch(
        "app.universe_ui.load_frozen_twse_research_source",
        return_value=frozen,
    ), patch(
        "app.load_daily_research_company_context",
        return_value={
            "2330.TW": {
                "company_name": "台積電",
                "broad_industry": "半導體業",
                "classification_as_of_date": "2026-08-20",
                "source": "test",
            }
        },
    ), patch(
        "app.live_market_data_status",
        return_value=SimpleNamespace(
            selected_market_date=__import__("datetime").date(2026, 8, 28),
            benchmark_market_date=__import__("datetime").date(2026, 8, 28),
            selected_market_data_is_fresh=True,
        ),
    ):
        app_module.initialize_session_state()
        app_module.render_daily_research_dashboard()


def candidate_explorer_app():
    import app as app_module
    from unittest.mock import patch

    with patch("app.build_research_shortlist_status_rows", return_value=[]):
        app_module.initialize_session_state()
        app_module.render_research_candidate_explorer(
            watchlist_symbols=["2330.TW"],
            universes=[],
            frozen_universe=None,
            company_context={
                "2330.TW": {
                    "company_name": "台積電",
                    "broad_industry": "半導體業",
                }
            },
        )


def evidence_refresh_fixture_app():
    import app as app_module
    from unittest.mock import patch

    def refresh(rows):
        app_module.st.session_state["fixture_refresh_calls"] = app_module.st.session_state.get("fixture_refresh_calls", 0) + 1
        return ({
            "股票代號": "1216.TW", "目前快照": "已更新", "基本面": "可用", "估值": "可用",
            "市場": "可用", "歷史市場": "已更新", "月營收": "本地資料可用", "相對 0050": "可用",
        },)

    with patch("app.build_research_shortlist_status_rows", return_value=[]), patch(
        "app.refresh_research_shortlist_evidence", side_effect=refresh
    ), patch("app.analyze_research_shortlist") as analyze:
        app_module.initialize_session_state()
        app_module.st.session_state[app_module.RESEARCH_SHORTLIST_SESSION_KEY] = [{
            "股票代號": "1216.TW", "公司名稱": "統一", "產業": "食品業",
        }]
        app_module.render_research_shortlist_controls(
            [], company_context={"1216.TW": {"company_name": "統一", "broad_industry": "食品業"}}, watchlist_symbols=[]
        )
        app_module.st.session_state["fixture_ai_calls"] = analyze.call_count


def opportunity_radar_fixture_app():
    from datetime import datetime
    from types import SimpleNamespace
    from unittest.mock import patch
    import app as app_module
    from opportunity_radar_service import MonthlyRevenueRecord

    frozen = SimpleNamespace(symbols=("2330.TW", "2454.TW", "2603.TW"))
    records = (
        MonthlyRevenueRecord("2330.TW", "台積電", "2026-08", 120, 100, 80, 0.5, 0.2),
        MonthlyRevenueRecord("2454.TW", "聯發科", "2026-08", 100, 110, 80, 0.25, -0.09),
        MonthlyRevenueRecord("2603.TW", "長榮", "2026-08", 90, 80, 100, -0.1, 0.125),
    )
    def local_context(*, stock_series, **_kwargs):
        values = {"2330.TW": (0.1, 0.2), "2454.TW": (0.1, -0.1), "2603.TW": (None, None)}
        return SimpleNamespace(rel_return_20d=values[stock_series][0], rel_return_60d=values[stock_series][1])
    with patch("app.load_latest_monthly_revenue_snapshot", return_value=({"retrieved_at": datetime(2026, 8, 29).isoformat()}, records)), patch("app.load_live_historical_price_series", side_effect=lambda symbol: symbol), patch("app.build_local_observation_context", side_effect=local_context):
        app_module.initialize_session_state()
        app_module.render_opportunity_radar(frozen, {"2330.TW": {"company_name": "台積電", "broad_industry": "半導體業"}, "2454.TW": {"company_name": "聯發科", "broad_industry": "半導體業"}, "2603.TW": {"company_name": "長榮", "broad_industry": "航運業"}}, ["2330.TW"])


def ai_analyst_shortlist_fixture_app():
    from unittest.mock import patch
    import app as app_module

    cards = [
        {
            "symbol": "2330.TW",
            "company_name": "台積電",
            "research_priority": "優先深入研究",
            "verified_evidence": [
                {"section": "Opportunity Radar", "metric": "revenue_yoy", "label": "Revenue YoY", "display_value": "50.00%", "status": "available", "evidence_id": "radar:2330.TW:revenue_yoy"},
                {"section": "Opportunity Radar", "metric": "rel_return_20d", "label": "20D 相對 0050", "display_value": "資料不足", "status": "missing", "evidence_id": None},
                {"section": "基本面", "metric": "net_margin", "label": "Net Margin", "display_value": "25.00%", "status": "available", "evidence_id": "current:net_margin"},
                {"section": "基本面", "metric": "trailing_eps", "label": "EPS", "display_value": "TWD 2.50", "status": "available", "evidence_id": "current:trailing_eps"},
                {"section": "基本面", "metric": "total_cash", "label": "Total Cash", "display_value": "TWD 10.00B", "status": "available", "evidence_id": "current:total_cash"},
                {"section": "基本面", "metric": "total_debt", "label": "Total Debt", "display_value": "TWD 20.00B", "status": "available", "evidence_id": "current:total_debt"},
                {"section": "基本面", "metric": "debt_to_equity", "label": "Debt to Equity", "display_value": "50.00", "status": "available", "evidence_id": "current:debt_to_equity"},
                {"section": "基本面", "metric": "operating_cash_flow", "label": "Operating Cash Flow", "display_value": "TWD 5.00B", "status": "available", "evidence_id": "current:operating_cash_flow"},
                {"section": "基本面", "metric": "free_cash_flow", "label": "Free Cash Flow", "display_value": "TWD 3.00B", "status": "available", "evidence_id": "current:free_cash_flow"},
                {"section": "估值", "metric": "trailing_pe", "label": "Trailing P/E", "display_value": "20.00", "status": "available", "evidence_id": "current:trailing_pe"},
                {"section": "估值", "metric": "forward_pe", "label": "Forward P/E", "display_value": "18.00", "status": "available", "evidence_id": "current:forward_pe"},
                {"section": "估值", "metric": "price_to_book", "label": "P/B", "display_value": "4.00", "status": "available", "evidence_id": "current:price_to_book"},
                {"section": "市場", "metric": "current_price", "label": "Current Price", "display_value": "TWD 100.00", "status": "available", "evidence_id": "current:current_price"},
                {"section": "市場", "metric": "fifty_two_week_high", "label": "52-week High", "display_value": "TWD 110.00", "status": "available", "evidence_id": "current:fifty_two_week_high"},
                {"section": "市場", "metric": "fifty_two_week_low", "label": "52-week Low", "display_value": "TWD 70.00", "status": "available", "evidence_id": "current:fifty_two_week_low"},
                {"section": "市場", "metric": "fifty_day_average", "label": "50-day Average", "display_value": "TWD 98.00", "status": "available", "evidence_id": "current:fifty_day_average"},
                {"section": "市場", "metric": "two_hundred_day_average", "label": "200-day Average", "display_value": "TWD 90.00", "status": "available", "evidence_id": "current:two_hundred_day_average"},
                {"section": "估值", "metric": "net_margin", "label": "Net Margin", "display_value": "25.00%", "status": "available", "evidence_id": "current:net_margin"},
                {"section": "估值", "metric": "trailing_eps", "label": "EPS", "display_value": "TWD 2.50", "status": "available", "evidence_id": "current:trailing_eps"},
                {"section": "估值", "metric": "total_cash", "label": "Total Cash", "display_value": "TWD 10.00B", "status": "available", "evidence_id": "current:total_cash"},
                {"section": "估值", "metric": "total_debt", "label": "Total Debt", "display_value": "TWD 20.00B", "status": "available", "evidence_id": "current:total_debt"},
                {"section": "估值", "metric": "debt_to_equity", "label": "Debt to Equity", "display_value": "50.00", "status": "available", "evidence_id": "current:debt_to_equity"},
                {"section": "估值", "metric": "operating_cash_flow", "label": "Operating Cash Flow", "display_value": "TWD 5.00B", "status": "available", "evidence_id": "current:operating_cash_flow"},
                {"section": "估值", "metric": "free_cash_flow", "label": "Free Cash Flow", "display_value": "TWD 3.00B", "status": "available", "evidence_id": "current:free_cash_flow"},
            ],
            "opportunity_interpretation": ["營收方向提供研究線索。"],
            "fundamental_quality": "基本面資料目前較完整。",
            "valuation_context": "估值仍需同業比較。",
            "market_confirmation": "市場確認存在但仍需追蹤。",
            "risks": ["資料時點仍需確認。"],
            "contradictions": ["Revenue YoY 為正，但 Revenue MoM 為負。"],
            "missing_evidence": ["missing:current:market_cap", "context:unmapped_internal_gap"],
            "next_checks": ["確認 global:unmapped_internal_limit。"],
            "evidence_refs": ["radar:2330.TW:revenue_yoy"],
            "evidence_dates": {"revenue_yoy": "2026-08-01"},
        },
        {
            "symbol": "2454.TW",
            "company_name": "聯發科",
            "research_priority": "值得觀察",
            "verified_evidence": [],
            "opportunity_interpretation": ["相對強弱提供觀察線索。"],
            "fundamental_quality": "目前證據不足。",
            "valuation_context": "目前證據不足。",
            "market_confirmation": "目前證據不足。",
            "risks": [],
            "contradictions": [],
            "missing_evidence": ["缺少本機基本面快照。"],
            "next_checks": ["補齊本機資料。"],
            "evidence_refs": [],
            "evidence_dates": {},
        },
        {
            "symbol": "2603.TW",
            "company_name": "長榮",
            "research_priority": "證據不足",
            "verified_evidence": [],
            "opportunity_interpretation": [],
            "fundamental_quality": "目前證據不足。",
            "valuation_context": "目前證據不足。",
            "market_confirmation": "目前證據不足。",
            "risks": [],
            "contradictions": [],
            "missing_evidence": ["缺少本機基本面快照。"],
            "next_checks": ["補齊本機資料。"],
            "evidence_refs": [],
            "evidence_dates": {},
        },
    ]
    result = {
        "cards": cards,
        "synthesis": {
            "priority_deep_dive": [{"symbol": "2330.TW", "reason": "目前證據較完整。", "main_unresolved_risk": "資料時點仍待確認。"}],
            "cross_company_observations": ["兩家公司證據完整度不同。", "missing:current:market_cap"],
            "overall_note": "僅供研究注意力安排。",
        },
        "synthesis_error": None,
        "provider_call_count": 4,
    }
    with patch("app.build_research_shortlist_status_rows", return_value=[]), patch(
        "app.analyze_research_shortlist", return_value=result
    ):
        app_module.initialize_session_state()
        app_module.st.session_state[app_module.RESEARCH_SHORTLIST_SESSION_KEY] = [
            {"股票代號": "2330.TW", "公司名稱": "台積電", "產業": "半導體業"},
            {"股票代號": "2454.TW", "公司名稱": "聯發科", "產業": "半導體業"},
            {"股票代號": "2603.TW", "公司名稱": "長榮", "產業": "航運業"},
        ]
        app_module.render_research_shortlist_controls(
            [],
            company_context={
                "2330.TW": {"company_name": "台積電", "broad_industry": "半導體業"},
                "2454.TW": {"company_name": "聯發科", "broad_industry": "半導體業"},
                "2603.TW": {"company_name": "長榮", "broad_industry": "航運業"},
            },
            watchlist_symbols=["2330.TW"],
        )


def _renderer_card(symbol, *, rich):
    from ai_analyst_shortlist import VERIFIED_EVIDENCE_FIELDS

    available_values = {
        "revenue_period": "2026-08",
        "revenue_yoy": "8.85%" if symbol == "1216.TW" else "46.12%",
        "revenue_mom": "6.63%" if symbol == "1216.TW" else "5.97%",
    }
    if rich:
        available_values.update({
            metric: f"{index}.00"
            for index, (_section, metric, _label) in enumerate(VERIFIED_EVIDENCE_FIELDS, start=1)
        })
    rows = [
        {
            "section": section,
            "metric": metric,
            "label": label,
            "display_value": available_values.get(metric, "資料不足"),
            "status": "available" if metric in available_values else "missing",
            "evidence_id": f"fixture:{symbol}:{metric}" if metric in available_values else None,
        }
        for section, metric, label in VERIFIED_EVIDENCE_FIELDS
    ]
    rows[:0] = [
        {
            **rows[1],
            "section": "估值",
            "display_value": "STALE DUPLICATE",
        },
        {
            **rows[-1],
            "section": "基本面",
            "display_value": "STALE DUPLICATE",
        },
    ]
    return {
        "symbol": symbol,
        "company_name": "統一" if symbol == "1216.TW" else "大成鋼",
        "research_priority": "值得觀察",
        "verified_evidence": rows,
        "opportunity_interpretation": ["月營收方向提供研究線索。"],
        "fundamental_quality": "基本面資料可供研究。" if rich else "目前證據不足。",
        "valuation_context": "估值倍數可供比較。" if rich else "目前證據不足。",
        "market_confirmation": "市場位置可供確認。" if rich else "目前證據不足。",
        "risks": ["資料完整性仍需確認。"],
        "contradictions": [],
        "missing_evidence": ["missing:current:market_cap"],
        "next_checks": ["確認 context:no_historical_series。"],
        "evidence_refs": [],
        "evidence_dates": {},
    }


def _render_single_analyst_card(symbol, *, rich):
    import app as app_module

    card = _renderer_card(symbol, rich=rich)
    app_module.render_ai_analyst_shortlist_result({
        "cards": [card],
        "stage1_success_count": 1,
        "synthesis": {
            "priority_deep_dive": [],
            "cross_company_observations": [],
            "overall_note": "僅供研究注意力安排。",
        },
    })


def ai_analyst_sparse_renderer_fixture_app():
    from tests.test_daily_research_dashboard import _render_single_analyst_card

    _render_single_analyst_card("1216.TW", rich=False)


def ai_analyst_rich_renderer_fixture_app():
    from tests.test_daily_research_dashboard import _render_single_analyst_card

    _render_single_analyst_card("2027.TW", rich=True)


def ai_analyst_malformed_synthesis_fixture_app():
    from unittest.mock import patch
    import app as app_module

    failed_result = {
        "cards": [{
            "symbol": "2330.TW",
            "company_name": "台積電",
            "research_priority": "證據不足",
            "verified_evidence": [],
            "opportunity_interpretation": [],
            "fundamental_quality": "AI 初步審查未完成。",
            "valuation_context": "AI 初步審查未完成。",
            "market_confirmation": "AI 初步審查未完成。",
            "risks": [],
            "contradictions": [],
            "missing_evidence": ["AI 輸出格式不正確。"],
            "next_checks": ["稍後重試。"],
            "evidence_refs": [],
            "evidence_dates": {},
        }],
        "synthesis": None,
        "synthesis_error": "malformed",
        "stage2_diagnostic": {
            "code": "STRUCTURED_OUTPUT_SCHEMA_ERROR",
            "exception_class": "AIAnalystShortlistError",
            "input_length": 123,
            "prompt_length": 456,
        },
        "provider_call_count": 2,
    }
    with patch("app.build_research_shortlist_status_rows", return_value=[]), patch(
        "app.analyze_research_shortlist", return_value=failed_result
    ):
        app_module.initialize_session_state()
        app_module.st.session_state[app_module.RESEARCH_SHORTLIST_SESSION_KEY] = [
            {"股票代號": "2330.TW", "公司名稱": "台積電", "產業": "半導體業"}
        ]
        app_module.render_research_shortlist_controls(
            [],
            company_context={"2330.TW": {"company_name": "台積電", "broad_industry": "半導體業"}},
            watchlist_symbols=["2330.TW"],
        )


def _render_acceptance_pipeline():
    from functools import partial
    from ai_analyst_shortlist import analyze_research_shortlist
    from tests.test_ai_analyst_shortlist import (
        NOW, section_answer, acceptance_stock, shortlist_row, valid_synthesis,
    )
    import app as app_module

    app_module.initialize_session_state()
    state = app_module.st.session_state
    symbols = ["1216.TW", "1608.TW", "2027.TW"]
    valid_count = state.get("fixture_valid_count", 3)
    state.setdefault("fixture_stage1_calls", [])
    state.setdefault("fixture_stage2_calls", [])
    state.setdefault("fixture_stage2_payloads", [])
    rows = [shortlist_row(symbol) for symbol in symbols]
    for row in rows:
        row["公司名稱"] = acceptance_stock(row["股票代號"]).company_name

    def generate(*, selected_context, **kwargs):
        state["fixture_stage1_calls"].append(selected_context.symbol)
        if selected_context.symbol not in symbols[:valid_count]:
            raise RuntimeError("fixture Stage-1 failure")
        output = section_answer(selected_context)
        if state.get("fixture_reject_valuation") and "valuation_text" in output:
            output["valuation_text"] = "估值18.33倍，便宜可持有。"
        if state.get("fixture_all_slots_invalid"):
            for key in output:
                if key.endswith("_text"):
                    output[key] = "ROE 12%"
        return output

    def synthesize(*, cards):
        state["fixture_stage2_calls"].append([card["symbol"] for card in cards])
        state["fixture_stage2_payloads"].append(cards)
        answer = valid_synthesis(cards)
        answer["priority_deep_dive"] = [{
            "symbol": cards[0]["symbol"], "reason": "先查核營收變化的來源。",
            "main_unresolved_risk": "缺少長期資料供交叉確認。",
        }]
        return answer

    run = partial(
        analyze_research_shortlist, section_generator=generate,
        synthesis_generator=synthesize, generated_at=NOW,
    )
    radar = {row["股票代號"]: row["_analyst_evidence"] for row in rows}
    with patch("app.analyze_research_shortlist", side_effect=run), patch(
        "app.load_cached_stock_for_ai_analyst", side_effect=acceptance_stock,
    ), patch("app.resolve_current_opportunity_radar_evidence", side_effect=radar.get):
        app_module.render_ai_analyst_shortlist_control(rows)


def ai_analyst_acceptance_pipeline_fixture_app():
    from tests.test_daily_research_dashboard import _render_acceptance_pipeline

    _render_acceptance_pipeline()


class DailyResearchDashboardTestCase(unittest.TestCase):
    def test_ai_analyst_radar_resolver_uses_local_snapshot_and_local_relative_context(self):
        import app as app_module
        from opportunity_radar_service import MonthlyRevenueRecord

        record = MonthlyRevenueRecord("2027.TW", "大成鋼", "N/A", 120, 100, 80, 0.4612, 0.0597)
        with patch("app.find_latest_monthly_revenue_record", return_value=({"retrieved_at": "2026-08-30T00:00:00+08:00"}, record)), patch(
            "app.load_live_historical_price_series", side_effect=lambda symbol: symbol
        ), patch(
            "app.build_local_observation_context",
            return_value=SimpleNamespace(rel_return_20d=0.1260, rel_return_60d=0.2047),
        ):
            evidence = app_module.resolve_current_opportunity_radar_evidence("2027.TW")

        self.assertEqual(evidence["revenue_period"], "N/A")
        self.assertEqual(evidence["revenue_yoy"], 0.4612)
        self.assertEqual(evidence["revenue_mom"], 0.0597)
        self.assertEqual(evidence["relative_return_20d"], 0.1260)
        self.assertEqual(evidence["relative_return_60d"], 0.2047)

    def test_portfolio_display_inputs_are_arrow_safe_without_mutating_projection(self):
        import app as app_module
        from portfolio_dashboard.streamlit_view import build_overview_metric_rows
        from portfolio_dashboard.view_model import PortfolioOverviewProjection
        from portfolio_dashboard.view_model import PortfolioRiskDashboardProjection

        created_at = datetime(2026, 8, 30, 13, 0, tzinfo=UTC)
        projection = PortfolioRiskDashboardProjection(
            overview=PortfolioOverviewProjection(
                portfolio_ids=("portfolio-a",),
                symbol_count=2,
                artifact_count=1,
                event_count=3,
                alert_candidate_count=0,
                risk_level_counts=(),
                monitoring_state_counts=(),
                policy_version_counts=(),
                latest_created_at=created_at,
            ),
            positions=(),
            risk_event_rows=(),
            alert_candidate_rows=(),
            artifact_lineage_rows=(),
        )
        warning_metadata = {"artifact_count": 1, "reference_time": created_at, "missing": None}

        display_projection, display_metadata = app_module.build_portfolio_risk_display_inputs(
            projection, warning_metadata,
        )

        self.assertEqual(projection.overview.symbol_count, 2)
        self.assertIs(projection.overview.latest_created_at, created_at)
        self.assertEqual(display_projection.overview.symbol_count, "2")
        self.assertEqual(display_projection.overview.latest_created_at, created_at.isoformat())
        self.assertEqual(display_metadata, {
            "artifact_count": "1", "reference_time": created_at.isoformat(), "missing": "資料不足",
        })
        overview_rows = build_overview_metric_rows(display_projection)
        overview_table = pa.Table.from_pylist(overview_rows)
        self.assertEqual(str(overview_table.schema.field("Value").type), "string")
        warning_table = pa.Table.from_pylist([
            {"Name": key, "Value": value} for key, value in display_metadata.items()
        ])
        self.assertEqual(str(warning_table.schema.field("Value").type), "string")


    def test_status_rows_preserve_existing_module_boundaries(self):
        rows = build_rows(
            research_stock=stock("2330.TW"),
            historical_stock=stock("2330.TW"),
            historical_series=object(),
            ai_research_session=SimpleNamespace(symbol="2330.TW", turns=(object(),)),
            swing_research_result=SimpleNamespace(
                match_symbols=(),
                no_match_symbols=("2330.TW",),
                not_evaluable_symbols=(),
                failed_symbols=(),
                candidates=(),
            ),
            comparison_stocks=[stock("2330.TW")],
        )

        statuses = {row["研究區塊"]: row["狀態"] for row in rows}
        self.assertEqual(statuses["長期研究"], "有資料")
        self.assertEqual(statuses["歷史趨勢"], "有資料")
        self.assertEqual(statuses["AI 研究"], "有資料")
        self.assertEqual(statuses["波段研究"], "有資料")
        self.assertEqual(statuses["比較分析"], "有資料")
        self.assertEqual(statuses["觀察清單"], "有資料")

    def test_status_rows_do_not_create_scores_or_recommendations(self):
        rows = build_rows()

        row_text = str(rows)
        self.assertNotIn("Score", row_text)
        self.assertNotIn("Ranking", row_text)
        self.assertNotIn("Buy", row_text)
        self.assertNotIn("Sell", row_text)
        self.assertTrue(all(row["狀態"] in {"有資料", "可前往建立", "尚無資料"} for row in rows))

    def test_daily_dashboard_renders_first_screen_with_local_sources(self):
        app_test = AppTest.from_function(daily_dashboard_app)
        app_test.run()

        self.assertFalse(app_test.exception)
        markdown_text = "\n".join(element.value for element in app_test.markdown)
        header_text = "\n".join(element.value for element in app_test.header)
        subheader_text = "\n".join(element.value for element in app_test.subheader)
        caption_text = "\n".join(element.value for element in app_test.caption)
        self.assertIn("每日研究首頁", header_text)
        self.assertIn("2330.TW · 台積電", subheader_text)
        self.assertIn("研究可用狀態", markdown_text)
        self.assertIn("不產生分數、排名或買賣建議", caption_text)
        self.assertTrue(any(metric.label == "產業分類日期" for metric in app_test.metric))
        self.assertTrue(any(metric.label == "市場資料日期" for metric in app_test.metric))
        self.assertTrue(
            any(button.label == "儲存今日研究快照" for button in app_test.button)
        )
        self.assertTrue(
            any(button.label == "更新本地市場資料" for button in app_test.button)
        )

    def test_explicit_market_refresh_targets_selected_symbol_and_0050_only(self):
        import app as app_module

        calls = []

        def loader(symbol, *, force_refresh):
            calls.append((symbol, force_refresh))
            return SimpleNamespace(is_stale=False)

        failures = app_module.refresh_forward_observation_market_data("2454.TW", price_loader=loader)

        self.assertEqual(failures, ())
        self.assertEqual(calls, [("2454.TW", True), ("0050.TW", True)])

    def test_refresh_failure_is_reported_without_automatic_retry(self):
        import app as app_module
        from historical_price_service import HistoricalPriceSourceError

        calls = []

        def loader(symbol, *, force_refresh):
            calls.append((symbol, force_refresh))
            raise HistoricalPriceSourceError("offline")

        failures = app_module.refresh_forward_observation_market_data("2454.TW", price_loader=loader)

        self.assertEqual(failures, ("2454.TW", "0050.TW"))
        self.assertEqual(calls, [("2454.TW", True), ("0050.TW", True)])

    def test_shortlist_add_deduplicates_and_keeps_neutral_symbol_order(self):
        import app as app_module

        existing = [candidate_row("2454.TW")]
        shortlist = app_module.add_research_shortlist_rows(existing, [candidate_row("2330.TW"), candidate_row("2454.TW")])

        self.assertEqual([row["股票代號"] for row in shortlist], ["2330.TW", "2454.TW"])

    def test_shortlist_rejects_more_than_twenty_symbols_without_truncation(self):
        import app as app_module

        rows = [candidate_row(f"{index:04d}.TW") for index in range(21)]
        with self.assertRaisesRegex(ValueError, "最多 20 檔"):
            app_module.add_research_shortlist_rows([], rows)

    def test_shortlist_remove_and_clear_are_session_only_operations(self):
        import app as app_module

        shortlist = [candidate_row("2330.TW"), candidate_row("2454.TW")]
        remaining = app_module.remove_research_shortlist_symbols(shortlist, ["2454.TW"])

        self.assertEqual([row["股票代號"] for row in remaining], ["2330.TW"])
        self.assertEqual(app_module.remove_research_shortlist_symbols(remaining, ["2330.TW"]), [])

    def test_batch_refresh_processes_each_shortlist_symbol_and_0050_once(self):
        import app as app_module

        calls = []

        def loader(symbol, *, force_refresh):
            calls.append((symbol, force_refresh))
            if symbol == "2454.TW":
                raise HistoricalPriceError("offline")
            return SimpleNamespace(is_stale=False)

        results = app_module.refresh_research_shortlist_market_data(
            [candidate_row("2454.TW"), candidate_row("2330.TW"), candidate_row("2330.TW"), candidate_row("0050.TW")],
            price_loader=loader,
        )

        self.assertEqual(calls, [("2330.TW", True), ("2454.TW", True), ("0050.TW", True)])
        self.assertEqual(
            [(row["股票代號"], row["更新狀態"]) for row in results],
            [("2330.TW", "UPDATED"), ("2454.TW", "FAILED"), ("0050.TW", "UPDATED")],
        )

    def test_explicit_evidence_refresh_updates_current_and_prices_with_isolated_failures(self):
        import app as app_module

        stock_calls = []
        price_calls = []
        radar_calls = []

        def stock_loader(symbol, *, force_refresh):
            stock_calls.append((symbol, force_refresh))
            if symbol == "1608.TW":
                raise app_module.StockServiceError("offline")
            return SimpleNamespace(
                revenue_growth=0.1, earnings_growth=0.2, return_on_equity=0.1,
                gross_margin=0.2, operating_margin=0.1, net_margin=0.1,
                trailing_eps=1.0, total_cash=1, total_debt=2, debt_to_equity=3,
                operating_cash_flow=None, free_cash_flow=None, trailing_pe=10.0,
                forward_pe=9.0, price_to_book=1.2, current_price=100.0,
                fifty_two_week_high=110.0, fifty_two_week_low=70.0,
                fifty_day_average=95.0, two_hundred_day_average=90.0,
            )

        def price_loader(symbol, *, force_refresh):
            price_calls.append((symbol, force_refresh))
            if symbol == "1608.TW":
                raise HistoricalPriceError("offline")
            return SimpleNamespace(is_stale=False)

        def radar(symbol):
            radar_calls.append((symbol, list(price_calls)))
            return {
                "revenue_yoy": 0.1,
                "revenue_mom": 0.2,
                "relative_return_20d": 0.01 if symbol == "1216.TW" else None,
                "relative_return_60d": 0.02 if symbol == "1216.TW" else None,
            }
        results = app_module.refresh_research_shortlist_evidence(
            [candidate_row("1608.TW"), candidate_row("1216.TW"), candidate_row("1216.TW")],
            stock_loader=stock_loader,
            price_loader=price_loader,
            radar_evidence_resolver=radar,
        )

        self.assertEqual(stock_calls, [("1216.TW", True), ("1608.TW", True)])
        self.assertEqual(price_calls, [("1216.TW", True), ("1608.TW", True), ("0050.TW", True)])
        self.assertTrue(all(calls[-1] == ("0050.TW", True) for _symbol, calls in radar_calls))
        by_symbol = {row["股票代號"]: row for row in results}
        self.assertEqual(by_symbol["1216.TW"]["目前快照"], "已更新")
        self.assertEqual(by_symbol["1216.TW"]["基本面"], "部分可用")
        self.assertEqual(by_symbol["1216.TW"]["相對 0050"], "可用")
        self.assertEqual(by_symbol["1608.TW"]["目前快照"], "更新失敗")
        self.assertEqual(by_symbol["1608.TW"]["歷史市場"], "更新失敗")
        self.assertEqual(by_symbol["1608.TW"]["相對 0050"], "日期未對齊或資料不足")
        self.assertEqual(by_symbol["0050.TW"]["歷史市場"], "已更新")

    def test_batch_save_is_local_only_and_reports_created_existing_and_stale(self):
        import app as app_module

        calls = []

        def capture(**kwargs):
            calls.append(kwargs)
            if kwargs["symbol"] == "2330.TW":
                return SimpleNamespace(created=True)
            if kwargs["symbol"] == "2454.TW":
                return SimpleNamespace(created=False)
            raise ForwardResearchObservationError("市場資料過舊，請先更新本地市場資料後再儲存。")

        results = app_module.save_research_shortlist_observations(
            [candidate_row("2454.TW"), candidate_row("2330.TW"), candidate_row("2603.TW")],
            watchlist_symbols=["2330.TW"],
            capture_observation=capture,
        )

        self.assertEqual([call["symbol"] for call in calls], ["2330.TW", "2454.TW", "2603.TW"])
        self.assertTrue(calls[0]["in_watchlist"])
        self.assertFalse(calls[1]["in_watchlist"])
        self.assertEqual(
            [(row["股票代號"], row["儲存狀態"]) for row in results],
            [("2330.TW", "CREATED"), ("2454.TW", "ALREADY_EXISTS"), ("2603.TW", "STALE_DATA")],
        )

    def test_candidate_explorer_renders_shortlist_controls_without_session_state_error(self):
        app_test = AppTest.from_function(candidate_explorer_app)
        app_test.run()

        self.assertFalse(app_test.exception)
        self.assertTrue(any(button.label == "加入本次研究清單" for button in app_test.button))
        self.assertTrue(any("本次研究清單" in element.value for element in app_test.markdown))

    def test_explicit_evidence_refresh_button_does_not_run_ai_analysis(self):
        app_test = AppTest.from_function(evidence_refresh_fixture_app)
        app_test.run()

        self.assertFalse(app_test.exception)
        self.assertTrue(any(button.label == "更新研究證據" for button in app_test.button))
        self.assertEqual(app_test.session_state["fixture_refresh_calls"] if "fixture_refresh_calls" in app_test.session_state else 0, 0)
        app_test.button(key="research_shortlist_refresh").click().run()

        self.assertFalse(app_test.exception)
        self.assertEqual(app_test.session_state["fixture_refresh_calls"], 1)
        self.assertEqual(app_test.session_state["fixture_ai_calls"], 0)
        self.assertTrue(app_test.dataframe)

    def test_opportunity_radar_fixture_renders_filters_shortlist_and_pending_handoff(self):
        app_test = AppTest.from_function(opportunity_radar_fixture_app)
        app_test.run()
        self.assertFalse(app_test.exception)
        text = "\n".join(item.value for item in app_test.markdown) + "\n" + "\n".join(item.value for item in app_test.caption)
        self.assertIn("研究機會雷達", text)
        self.assertTrue(any(button.label == "加入本次研究清單" for button in app_test.button))
        app_test.button(key="opportunity_radar_add_shortlist").click().run()
        self.assertFalse(app_test.exception)

    def test_opportunity_radar_handoff_explains_manual_tab_switch(self):
        app_test = AppTest.from_function(opportunity_radar_fixture_app)
        app_test.run()
        app_test.button(key="opportunity_radar_go_research").click().run()

        self.assertFalse(app_test.exception)
        self.assertTrue(any("請點上方 Research 分頁繼續" in item.value for item in app_test.success))

    def test_ai_analyst_explicit_click_renders_cards_and_deep_dive(self):
        app_test = AppTest.from_function(ai_analyst_shortlist_fixture_app)
        app_test.run()
        self.assertTrue(any(button.label == "AI 分析本次研究清單" for button in app_test.button))

        app_test.button(key="ai_analyst_shortlist_run").click().run()

        self.assertFalse(app_test.exception)
        markdown = "\n".join(item.value for item in app_test.markdown)
        captions = "\n".join(item.value for item in app_test.caption)
        self.assertIn("AI 分析師初步審查", markdown)
        self.assertIn("已驗證研究證據", markdown)
        self.assertIn("AI 分析", markdown)
        self.assertIn("Revenue YoY：50.00%", markdown)
        self.assertIn("20D 相對 0050：資料不足", markdown)
        self.assertIn("本次優先深入研究", markdown)
        self.assertIn("研究注意力", captions)
        for label in (
            "Net Margin", "EPS", "Total Cash", "Total Debt", "Debt to Equity",
            "Operating Cash Flow", "Free Cash Flow", "Trailing P/E", "Forward P/E",
            "P/B", "Current Price", "52-week High", "52-week Low", "50-day Average", "200-day Average",
        ):
            self.assertEqual(markdown.count(f"{label}："), 1)
        rendered_text = markdown + "\n" + captions
        self.assertIn("市值資料", rendered_text)
        self.assertIn("相關研究資料", rendered_text)
        self.assertNotRegex(rendered_text, r"(?:missing|context|global):")
        expander_labels = "\n".join(item.label for item in app_test.expander)
        self.assertIn("優先深入研究", expander_labels)
        self.assertIn("值得觀察", expander_labels)
        self.assertIn("證據不足", expander_labels)
        self.assertNotIn("上漲機率", markdown)
        self.assertNotIn("目標價", markdown)

    def test_ai_analyst_malformed_synthesis_keeps_card_and_friendly_failure(self):
        app_test = AppTest.from_function(ai_analyst_malformed_synthesis_fixture_app)
        app_test.run()
        app_test.button(key="ai_analyst_shortlist_run").click().run()

        self.assertFalse(app_test.exception)
        self.assertTrue(any("清單比較暫時無法完成" in item.value for item in app_test.warning))
        self.assertTrue(any("AI 分析師初步審查" in item.value for item in app_test.markdown))
        diagnostic = next(item for item in app_test.expander if item.label == "技術診斷")
        self.assertIn("STRUCTURED_OUTPUT_SCHEMA_ERROR", "\n".join(item.value for item in diagnostic.caption))

    def _assert_single_card_renderer_is_canonical(self, fixture_app):
        from ai_analyst_shortlist import VERIFIED_EVIDENCE_FIELDS

        app_test = AppTest.from_function(fixture_app)
        app_test.run()

        self.assertFalse(app_test.exception)
        markdown_values = [item.value for item in app_test.markdown]
        markdown = "\n".join(markdown_values)
        evidence_start = markdown_values.index("##### 已驗證研究證據")
        analysis_start = markdown_values.index("##### AI 分析")
        evidence_markdown = "\n".join(markdown_values[evidence_start:analysis_start])
        for section in ("Opportunity Radar", "基本面", "估值", "市場"):
            self.assertEqual(evidence_markdown.count(f"**{section}**"), 1)
            self.assertEqual(markdown_values.count(f"**{section}**"), 1)
        self.assertEqual(markdown_values.count("**估值解讀**"), 1)
        for _section, _metric, label in VERIFIED_EVIDENCE_FIELDS:
            self.assertEqual(markdown.count(f"{label}："), 1)
        self.assertNotIn("STALE DUPLICATE", markdown)
        self.assertNotRegex(markdown, r"(?:missing|context|global):")

    def test_ai_analyst_sparse_1216_renderer_uses_one_canonical_metric_map(self):
        self._assert_single_card_renderer_is_canonical(ai_analyst_sparse_renderer_fixture_app)

    def test_ai_analyst_rich_2027_renderer_uses_one_canonical_metric_map(self):
        self._assert_single_card_renderer_is_canonical(ai_analyst_rich_renderer_fixture_app)

    def _assert_acceptance_card_ownership(self, expander):
        values = [item.value for item in expander.markdown]
        text = "\n".join(values)
        self.assertEqual(values.count("##### 已驗證研究證據"), 1)
        self.assertEqual(values.count("##### AI 分析"), 1)
        expected = {
            "Opportunity Radar": ["營收月份", "Revenue YoY", "Revenue MoM", "20D 相對 0050", "60D 相對 0050"],
            "基本面": ["Revenue Growth", "Earnings Growth", "ROE", "Gross Margin", "Operating Margin", "Net Margin",
                    "EPS", "Total Cash", "Total Debt", "Debt to Equity", "Operating Cash Flow", "Free Cash Flow"],
            "估值": ["Trailing P/E", "Forward P/E", "P/B"],
            "市場": ["Current Price", "52-week High", "52-week Low", "50-day Average", "200-day Average"],
        }
        self.assertEqual([len(labels) for labels in expected.values()], [5, 12, 3, 5])
        sections = list(expected)
        for index, (section, labels) in enumerate(expected.items()):
            heading = f"**{section}**"
            self.assertEqual(values.count(heading), 1)
            end = values.index(f"**{sections[index + 1]}**") if index < 3 else values.index("##### AI 分析")
            rows = values[values.index(heading) + 1:end]
            self.assertEqual(len(rows), len(labels))
            for row, label in zip(rows, labels):
                self.assertTrue(row.startswith(f"- {label}："), row)
                self.assertEqual(text.count(f"- {label}："), 1)
        for heading in ("機會判讀", "基本面品質", "估值解讀", "市場確認", "主要風險", "矛盾", "缺少證據", "下一步確認"):
            self.assertEqual(values.count(f"**{heading}**"), 1)
        self.assertNotRegex(text, r"(?:missing|context|global):")
        return text

    def _run_acceptance_pipeline(self, valid_count):
        app_test = AppTest.from_function(ai_analyst_acceptance_pipeline_fixture_app)
        app_test.session_state["fixture_valid_count"] = valid_count
        app_test.run()
        self.assertFalse(app_test.exception)
        self.assertEqual(app_test.session_state["fixture_stage1_calls"], [])
        app_test.button(key="ai_analyst_shortlist_run").click().run()
        self.assertFalse(app_test.exception)
        return app_test

    def test_three_company_button_session_renderer_preserves_all_metrics_once(self):
        app_test = self._run_acceptance_pipeline(3)
        symbols = ["1216.TW", "1608.TW", "2027.TW"]
        self.assertEqual(app_test.session_state["fixture_stage1_calls"], symbols)
        self.assertEqual(app_test.session_state["fixture_stage2_calls"], [symbols])
        self.assertEqual(len(app_test.expander), 3)
        for symbol, expander in zip(symbols, app_test.expander):
            with self.subTest(symbol=symbol):
                self.assertTrue(expander.label.startswith(symbol))
                text = self._assert_acceptance_card_ownership(expander)
                if symbol != "2027.TW":
                    self.assertIn("- ROE：資料不足", text)
                    self.assertIn("- Current Price：資料不足", text)
                else:
                    for expected in ("Current Price：TWD 48.40", "50-day Average：TWD 44.08",
                                     "200-day Average：TWD 39.55", "Earnings Growth：362.20%"):
                        self.assertIn(expected, text)
        self.assertTrue(any(item.value == "#### 本次優先深入研究" for item in app_test.markdown))
        app_test.run()
        self.assertFalse(app_test.exception)
        self.assertEqual(app_test.session_state["fixture_stage1_calls"], symbols)
        self.assertEqual(app_test.session_state["fixture_stage2_calls"], [symbols])

    def test_section_failure_keeps_verified_numbers_and_other_sections_visible(self):
        app_test = AppTest.from_function(ai_analyst_acceptance_pipeline_fixture_app)
        app_test.session_state["fixture_reject_valuation"] = True
        app_test.run().button(key="ai_analyst_shortlist_run").click().run()
        self.assertFalse(app_test.exception)
        text = "\n".join(item.value for item in app_test.markdown)
        self.assertIn("AI 解讀未通過驗證；已驗證數據仍可使用。", text)
        self.assertIn("Current Price：TWD 48.40", text)
        self.assertIn("目前財務證據可供初步研究", text)
        self.assertNotIn("估值18.33倍，便宜可持有。", text)
        payload = app_test.session_state["fixture_stage2_payloads"][0]
        rich = next(card for card in payload if card["symbol"] == "2027.TW")
        self.assertNotIn("valuation_context", rich)
        self.assertNotIn("verified_evidence", rich)
        self.assertEqual(app_test.session_state["fixture_stage1_calls"], ["1216.TW", "1608.TW", "2027.TW"])

    def test_all_invalid_sections_render_evidence_only_and_skip_comparison(self):
        app_test = AppTest.from_function(ai_analyst_acceptance_pipeline_fixture_app)
        app_test.session_state["fixture_all_slots_invalid"] = True
        app_test.run().button(key="ai_analyst_shortlist_run").click().run()
        self.assertFalse(app_test.exception)
        text = "\n".join(item.value for item in app_test.markdown)
        self.assertIn("Current Price：TWD 48.40", text)
        self.assertNotIn("ROE 12%", text)
        self.assertEqual(app_test.session_state["fixture_stage2_calls"], [])
        self.assertTrue(all("證據不足" in expander.label for expander in app_test.expander))

    def test_partial_comparison_renders_validated_pair_and_excluded_company_notice(self):
        app_test = self._run_acceptance_pipeline(2)
        self.assertEqual(app_test.session_state["fixture_stage2_calls"], [["1216.TW", "1608.TW"]])
        self.assertTrue(any(item.value == "#### 本次優先深入研究" for item in app_test.markdown))
        info = "\n".join(item.value for item in app_test.info)
        self.assertIn("本次比較僅涵蓋已通過初步審查的標的", info)
        self.assertIn("2027.TW 未通過 Stage 1", info)
        text = "\n".join(item.value for item in app_test.markdown)
        self.assertIn("**1216.TW**：先查核營收變化的來源。", text)
        self.assertNotIn("**2027.TW**：", text)
        for expander in app_test.expander[:2]:
            self._assert_acceptance_card_ownership(expander)

    def test_single_validated_card_skips_comparison_with_clear_reason(self):
        app_test = self._run_acceptance_pipeline(1)
        self.assertEqual(app_test.session_state["fixture_stage2_calls"], [])
        self.assertTrue(any("至少需要兩檔" in item.value for item in app_test.info))
        self.assertFalse(any(item.value == "#### 本次優先深入研究" for item in app_test.markdown))
        self.assertFalse(any("清單比較暫時無法完成" in item.value for item in app_test.warning))

    def test_zero_validated_cards_skips_comparison_with_clear_reason(self):
        app_test = self._run_acceptance_pipeline(0)
        self.assertEqual(app_test.session_state["fixture_stage2_calls"], [])
        self.assertTrue(any("尚無標的通過初步審查" in item.value for item in app_test.info))
        self.assertFalse(any(item.value == "#### 本次優先深入研究" for item in app_test.markdown))

    def test_candidate_rows_use_selected_source_and_neutral_symbol_order(self):
        import app as app_module

        rows = app_module.build_research_candidate_rows(
            ("2454.TW", "2330.TW"),
            source_label="Frozen TWSE 研究股票池",
            company_context=company_context(),
        )

        self.assertEqual([row["股票代號"] for row in rows], ["2330.TW", "2454.TW"])
        self.assertTrue(all(row["來源"] == "Frozen TWSE 研究股票池" for row in rows))

    def test_candidate_filter_supports_symbol_company_and_industry(self):
        import app as app_module

        rows = app_module.build_research_candidate_rows(
            ("2330.TW", "2603.TW"),
            source_label="研究股票池 - 測試",
            company_context=company_context(),
        )

        by_company = app_module.filter_research_candidate_rows(rows, query="台積")
        by_industry = app_module.filter_research_candidate_rows(rows, industry="航運業")

        self.assertEqual([row["股票代號"] for row in by_company], ["2330.TW"])
        self.assertEqual([row["股票代號"] for row in by_industry], ["2603.TW"])

    def test_candidate_availability_filter_is_data_presence_only(self):
        import app as app_module

        rows = app_module.build_research_candidate_rows(
            ("2330.TW", "2603.TW"),
            source_label="觀察清單",
            company_context=company_context(),
            research_stock=stock("2330.TW"),
        )

        filtered = app_module.filter_research_candidate_rows(
            rows,
            required_availability=("長期研究",),
        )

        self.assertEqual([row["股票代號"] for row in filtered], ["2330.TW"])
        row_text = str(rows)
        self.assertNotIn("Opportunity Score", row_text)
        self.assertNotIn("Stock Ranking", row_text)
        self.assertNotIn("Buy", row_text)
        self.assertNotIn("Sell", row_text)

    def test_candidate_reason_allows_missing_research_data(self):
        import app as app_module

        row = app_module.build_research_candidate_rows(
            ("2603.TW",),
            source_label="研究股票池 - 測試",
            company_context=company_context(),
        )[0]

        reason = app_module.build_research_candidate_reason(row, industry="航運業")

        self.assertIn("符合航運業產業", reason)
        self.assertIn("尚未建立研究資料", reason)

    def test_candidate_handoff_actions_use_pending_keys_not_target_widget_keys(self):
        import app as app_module

        source = inspect.getsource(app_module.research_candidate_action_buttons)

        self.assertIn("queue_research_symbol_handoff", source)
        self.assertNotIn('["research_input"]', source)
        self.assertNotIn('["historical_trends_input"]', source)
        self.assertNotIn('["ai_research_symbol_input"]', source)
        self.assertNotIn('["swing_research_symbol_input"]', source)
        self.assertNotIn('["swing_research_symbol_source"]', source)
        self.assertNotIn('["comparison_input"]', source)

    def test_candidate_explorer_to_swing_handoff_does_not_mutate_instantiated_widget(self):
        script = """
from pathlib import Path
import sys
import streamlit as st

project_root = Path("/Users/hankmacmini/Documents/Projects/AI-Investment-Research")
src_path = project_root / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import app
import universe_dashboard as universe_ui

app.initialize_session_state()
st.selectbox(
    "股票來源",
    [universe_ui.MANUAL_SOURCE, universe_ui.WATCHLIST_SOURCE],
    key="swing_research_symbol_source",
)
st.text_area("股票池", key="swing_research_symbol_input")
app.research_candidate_action_buttons("2337.TW", key_prefix="handoff_regression")
st.write(st.session_state.get("pending_swing_research_symbol", "NO_PENDING"))
"""
        app_test = AppTest.from_string(script)
        app_test.run()

        self.assertFalse(app_test.exception)
        swing_buttons = [
            button
            for button in app_test.button
            if button.key == "handoff_regression_swing"
        ]
        self.assertEqual(len(swing_buttons), 1)

        swing_buttons[0].click().run()

        self.assertFalse(app_test.exception)
        output_text = "\n".join(str(item.value) for item in app_test.markdown)
        self.assertIn("2337.TW", output_text)

    def test_pending_handoff_consumes_latest_symbol_before_target_widget(self):
        script = """
from pathlib import Path
import sys
import streamlit as st

project_root = Path("/Users/hankmacmini/Documents/Projects/AI-Investment-Research")
src_path = project_root / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import app

app.initialize_session_state()
app.queue_research_symbol_handoff("swing", "2337.TW", rerun=False)
app.queue_research_symbol_handoff("swing", "2454.TW", rerun=False)
app.consume_research_symbol_handoff("swing")
st.text_area("股票池", key="swing_research_symbol_input")
st.write(st.session_state["swing_research_symbol_input"])
"""
        app_test = AppTest.from_string(script)
        app_test.run()

        self.assertFalse(app_test.exception)
        output_text = "\n".join(str(item.value) for item in app_test.markdown)
        self.assertIn("2454.TW", output_text)


def build_rows(**overrides):
    import app as app_module

    defaults = {
        "watchlist_symbols": ["2330.TW"],
        "research_stock": None,
        "historical_stock": None,
        "historical_series": None,
        "ai_research_session": None,
        "swing_research_result": None,
        "comparison_stocks": [],
    }
    defaults.update(overrides)
    return app_module.build_daily_research_overview_rows("2330.TW", **defaults)


def stock(symbol):
    return SimpleNamespace(symbol=symbol)


def company_context():
    return {
        "2330.TW": {
            "company_name": "台積電",
            "broad_industry": "半導體業",
            "classification_as_of_date": "2026-08-20",
            "source": "test",
        },
        "2454.TW": {
            "company_name": "聯發科",
            "broad_industry": "半導體業",
            "classification_as_of_date": "2026-08-20",
            "source": "test",
        },
        "2603.TW": {
            "company_name": "長榮",
            "broad_industry": "航運業",
            "classification_as_of_date": "2026-08-20",
            "source": "test",
        },
    }


def candidate_row(symbol: str) -> dict[str, str]:
    return {
        "股票代號": symbol,
        "公司名稱": "測試公司",
        "產業": "測試產業",
        "長期研究": "尚無資料",
        "歷史趨勢": "尚無資料",
        "AI 研究": "尚無資料",
        "波段研究": "尚無資料",
    }


if __name__ == "__main__":
    unittest.main()
