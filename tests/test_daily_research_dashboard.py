import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


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
    ):
        app_module.initialize_session_state()
        app_module.render_daily_research_dashboard()


class DailyResearchDashboardTestCase(unittest.TestCase):

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


if __name__ == "__main__":
    unittest.main()
