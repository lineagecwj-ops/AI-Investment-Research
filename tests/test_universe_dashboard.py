import sys
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import ResearchUniverse
from universe_dashboard import LARGE_UNIVERSE_WARNING_THRESHOLD
from universe_dashboard import FROZEN_TWSE_RESEARCH_SOURCE
from universe_dashboard import MANUAL_SOURCE
from universe_dashboard import SAVED_UNIVERSE_SOURCE
from universe_dashboard import SOURCE_OPTIONS
from universe_dashboard import WATCHLIST_SOURCE
from universe_dashboard import build_source_context
from universe_dashboard import frozen_twse_research_source_context
from universe_dashboard import build_universe_form_defaults
from universe_dashboard import format_universe_updated_at
from universe_dashboard import parse_universe_symbol_text
from universe_dashboard import should_warn_large_universe
from universe_dashboard import source_display_name
from universe_dashboard import source_fingerprint
from universe_dashboard import symbols_to_text
from universe_dashboard import universe_selector_label
from universe_dashboard import universe_symbols_fingerprint
from universe_dashboard import validate_form_lengths
from frozen_twse_research_universe_service import FrozenTWSEResearchUniverse


class UniverseDashboardTestCase(unittest.TestCase):

    def universe(self):
        timestamp = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)
        return ResearchUniverse(
            id="u-1",
            name="半導體觀察池",
            description="desc",
            symbols=("2330.TW", "2454.TW", "NVDA"),
            created_at=timestamp,
            updated_at=timestamp,
        )

    def test_parse_symbol_text_accepts_common_separators(self):
        symbols = parse_universe_symbol_text("2330, 2454\nNVDA；AAPL，6488.TWO")

        self.assertEqual(symbols, ("2330.TW", "2454.TW", "NVDA", "AAPL", "6488.TWO"))

    def test_parse_symbol_text_dedupes_first_seen(self):
        symbols = parse_universe_symbol_text("2330\n2330.TW\nNVDA\nnvda")

        self.assertEqual(symbols, ("2330.TW", "NVDA"))

    def test_symbols_to_text_uses_one_symbol_per_line(self):
        self.assertEqual(symbols_to_text(("2330.TW", "NVDA")), "2330.TW\nNVDA")

    def test_universe_selector_label_includes_count(self):
        self.assertEqual(universe_selector_label(self.universe()), "半導體觀察池 (3)")

    def test_format_updated_at_is_json_safe(self):
        self.assertEqual(format_universe_updated_at(self.universe()), "2026-08-08T01:00:00+00:00")

    def test_source_display_name_for_manual_watchlist_and_universe(self):
        self.assertEqual(source_display_name(source_type=MANUAL_SOURCE), "手動輸入")
        self.assertEqual(source_display_name(source_type=WATCHLIST_SOURCE), "觀察清單")
        self.assertEqual(
            source_display_name(source_type=FROZEN_TWSE_RESEARCH_SOURCE),
            "研究股票池（Frozen TWSE 218）",
        )
        self.assertEqual(
            source_display_name(
                source_type=SAVED_UNIVERSE_SOURCE,
                universe_name="AI Server",
            ),
            "已儲存股票池 - AI Server",
        )

    def test_source_options_include_frozen_twse_research_source(self):
        self.assertEqual(
            SOURCE_OPTIONS,
            (
                MANUAL_SOURCE,
                WATCHLIST_SOURCE,
                SAVED_UNIVERSE_SOURCE,
                FROZEN_TWSE_RESEARCH_SOURCE,
            ),
        )

    def test_build_source_context_freezes_symbols(self):
        context = build_source_context(
            source_type=SAVED_UNIVERSE_SOURCE,
            universe_id="u-1",
            universe_name="AI Server",
            symbols=("NVDA", "AAPL"),
        )

        self.assertEqual(context["source_universe_id"], "u-1")
        self.assertEqual(context["source_universe_name"], "AI Server")
        self.assertEqual(context["symbols_copy"], ("NVDA", "AAPL"))
        self.assertEqual(context["symbol_count"], 2)

    def test_frozen_twse_context_uses_read_only_research_identity(self):
        universe = FrozenTWSEResearchUniverse(
            universe_id="frozen_twse_research_universe_2026_08_09",
            universe_version="2026-08-current-etf-constituent-v1",
            symbols=("1101.TW", "2330.TW"),
            frozen_total_count=224,
            twse_count=218,
            tpex_excluded_count=6,
            selection_rule="test",
        )

        context = frozen_twse_research_source_context(universe)

        self.assertEqual(context["source_type"], FROZEN_TWSE_RESEARCH_SOURCE)
        self.assertEqual(context["source_universe_id"], universe.universe_id)
        self.assertEqual(context["source_universe_name"], "研究股票池（Frozen TWSE 218）")
        self.assertEqual(context["symbols_copy"], ("1101.TW", "2330.TW"))
        self.assertEqual(context["symbol_count"], 2)

    def test_symbols_fingerprint_changes_when_content_changes(self):
        first = universe_symbols_fingerprint(("NVDA", "AAPL"))
        second = universe_symbols_fingerprint(("NVDA", "AAPL", "MSFT"))

        self.assertNotEqual(first, second)

    def test_source_fingerprint_changes_when_source_mode_changes(self):
        manual = source_fingerprint(source_type=MANUAL_SOURCE, symbols=("NVDA",))
        saved = source_fingerprint(
            source_type=SAVED_UNIVERSE_SOURCE,
            universe_id="u-1",
            symbols=("NVDA",),
        )

        self.assertNotEqual(manual, saved)

    def test_source_fingerprint_changes_when_universe_content_changes(self):
        first = source_fingerprint(
            source_type=SAVED_UNIVERSE_SOURCE,
            universe_id="u-1",
            symbols=("NVDA",),
        )
        second = source_fingerprint(
            source_type=SAVED_UNIVERSE_SOURCE,
            universe_id="u-1",
            symbols=("NVDA", "AAPL"),
        )

        self.assertNotEqual(first, second)

    def test_build_form_defaults_for_existing_universe(self):
        defaults = build_universe_form_defaults(self.universe())

        self.assertEqual(defaults["name"], "半導體觀察池")
        self.assertEqual(defaults["description"], "desc")
        self.assertEqual(defaults["symbols"], "2330.TW\n2454.TW\nNVDA")

    def test_build_form_defaults_for_empty_create_form(self):
        self.assertEqual(
            build_universe_form_defaults(None),
            {"name": "", "description": "", "symbols": ""},
        )

    def test_large_universe_warning_is_soft_threshold(self):
        self.assertFalse(should_warn_large_universe(tuple(str(i) for i in range(50))))
        self.assertTrue(
            should_warn_large_universe(
                tuple(str(i) for i in range(LARGE_UNIVERSE_WARNING_THRESHOLD + 1))
            )
        )

    def test_validate_form_lengths_reports_name_and_description(self):
        errors = validate_form_lengths("x" * 101, "y" * 501)

        self.assertEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()
