import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database import initialize_database
from universe_service import UniverseAlreadyExistsError
from universe_service import UniverseDataError
from universe_service import UniverseNotFoundError
from universe_service import UniverseValidationError
from universe_service import add_symbols
from universe_service import create_universe
from universe_service import delete_universe
from universe_service import get_universe
from universe_service import list_universes
from universe_service import normalize_universe_symbols
from universe_service import remove_symbols
from universe_service import replace_symbols
from universe_service import update_universe


class UniverseServiceTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        self.created_at = datetime(2026, 8, 8, 1, 0, tzinfo=UTC)
        self.updated_at = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initialize_database_creates_universe_tables(self):
        initialize_database(self.db_path)

        connection = sqlite3.connect(self.db_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        finally:
            connection.close()

        self.assertIn("research_universes", tables)
        self.assertIn("research_universe_symbols", tables)

    def test_repeated_initialize_is_idempotent_for_universe_tables(self):
        initialize_database(self.db_path)
        initialize_database(self.db_path)

        self.assertEqual(list_universes(db_path=self.db_path), [])

    def test_create_universe_without_symbols_is_allowed(self):
        universe = create_universe(
            name="  測試波段池  ",
            symbols=[],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        self.assertEqual(universe.id, "u-1")
        self.assertEqual(universe.name, "測試波段池")
        self.assertEqual(universe.symbols, tuple())
        self.assertEqual(universe.symbol_count, 0)

    def test_create_universe_with_symbols_normalizes_and_dedupes_first_seen_order(self):
        universe = create_universe(
            name="Semis",
            symbols=["2330", "2330.TW", "NVDA", "6488.TWO", "nvda"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        self.assertEqual(universe.symbols, ("2330.TW", "NVDA", "6488.TWO"))

    def test_get_universe_reads_persisted_uuid_without_rebuilding(self):
        created = create_universe(
            name="AI Server",
            symbols=["NVDA"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "stable-id",
        )

        loaded = get_universe(created.id, db_path=self.db_path)

        self.assertEqual(loaded.id, "stable-id")
        self.assertEqual(loaded.symbols, ("NVDA",))

    def test_list_universes_is_name_ascending(self):
        create_universe(
            name="z list",
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-z",
        )
        create_universe(
            name="A list",
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-a",
        )

        self.assertEqual(
            [universe.name for universe in list_universes(db_path=self.db_path)],
            ["A list", "z list"],
        )

    def test_update_universe_renames_and_updates_description(self):
        created = create_universe(
            name="Old",
            description="old desc",
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        updated = update_universe(
            created.id,
            name="New",
            description="new desc",
            db_path=self.db_path,
            now=self.updated_at,
        )

        self.assertEqual(updated.name, "New")
        self.assertEqual(updated.description, "new desc")
        self.assertEqual(updated.created_at, self.created_at)
        self.assertEqual(updated.updated_at, self.updated_at)

    def test_replace_symbols_preserves_new_order(self):
        created = create_universe(
            name="Pool",
            symbols=["NVDA", "AAPL"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        updated = replace_symbols(
            created.id,
            ["2330", "NVDA"],
            db_path=self.db_path,
            now=self.updated_at,
        )

        self.assertEqual(updated.symbols, ("2330.TW", "NVDA"))

    def test_add_symbols_appends_new_symbols_only(self):
        created = create_universe(
            name="Pool",
            symbols=["2330"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        updated = add_symbols(
            created.id,
            ["2330.TW", "2454", "NVDA"],
            db_path=self.db_path,
            now=self.updated_at,
        )

        self.assertEqual(updated.symbols, ("2330.TW", "2454.TW", "NVDA"))

    def test_remove_symbols_removes_normalized_matches(self):
        created = create_universe(
            name="Pool",
            symbols=["2330", "2454", "NVDA"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        updated = remove_symbols(
            created.id,
            ["2330.TW", "NVDA"],
            db_path=self.db_path,
            now=self.updated_at,
        )

        self.assertEqual(updated.symbols, ("2454.TW",))

    def test_delete_universe_deletes_symbols_explicitly(self):
        created = create_universe(
            name="Pool",
            symbols=["2330", "NVDA"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        delete_universe(created.id, db_path=self.db_path)

        with self.assertRaises(UniverseNotFoundError):
            get_universe(created.id, db_path=self.db_path)
        connection = sqlite3.connect(self.db_path)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM research_universe_symbols"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 0)

    def test_duplicate_name_case_insensitive_is_rejected(self):
        create_universe(
            name="AI Server",
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        with self.assertRaises(UniverseAlreadyExistsError):
            create_universe(
                name="ai server",
                db_path=self.db_path,
                now=self.created_at,
                id_factory=lambda: "u-2",
            )

    def test_rename_to_existing_name_is_rejected(self):
        create_universe(
            name="A",
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-a",
        )
        second = create_universe(
            name="B",
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-b",
        )

        with self.assertRaises(UniverseAlreadyExistsError):
            update_universe(second.id, name="a", db_path=self.db_path)

    def test_blank_name_is_rejected(self):
        with self.assertRaises(UniverseValidationError):
            create_universe(name="   ", db_path=self.db_path)

    def test_long_name_is_rejected(self):
        with self.assertRaises(UniverseValidationError):
            create_universe(name="x" * 101, db_path=self.db_path)

    def test_long_description_is_rejected(self):
        with self.assertRaises(UniverseValidationError):
            create_universe(name="Pool", description="x" * 501, db_path=self.db_path)

    def test_unknown_get_update_delete_raise_not_found(self):
        with self.assertRaises(UniverseNotFoundError):
            get_universe("missing", db_path=self.db_path)
        with self.assertRaises(UniverseNotFoundError):
            update_universe("missing", name="x", db_path=self.db_path)
        with self.assertRaises(UniverseNotFoundError):
            delete_universe("missing", db_path=self.db_path)

    def test_normalize_universe_symbols_keeps_multi_market(self):
        self.assertEqual(
            normalize_universe_symbols(["2330", "6488.TWO", "NVDA", "AAPL"]),
            ("2330.TW", "6488.TWO", "NVDA", "AAPL"),
        )

    def test_read_rejects_duplicate_positions(self):
        create_universe(
            name="Pool",
            symbols=["2330", "NVDA"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "UPDATE research_universe_symbols SET position = 0 WHERE symbol = ?",
                ("NVDA",),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(UniverseDataError):
            get_universe("u-1", db_path=self.db_path)

    def test_read_rejects_position_gaps(self):
        create_universe(
            name="Pool",
            symbols=["2330", "NVDA"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "UPDATE research_universe_symbols SET position = 3 WHERE symbol = ?",
                ("NVDA",),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(UniverseDataError):
            get_universe("u-1", db_path=self.db_path)

    def test_read_rejects_malformed_symbol(self):
        create_universe(
            name="Pool",
            symbols=["NVDA"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "UPDATE research_universe_symbols SET symbol = ?",
                ("nvda",),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(UniverseDataError):
            get_universe("u-1", db_path=self.db_path)

    def test_created_at_stays_stable_when_symbols_change(self):
        created = create_universe(
            name="Pool",
            symbols=["NVDA"],
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        updated = add_symbols(
            created.id,
            ["AAPL"],
            db_path=self.db_path,
            now=self.updated_at,
        )

        self.assertEqual(updated.created_at, self.created_at)
        self.assertEqual(updated.updated_at, self.updated_at)

    def test_description_can_be_cleared_to_none(self):
        created = create_universe(
            name="Pool",
            description="desc",
            db_path=self.db_path,
            now=self.created_at,
            id_factory=lambda: "u-1",
        )

        updated = update_universe(
            created.id,
            description="   ",
            db_path=self.db_path,
            now=self.updated_at,
        )

        self.assertIsNone(updated.description)


if __name__ == "__main__":
    unittest.main()
