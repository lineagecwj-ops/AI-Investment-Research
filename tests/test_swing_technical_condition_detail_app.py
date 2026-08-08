import ast
import importlib
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


class SwingTechnicalConditionDetailAppTestCase(unittest.TestCase):

    def test_detail_renderer_smoke_has_selector_table_and_chart(self):
        at = AppTest.from_function(app)

        at.run(timeout=10)

        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.selectbox), 1)
        self.assertGreaterEqual(len(at.dataframe), 2)

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

        self.assertEqual(
            references,
            set(app_module.SWING_TECHNICAL_DETAIL_REQUIRED_ATTRIBUTES),
        )

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


if __name__ == "__main__":
    unittest.main()
