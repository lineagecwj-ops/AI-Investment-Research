import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database import DEFAULT_DB_PATH
from etf_constituent_universe_service import UNIVERSE_VERSION
from frozen_twse_research_universe_service import FROZEN_TPEX_EXCLUDED_COUNT
from frozen_twse_research_universe_service import FROZEN_TAIWAN_TOTAL_COUNT
from frozen_twse_research_universe_service import FROZEN_TWSE_RESEARCH_SYMBOL_COUNT
from frozen_twse_research_universe_service import FrozenTWSEResearchUniverseError
from frozen_twse_research_universe_service import load_frozen_twse_research_symbols
from frozen_twse_research_universe_service import load_frozen_twse_research_universe


class FrozenTWSEResearchUniverseServiceTestCase(unittest.TestCase):

    def test_repository_loader_returns_valid_frozen_twse_symbols(self):
        universe = load_frozen_twse_research_universe(db_path=DEFAULT_DB_PATH)

        self.assertEqual(universe.universe_version, UNIVERSE_VERSION)
        self.assertEqual(universe.frozen_total_count, FROZEN_TAIWAN_TOTAL_COUNT)
        self.assertEqual(universe.twse_count, FROZEN_TWSE_RESEARCH_SYMBOL_COUNT)
        self.assertEqual(universe.tpex_excluded_count, FROZEN_TPEX_EXCLUDED_COUNT)
        self.assertEqual(len(universe.symbols), 218)
        self.assertEqual(len(set(universe.symbols)), 218)
        self.assertEqual(tuple(sorted(universe.symbols)), universe.symbols)
        self.assertTrue(all(symbol.endswith(".TW") for symbol in universe.symbols))
        self.assertFalse(any(symbol.endswith(".TWO") for symbol in universe.symbols))
        self.assertNotIn("AAPL", universe.symbols)
        self.assertNotIn("NVDA", universe.symbols)
        self.assertNotIn("0050.TW", universe.symbols)

    def test_symbol_loader_returns_canonical_symbol_tuple(self):
        self.assertEqual(
            load_frozen_twse_research_symbols(db_path=DEFAULT_DB_PATH),
            load_frozen_twse_research_universe(db_path=DEFAULT_DB_PATH).symbols,
        )

    def test_wrong_count_fails_deterministically(self):
        with self.assertRaisesRegex(FrozenTWSEResearchUniverseError, "必須包含 218 檔"):
            load_frozen_twse_research_symbols(
                symbol_loader=lambda _db_path: ("1101.TW",),
            )

    def test_missing_artifact_fails_deterministically(self):
        with self.assertRaisesRegex(FrozenTWSEResearchUniverseError, "artifact 無法讀取"):
            load_frozen_twse_research_symbols(
                db_path=PROJECT_ROOT / "data" / "missing.db",
            )

    def test_duplicate_symbol_fails_deterministically(self):
        symbols = tuple(f"{1101 + index:04d}.TW" for index in range(217)) + ("1101.TW",)

        with self.assertRaisesRegex(FrozenTWSEResearchUniverseError, "重複股票代號"):
            load_frozen_twse_research_symbols(symbol_loader=lambda _db_path: symbols)

    def test_invalid_market_or_non_taiwan_symbol_fails_deterministically(self):
        symbols = tuple(f"{1101 + index:04d}.TW" for index in range(217)) + ("6488.TWO",)

        with self.assertRaisesRegex(FrozenTWSEResearchUniverseError, "非 TWSE common-stock"):
            load_frozen_twse_research_symbols(symbol_loader=lambda _db_path: symbols)

    def test_non_deterministic_order_fails_deterministically(self):
        symbols = tuple(f"{1101 + index:04d}.TW" for index in range(218))
        unordered = symbols[1:] + symbols[:1]

        with self.assertRaisesRegex(FrozenTWSEResearchUniverseError, "deterministic ascending order"):
            load_frozen_twse_research_symbols(symbol_loader=lambda _db_path: unordered)


if __name__ == "__main__":
    unittest.main()
