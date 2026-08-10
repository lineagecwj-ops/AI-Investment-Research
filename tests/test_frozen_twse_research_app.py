import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from frozen_twse_research_universe_service import FrozenTWSEResearchUniverse
from frozen_twse_research_universe_service import FrozenTWSEResearchUniverseError
import universe_dashboard as universe_ui


class FrozenTWSEResearchAppTestCase(unittest.TestCase):

    def frozen_universe(self):
        return FrozenTWSEResearchUniverse(
            universe_id="frozen_twse_research_universe_2026_08_09",
            universe_version="2026-08-current-etf-constituent-v1",
            symbols=("1101.TW", "2330.TW"),
            frozen_total_count=224,
            twse_count=218,
            tpex_excluded_count=6,
            selection_rule="test",
        )

    def test_frozen_source_resolves_to_loader_symbols_without_manual_parsing(self):
        import app

        with patch("app.universe_ui.load_frozen_twse_research_source", return_value=self.frozen_universe()) as loader:
            symbols, context = app.resolve_swing_research_source(
                source_type=universe_ui.FROZEN_TWSE_RESEARCH_SOURCE,
                input_symbols="NVDA",
                watchlist_symbols=["AAPL"],
                selected_universe=None,
            )

        loader.assert_called_once_with()
        self.assertEqual(symbols, ("1101.TW", "2330.TW"))
        self.assertEqual(context["source_type"], universe_ui.FROZEN_TWSE_RESEARCH_SOURCE)
        self.assertEqual(context["source_universe_id"], "frozen_twse_research_universe_2026_08_09")
        self.assertEqual(context["symbol_count"], 2)

    def test_existing_sources_do_not_call_frozen_loader(self):
        import app
        from models import ResearchUniverse
        from datetime import UTC
        from datetime import datetime

        saved = ResearchUniverse(
            id="u-1",
            name="Pool",
            description=None,
            symbols=("2454.TW",),
            created_at=datetime(2026, 8, 8, tzinfo=UTC),
            updated_at=datetime(2026, 8, 8, tzinfo=UTC),
        )

        with patch("app.universe_ui.load_frozen_twse_research_source") as loader:
            manual, _ = app.resolve_swing_research_source(
                source_type=universe_ui.MANUAL_SOURCE,
                input_symbols="2330 NVDA 6488.TWO",
                watchlist_symbols=["1101.TW"],
                selected_universe=saved,
            )
            watchlist, _ = app.resolve_swing_research_source(
                source_type=universe_ui.WATCHLIST_SOURCE,
                input_symbols="2330",
                watchlist_symbols=["1101.TW"],
                selected_universe=saved,
            )
            saved_symbols, _ = app.resolve_swing_research_source(
                source_type=universe_ui.SAVED_UNIVERSE_SOURCE,
                input_symbols="2330",
                watchlist_symbols=["1101.TW"],
                selected_universe=saved,
            )

        loader.assert_not_called()
        self.assertEqual(manual, ("2330.TW", "NVDA", "6488.TWO"))
        self.assertEqual(watchlist, ("1101.TW",))
        self.assertEqual(saved_symbols, ("2454.TW",))

    def test_frozen_source_failure_is_not_swallowed_by_source_resolver(self):
        import app

        with patch(
            "app.universe_ui.load_frozen_twse_research_source",
            side_effect=FrozenTWSEResearchUniverseError("研究股票池資料驗證失敗"),
        ):
            with self.assertRaises(FrozenTWSEResearchUniverseError):
                app.resolve_swing_research_source(
                    source_type=universe_ui.FROZEN_TWSE_RESEARCH_SOURCE,
                    input_symbols="2330",
                    watchlist_symbols=["1101.TW"],
                    selected_universe=None,
                )


if __name__ == "__main__":
    unittest.main()
