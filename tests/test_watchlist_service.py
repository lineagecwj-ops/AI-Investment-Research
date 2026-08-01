import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from watchlist_service import add_stock
from watchlist_service import list_watchlist
from watchlist_service import remove_stock


class WatchlistServiceTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.watchlist_path = Path(self.temp_dir.name) / "watchlist.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_file_returns_empty_watchlist(self):
        self.assertEqual(list_watchlist(self.watchlist_path), [])

    def test_add_stock_normalizes_and_persists(self):
        added = add_stock("2330", self.watchlist_path)

        self.assertTrue(added)
        self.assertEqual(list_watchlist(self.watchlist_path), ["2330.TW"])

    def test_duplicate_add_does_not_duplicate_item(self):
        self.assertTrue(add_stock("nvda", self.watchlist_path))
        self.assertFalse(add_stock("NVDA", self.watchlist_path))

        self.assertEqual(list_watchlist(self.watchlist_path), ["NVDA"])

    def test_remove_stock(self):
        add_stock("2330", self.watchlist_path)

        removed = remove_stock("2330.TW", self.watchlist_path)

        self.assertTrue(removed)
        self.assertEqual(list_watchlist(self.watchlist_path), [])

    def test_remove_missing_stock_returns_false(self):
        self.assertFalse(remove_stock("AAPL", self.watchlist_path))

    def test_empty_file_is_handled_as_empty_watchlist(self):
        self.watchlist_path.write_text("", encoding="utf-8")

        self.assertEqual(list_watchlist(self.watchlist_path), [])

    def test_invalid_json_is_handled_as_empty_watchlist(self):
        self.watchlist_path.write_text("{invalid", encoding="utf-8")

        self.assertEqual(list_watchlist(self.watchlist_path), [])

    def test_non_list_json_is_handled_as_empty_watchlist(self):
        self.watchlist_path.write_text('{"symbol": "NVDA"}', encoding="utf-8")

        self.assertEqual(list_watchlist(self.watchlist_path), [])


if __name__ == "__main__":
    unittest.main()
