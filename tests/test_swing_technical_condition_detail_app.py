import ast
import copy
import inspect
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


def historical_condition_dashboard_app():
    import streamlit as st
    import app as app_module
    from tests.test_swing_research_dashboard import HistoricalConditionDashboardPresentationTestCase

    case = HistoricalConditionDashboardPresentationTestCase()
    diagnostics_result = case.diagnostics_result()
    comparison_result = case.comparison_result()
    fingerprint = app_module.swing_dashboard.build_historical_condition_dashboard_fingerprint(
        symbols=("2330.TW", "0050.TW", "2337.TW", "2404.TW", "2454.TW"),
        start_date=diagnostics_result.config.start_date,
        end_date=diagnostics_result.config.end_date,
        signal_id=diagnostics_result.config.signal_definition.id,
        outcome_id=comparison_result.config.outcome_definition.id,
        warmup_trading_bars=comparison_result.config.warmup_trading_bars,
        outcome_horizon_bars=comparison_result.config.outcome_definition.horizon_bars,
    )
    st.session_state["historical_condition_dashboard_payload"] = {
        "diagnostics_result": diagnostics_result,
        "outcome_comparison_result": comparison_result,
        "fingerprint": fingerprint,
        "symbols": ("2330.TW",),
        "start_date": diagnostics_result.config.start_date,
        "end_date": diagnostics_result.config.end_date,
    }
    st.session_state["historical_condition_dashboard_fingerprint"] = fingerprint
    st.session_state["historical_condition_dashboard_last_error"] = None
    st.session_state["historical_condition_dashboard_error_details"] = None
    app_module.render_historical_condition_dashboard()


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

    def test_historical_condition_dashboard_beginner_ui_smoke(self):
        at = AppTest.from_function(historical_condition_dashboard_app)

        at.run(timeout=10)

        text = " ".join(
            str(item.value)
            for collection in (at.markdown, at.caption, at.info, at.button, at.selectbox)
            for item in collection
        )
        self.assertEqual(len(at.exception), 0)
        self.assertIn("V1 歷史條件診斷", text)
        self.assertIn("不是未來上漲機率，也不是買進建議", text)
        self.assertIn("執行 V1 歷史診斷", [button.label for button in at.button])
        self.assertIn("V1 條件有效性總覽", text)
        self.assertIn("哪些條件最常造成差異", text)
        self.assertIn("哪些 V1 條件本來就比較難符合", text)
        self.assertGreaterEqual(len(at.dataframe), 3)

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

    def test_visual_panel_html_uses_compact_beginner_bar_layout(self):
        import app as app_module
        from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
        from signal_outcome_service import evaluate_signal_conditions
        from tests.test_swing_research_dashboard import SwingResearchDashboardTestCase

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
        detail = app_module.ensure_current_technical_detail_view(signal_match)

        html = app_module.build_technical_condition_visual_panel_html(detail.visual_specs)

        self.assertIn("technical-visual-panel", html)
        self.assertIn("var(--secondary-background-color", html)
        self.assertNotIn("background: #050505", html)
        self.assertNotIn("color: #f8fafc", html)
        self.assertIn("成交量活躍度", html)
        self.assertIn("<strong>0.64</strong>", html)
        self.assertIn("1.20 門檻", html)
        self.assertIn("尚差 <strong>0.56</strong> 才達到 V1 要求", html)
        self.assertIn("RSI 動能", html)
        self.assertIn("<strong>50.6</strong>", html)
        self.assertIn("70", html)
        self.assertIn("接近前高程度", html)
        self.assertIn("<strong>-6.51%</strong>", html)
        self.assertIn("-5% 門檻", html)
        self.assertIn("✕ 尚未符合", html)
        self.assertIn("✓ 符合", html)

    def test_visual_marker_position_helper_clamps_display_only(self):
        import app as app_module

        self.assertEqual(app_module._technical_visual_position(0.0, (0.0, 10.0)), 0.0)
        self.assertEqual(app_module._technical_visual_position(10.0, (0.0, 10.0)), 100.0)
        self.assertEqual(app_module._technical_visual_position(5.0, (0.0, 10.0)), 50.0)
        self.assertEqual(app_module._technical_visual_position(-5.0, (0.0, 10.0)), 0.0)
        self.assertEqual(app_module._technical_visual_position(15.0, (0.0, 10.0)), 100.0)

    def test_visual_marker_positions_use_dynamic_domains(self):
        import app as app_module
        from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
        from signal_outcome_service import evaluate_signal_conditions
        from tests.test_swing_research_dashboard import SwingResearchDashboardTestCase

        case = SwingResearchDashboardTestCase()
        signal_match = evaluate_signal_conditions(
            case.snapshot(
                symbol="DYNAMIC",
                volume_ratio_20=0.64,
                rsi_14=50.6,
                distance_to_prior_60d_high=-0.0651,
            ),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )
        detail = app_module.ensure_current_technical_detail_view(signal_match)

        volume, rsi, distance = detail.visual_specs

        self.assertAlmostEqual(
            app_module._technical_visual_position(0.64, volume.x_domain),
            42.6667,
            places=2,
        )
        self.assertAlmostEqual(
            app_module._technical_visual_position(50.6, rsi.x_domain),
            50.6,
            places=2,
        )
        self.assertAlmostEqual(
            app_module._technical_visual_position(-6.51, distance.x_domain),
            34.9,
            places=2,
        )

    def test_visual_panel_handles_scale_regression_values(self):
        import app as app_module
        from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
        from signal_outcome_service import evaluate_signal_conditions
        from tests.test_swing_research_dashboard import SwingResearchDashboardTestCase

        case = SwingResearchDashboardTestCase()
        scenarios = [
            {"volume_ratio_20": value}
            for value in (0.3, 0.64, 1.2, 1.8, 3.0)
        ] + [
            {"rsi_14": value}
            for value in (20, 50, 50.6, 70, 85)
        ] + [
            {"distance_to_prior_60d_high": value}
            for value in (-0.25, -0.10, -0.0651, -0.05, 0.0, 0.03)
        ]

        for values in scenarios:
            with self.subTest(values=values):
                signal_match = evaluate_signal_conditions(
                    case.snapshot(symbol="SCALE", **values),
                    TECHNICAL_EXAMPLE_SIGNAL_V1,
                )
                detail = app_module.ensure_current_technical_detail_view(signal_match)
                html = app_module.build_technical_condition_visual_panel_html(detail.visual_specs)

                self.assertIn("technical-visual-dot", html)
                self.assertIn("1.20 門檻", html)
                self.assertIn("-5% 門檻", html)
                self.assertIn("left:", html)

    def test_visual_panel_escapes_dynamic_html_text(self):
        import app as app_module
        from swing_research_dashboard import TechnicalConditionVisualSpec

        spec = TechnicalConditionVisualSpec(
            title='成交量活躍度<img src=x onerror=alert(1)>',
            explanation='<script>alert("x")</script>',
            status_label='尚未符合<script>',
            status_value="fail",
            current_label='<b>0.64</b>',
            threshold_label='<i>V1 門檻 1.20</i>',
            gap_text='目前 <img src=x onerror=alert(1)> 尚差 0.56。',
            x_domain=(0.0, 1.5),
            marker_rows=[
                {
                    "指標": "成交量活躍度",
                    "標記": "目前值",
                    "數值": 0.64,
                    "說明": '<b>0.64</b>',
                    "狀態": "尚未符合",
                }
            ],
            range_rows=[],
        )

        html = app_module.build_technical_condition_visual_panel_html([spec])

        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<b>0.64</b>", html)
        self.assertIn("&lt;b&gt;0.64&lt;/b&gt;", html)
        self.assertIn("&lt;script&gt;", html)

    def test_visual_panel_handles_missing_current_marker(self):
        import app as app_module
        from swing_research_dashboard import TechnicalConditionVisualSpec

        spec = TechnicalConditionVisualSpec(
            title="成交量活躍度",
            explanation="缺值測試",
            status_label="尚未符合",
            status_value="fail",
            current_label="N/A",
            threshold_label="V1 門檻 1.20",
            gap_text="目前沒有足夠資料顯示此指標。",
            x_domain=(0.0, 1.5),
            marker_rows=[
                {
                    "指標": "成交量活躍度",
                    "標記": "V1 門檻",
                    "數值": 1.2,
                    "說明": "1.20",
                    "狀態": "尚未符合",
                }
            ],
            range_rows=[],
        )

        html = app_module.build_technical_condition_visual_panel_html([spec])

        self.assertIn("<strong>N/A</strong>", html)
        self.assertNotIn('<span class="technical-visual-dot"', html)
        self.assertIn("technical-visual-tick", html)

    def test_visual_helper_has_no_hard_coded_sample_symbol_or_values(self):
        import app as app_module

        helper_source = "\n".join(
            inspect.getsource(function)
            for function in (
                app_module.build_technical_condition_visual_panel_html,
                app_module._technical_condition_visual_row_html,
                app_module._technical_visual_current_html,
                app_module._technical_visual_gap_html,
            )
        )

        self.assertNotIn("2330", helper_source)
        self.assertNotIn("0.64", helper_source)
        self.assertNotIn("50.6", helper_source)
        self.assertNotIn("-6.51", helper_source)

    def test_visual_render_does_not_mutate_visual_specs(self):
        import app as app_module
        from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
        from signal_outcome_service import evaluate_signal_conditions
        from tests.test_swing_research_dashboard import SwingResearchDashboardTestCase

        case = SwingResearchDashboardTestCase()
        signal_match = evaluate_signal_conditions(
            case.snapshot(symbol="IMMUTABLE", volume_ratio_20=1.8, rsi_14=70, distance_to_prior_60d_high=0.03),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )
        detail = app_module.ensure_current_technical_detail_view(signal_match)
        before = copy.deepcopy(detail.visual_specs)

        app_module.build_technical_condition_visual_panel_html(detail.visual_specs)

        self.assertEqual(detail.visual_specs, before)

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
