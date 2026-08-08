import ast
import importlib
import subprocess
import sys
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

def app():
    from app import render_swing_technical_condition_detail
    from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
    from signal_outcome_service import evaluate_signal_conditions
    from tests.test_swing_research_dashboard import SwingResearchDashboardTestCase

    case = SwingResearchDashboardTestCase()
    signal_match = evaluate_signal_conditions(
        case.snapshot(
            symbol="2330.TW",
            volume_ratio_20=1.08,
            distance_to_prior_60d_high=-0.072,
        ),
        TECHNICAL_EXAMPLE_SIGNAL_V1,
    )
    result = case.result(
        current_signal_details=(signal_match,),
        no_match_symbols=("2330.TW",),
    )
    render_swing_technical_condition_detail(result)


def stale_result_app():
    from app import render_swing_technical_condition_detail
    from tests.test_swing_research_dashboard import SwingResearchDashboardTestCase

    case = SwingResearchDashboardTestCase()
    render_swing_technical_condition_detail(
        case.legacy_result_without_current_signal_details()
    )


def stale_current_result_app():
    from app import render_swing_research_result
    from tests.test_swing_research_dashboard import SwingResearchDashboardTestCase

    case = SwingResearchDashboardTestCase()
    render_swing_research_result(case.legacy_result_without_current_signal_details())


def stale_detail_view_schema_app():
    import app as app_module
    import importlib
    from dataclasses import dataclass
    from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
    from signal_outcome_service import evaluate_signal_conditions
    from tests.test_swing_research_dashboard import SwingResearchDashboardTestCase

    @dataclass(frozen=True)
    class LegacyTechnicalConditionDetailView:
        signal_match: object
        matched_count: int
        total_count: int
        condition_rows: list
        category_rows: list
        visualization_rows: list

    case = SwingResearchDashboardTestCase()
    signal_match = evaluate_signal_conditions(
        case.snapshot(
            symbol="2330.TW",
            volume_ratio_20=0.64,
            rsi_14=50.6,
            distance_to_prior_60d_high=-0.0651,
        ),
        TECHNICAL_EXAMPLE_SIGNAL_V1,
    )
    result = case.result(
        current_signal_details=(signal_match,),
        no_match_symbols=("2330.TW",),
    )
    original_builder = app_module.swing_dashboard.build_technical_condition_detail_view

    def legacy_builder(selected_match):
        fresh = original_builder(selected_match)
        return LegacyTechnicalConditionDetailView(
            signal_match=fresh.signal_match,
            matched_count=fresh.matched_count,
            total_count=fresh.total_count,
            condition_rows=fresh.condition_rows,
            category_rows=fresh.category_rows,
            visualization_rows=fresh.visualization_rows,
        )

    app_module.swing_dashboard.build_technical_condition_detail_view = legacy_builder
    try:
        app_module.render_swing_technical_condition_detail(result)
    finally:
        app_module.swing_dashboard = importlib.reload(app_module.swing_dashboard)


class SwingTechnicalConditionDetailAppTestCase(unittest.TestCase):

    def test_detail_renderer_smoke_has_selector_table_and_chart(self):
        at = AppTest.from_function(app)

        at.run(timeout=10)

        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.selectbox), 1)
        self.assertGreaterEqual(len(at.dataframe), 2)

    def test_fresh_detail_view_schema_has_beginner_visual_specs(self):
        import app as app_module
        from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
        from signal_outcome_service import evaluate_signal_conditions
        from tests.test_swing_research_dashboard import SwingResearchDashboardTestCase

        case = SwingResearchDashboardTestCase()
        signal_match = evaluate_signal_conditions(
            case.snapshot(symbol="2330.TW"),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

        detail = app_module.ensure_current_technical_detail_view(signal_match)

        self.assertTrue(hasattr(detail, "visual_specs"))
        self.assertEqual(
            [spec.title for spec in detail.visual_specs],
            ["成交量活躍度", "RSI 動能", "接近前高程度"],
        )

    def test_stale_detail_view_schema_rebuilds_without_attribute_error(self):
        at = AppTest.from_function(stale_detail_view_schema_app)

        at.run(timeout=10)

        self.assertEqual(len(at.exception), 0)
        markdown_text = "\n".join(item.value for item in at.markdown)
        self.assertIn("成交量活躍度", markdown_text)
        self.assertIn("RSI 動能", markdown_text)
        self.assertIn("接近前高程度", markdown_text)

    def test_stale_result_renderer_shows_rescan_prompt_without_crash(self):
        at = AppTest.from_function(stale_result_app)

        at.run(timeout=10)

        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.selectbox), 0)
        self.assertTrue(
            any("請重新執行一次波段掃描以產生完整明細" in item.value for item in at.info)
        )

    def test_stale_current_result_keeps_scan_summary_and_detail_prompt(self):
        at = AppTest.from_function(stale_current_result_app)

        at.run(timeout=10)

        self.assertEqual(len(at.exception), 0)
        self.assertGreaterEqual(len(at.metric), 5)
        self.assertTrue(
            any("請重新執行一次波段掃描以產生完整明細" in item.value for item in at.info)
        )

    def test_render_contract_covers_all_swing_dashboard_references(self):
        import app as app_module

        source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        render_function = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "render_swing_technical_condition_detail"
        )
        references = {
            node.attr
            for node in ast.walk(render_function)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "swing_dashboard"
        }

        self.assertTrue(references.issubset(set(app_module.SWING_TECHNICAL_DETAIL_REQUIRED_ATTRIBUTES)))

    def test_view_schema_contract_requires_visual_specs(self):
        import app as app_module
        import swing_research_dashboard

        try:
            stale_fields = dict(swing_research_dashboard.TechnicalConditionDetailView.__dataclass_fields__)
            stale_fields.pop("visual_specs")
            swing_research_dashboard.TechnicalConditionDetailView.__dataclass_fields__ = stale_fields

            app_module.ensure_swing_technical_detail_contract()

            self.assertIn(
                "visual_specs",
                app_module.swing_dashboard.TechnicalConditionDetailView.__dataclass_fields__,
            )
        finally:
            importlib.reload(swing_research_dashboard)
            app_module.swing_dashboard = swing_research_dashboard

    def test_render_contract_recovers_stale_helper_module(self):
        import app as app_module
        import swing_research_dashboard

        try:
            delattr(swing_research_dashboard, "TECHNICAL_DETAIL_CAPTION")

            app_module.ensure_swing_technical_detail_contract()

            self.assertTrue(hasattr(app_module.swing_dashboard, "TECHNICAL_DETAIL_CAPTION"))
        finally:
            importlib.reload(swing_research_dashboard)
            app_module.swing_dashboard = swing_research_dashboard

    def test_current_scan_contract_recovers_stale_scanner_module_schema(self):
        script = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
sys.path.insert(0, str(Path('src').resolve()))
import app
import swing_scanner_service
stale_fields = dict(swing_scanner_service.SwingScannerResult.__dataclass_fields__)
stale_fields.pop('current_signal_details')
swing_scanner_service.SwingScannerResult.__dataclass_fields__ = stale_fields
app.ensure_swing_scanner_result_contract()
assert 'current_signal_details' in app.swing_scanner_module.SwingScannerResult.__dataclass_fields__
assert app.SwingScannerService is app.swing_scanner_module.SwingScannerService
assert app.swing_dashboard.SwingScannerResult is app.swing_scanner_module.SwingScannerResult
print('ok')
"""

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("ok", completed.stdout)


if __name__ == "__main__":
    unittest.main()
