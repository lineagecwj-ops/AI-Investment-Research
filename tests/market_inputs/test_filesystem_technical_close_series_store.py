import json
import os
import hashlib
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import FilesystemTechnicalCloseSeriesStore
from market_inputs import MarketArtifactCorruptionError
from market_inputs import MarketArtifactSaveStatus
from market_inputs import MarketArtifactStoreError
from market_inputs import ProductionMarketInputConfig
from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseObservation
from market_inputs import TechnicalCloseObservationSeries
from market_inputs import TechnicalCloseObservationSeriesCodec
from market_inputs import TechnicalCloseSeriesArtifactIdentity
from market_inputs import TechnicalCloseSeriesStore
from market_inputs import TECHNICAL_CLOSE_OBSERVATION_PRODUCER_VERSION_V1
from market_inputs import YAHOO_FINANCE_PROVIDER_ID_V1
from market_inputs import YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1


class FilesystemTechnicalCloseSeriesStoreTestCase(unittest.TestCase):

    def observation(self, market_session_date=date(2026, 8, 14), technical_close=100.25):
        return TechnicalCloseObservation(
            market_session_date=market_session_date,
            technical_close=technical_close,
        )

    def series(self, **overrides):
        values = {
            "symbol": "2330.TW",
            "provider": YAHOO_FINANCE_PROVIDER_ID_V1,
            "provider_symbol": "2330.TW",
            "timezone": "Asia/Taipei",
            "close_basis": TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            "valuation_date": date(2026, 8, 14),
            "observations": (
                self.observation(date(2026, 8, 12), 98.0),
                self.observation(date(2026, 8, 13), 99.5),
                self.observation(date(2026, 8, 14), 100.25),
            ),
            "fetched_at": datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
        }
        values.update(overrides)
        return TechnicalCloseObservationSeries(**values)

    def config(self, project_root):
        return ProductionMarketInputConfig.from_project_root(project_root)

    def store(self, project_root):
        return FilesystemTechnicalCloseSeriesStore(self.config(project_root))

    def identity(self, series):
        return TechnicalCloseSeriesArtifactIdentity.from_series(series)

    def final_path(self, project_root, series):
        config = self.config(project_root)
        return config.artifact_path(self.identity(series))

    def test_protocol_conformance_and_constructor_no_mkdir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config(temp_dir)
            store = FilesystemTechnicalCloseSeriesStore(config)

            self.assertIsInstance(store, TechnicalCloseSeriesStore)
            self.assertFalse(config.artifact_root.exists())

    def test_get_missing_root_returns_none_without_mkdir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config(temp_dir)
            series = self.series()

            self.assertIsNone(FilesystemTechnicalCloseSeriesStore(config).get(self.identity(series)))
            self.assertFalse(config.artifact_root.exists())

    def test_save_creates_canonical_directories_and_returns_inserted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config(temp_dir)
            series = self.series()

            result = FilesystemTechnicalCloseSeriesStore(config).save(series)

            self.assertEqual(result.status, MarketArtifactSaveStatus.INSERTED)
            self.assertEqual(result.identity, self.identity(series))
            self.assertEqual(config.artifact_path(result.identity), config.artifact_root / result.relative_path)
            self.assertTrue(config.artifact_path(result.identity).is_file())

    def test_same_series_is_idempotent_and_does_not_rewrite_mtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            series = self.series()
            path = self.final_path(temp_dir, series)

            first = store.save(series)
            first_sha = self.file_sha256(path)
            first_mtime = path.stat().st_mtime_ns
            second = store.save(series)
            second_sha = self.file_sha256(path)
            second_mtime = path.stat().st_mtime_ns

            self.assertEqual(first.status, MarketArtifactSaveStatus.INSERTED)
            self.assertEqual(second.status, MarketArtifactSaveStatus.IDEMPOTENT)
            self.assertEqual(first_sha, second_sha)
            self.assertEqual(first_mtime, second_mtime)

    def test_same_revision_different_fetched_at_is_idempotent_without_rewrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            first_series = self.series(fetched_at=datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc))
            second_series = self.series(fetched_at=datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc))
            path = self.final_path(temp_dir, first_series)

            self.assertEqual(first_series.market_revision_id, second_series.market_revision_id)

            first = store.save(first_series)
            first_sha = self.file_sha256(path)
            first_mtime = path.stat().st_mtime_ns
            first_payload = path.read_bytes()
            second = store.save(second_series)

            self.assertEqual(first.status, MarketArtifactSaveStatus.INSERTED)
            self.assertEqual(second.status, MarketArtifactSaveStatus.IDEMPOTENT)
            self.assertEqual(path.read_bytes(), first_payload)
            self.assertEqual(self.file_sha256(path), first_sha)
            self.assertEqual(path.stat().st_mtime_ns, first_mtime)
            self.assertEqual(store.get(self.identity(first_series)).fetched_at, first_series.fetched_at)
            self.assertNotEqual(store.get(self.identity(first_series)).fetched_at, second_series.fetched_at)

    def test_get_returns_exact_frozen_series(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            series = self.series()

            store.save(series)

            self.assertEqual(store.get(self.identity(series)), series)

    def test_different_revisions_coexist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            first = self.series()
            second = self.series(
                observations=(
                    self.observation(date(2026, 8, 12), 98.0),
                    self.observation(date(2026, 8, 13), 99.5),
                    self.observation(date(2026, 8, 14), 101.25),
                )
            )

            first_result = store.save(first)
            second_result = store.save(second)

            self.assertEqual(first_result.status, MarketArtifactSaveStatus.INSERTED)
            self.assertEqual(second_result.status, MarketArtifactSaveStatus.INSERTED)
            self.assertNotEqual(first_result.relative_path, second_result.relative_path)
            self.assertEqual(store.get(self.identity(first)), first)
            self.assertEqual(store.get(self.identity(second)), second)

    def test_different_producer_versions_create_different_revisions(self):
        generic = self.series(producer_version=TECHNICAL_CLOSE_OBSERVATION_PRODUCER_VERSION_V1)
        yahoo = self.series(producer_version=YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1)

        self.assertNotEqual(generic.market_revision_id, yahoo.market_revision_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            first_result = store.save(generic)
            second_result = store.save(yahoo)

            self.assertEqual(first_result.status, MarketArtifactSaveStatus.INSERTED)
            self.assertEqual(second_result.status, MarketArtifactSaveStatus.INSERTED)
            self.assertNotEqual(first_result.relative_path, second_result.relative_path)

    def test_malformed_json_invalid_utf8_wrong_version_and_oversized_files_are_corruption(self):
        cases = (
            b"{not json",
            b"\xff\xfe",
            self._wrong_codec_version_payload(),
            b"x" * (1024 * 1024 + 1),
        )

        for payload in cases:
            with self.subTest(size=len(payload)):
                with tempfile.TemporaryDirectory() as temp_dir:
                    store = self.store(temp_dir)
                    series = self.series()
                    identity = self.identity(series)
                    path = self.final_path(temp_dir, series)
                    path.parent.mkdir(parents=True)
                    path.write_bytes(payload)

                    with self.assertRaises(MarketArtifactCorruptionError):
                        store.get(identity)

    def test_revision_mismatch_and_identity_mismatch_are_corruption(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            requested = self.series()
            different_revision = self.series(
                observations=(
                    self.observation(date(2026, 8, 12), 98.0),
                    self.observation(date(2026, 8, 13), 99.5),
                    self.observation(date(2026, 8, 14), 101.25),
                )
            )
            requested_path = self.final_path(temp_dir, requested)
            requested_path.parent.mkdir(parents=True)
            requested_path.write_text(TechnicalCloseObservationSeriesCodec().encode(different_revision), encoding="utf-8")

            with self.assertRaises(MarketArtifactCorruptionError):
                store.get(self.identity(requested))

        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            requested = self.series()
            wrong_identity = self.series(symbol="NVDA", provider_symbol="NVDA")
            requested_path = self.final_path(temp_dir, requested)
            requested_path.parent.mkdir(parents=True)
            requested_path.write_text(TechnicalCloseObservationSeriesCodec().encode(wrong_identity), encoding="utf-8")

            with self.assertRaises(MarketArtifactCorruptionError):
                store.get(self.identity(requested))

    def test_final_directory_final_symlink_and_parent_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            series = self.series()
            path = self.final_path(temp_dir, series)
            path.mkdir(parents=True)

            with self.assertRaises(MarketArtifactCorruptionError):
                store.get(self.identity(series))

        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            series = self.series()
            path = self.final_path(temp_dir, series)
            path.parent.mkdir(parents=True)
            target = Path(temp_dir) / "outside.json"
            target.write_text("{}", encoding="utf-8")
            os.symlink(target, path)

            with self.assertRaises(MarketArtifactCorruptionError):
                store.get(self.identity(series))

        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config(temp_dir)
            series = self.series()
            identity = self.identity(series)
            provider_dir = config.artifact_root / "yahoo_finance_v1"
            provider_dir.parent.mkdir(parents=True)
            outside = Path(temp_dir) / "outside"
            outside.mkdir()
            os.symlink(outside, provider_dir)

            with self.assertRaises(MarketArtifactStoreError):
                FilesystemTechnicalCloseSeriesStore(config).save(series)
            self.assertIsNone((outside / config.artifact_relative_path(identity).parts[1]).exists() or None)

    def test_root_containment_and_parent_file_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config(temp_dir)
            series = self.series()
            identity = self.identity(series)
            relative = config.artifact_relative_path(identity)
            parent_blocker = config.artifact_root / relative.parts[0]
            parent_blocker.parent.mkdir(parents=True)
            parent_blocker.write_text("file", encoding="utf-8")

            with self.assertRaises(MarketArtifactStoreError):
                FilesystemTechnicalCloseSeriesStore(config).save(series)

    def test_write_failure_leaves_no_partial_final_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            series = self.series()
            path = self.final_path(temp_dir, series)

            with mock.patch("market_inputs.filesystem_technical_close_series_store.os.link", side_effect=OSError("disk full")):
                with self.assertRaises(MarketArtifactStoreError):
                    store.save(series)

            self.assertFalse(path.exists())
            self.assertEqual(tuple(path.parent.glob(".*.tmp")), ())

    def test_temp_cleanup_on_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            series = self.series()
            path = self.final_path(temp_dir, series)

            store.save(series)

            self.assertEqual(tuple(path.parent.glob(".*.tmp")), ())

    def test_publish_race_same_series_returns_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            series = self.series()
            path = self.final_path(temp_dir, series)
            original_link = os.link

            def race_link(src, dst):
                if not Path(dst).exists():
                    original_link(src, dst)
                    raise FileExistsError("race")
                return original_link(src, dst)

            with mock.patch("market_inputs.filesystem_technical_close_series_store.os.link", side_effect=race_link):
                result = store.save(series)

            self.assertEqual(result.status, MarketArtifactSaveStatus.IDEMPOTENT)
            self.assertEqual(store.get(self.identity(series)), series)
            self.assertTrue(path.exists())

    def test_publish_race_same_revision_different_fetched_at_returns_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self.store(temp_dir)
            winner = self.series(fetched_at=datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc))
            loser = self.series(fetched_at=datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc))
            path = self.final_path(temp_dir, loser)
            original_link = os.link

            self.assertEqual(winner.market_revision_id, loser.market_revision_id)

            def race_link(src, dst):
                if not Path(dst).exists():
                    Path(dst).write_text(TechnicalCloseObservationSeriesCodec().encode(winner), encoding="utf-8")
                    raise FileExistsError("race")
                return original_link(src, dst)

            with mock.patch("market_inputs.filesystem_technical_close_series_store.os.link", side_effect=race_link):
                result = store.save(loser)

            self.assertEqual(result.status, MarketArtifactSaveStatus.IDEMPOTENT)
            self.assertEqual(store.get(self.identity(loser)), winner)
            self.assertTrue(path.exists())

    def test_concurrent_same_revision_one_inserted_one_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config(temp_dir)
            series = self.series()
            barrier = threading.Barrier(2)

            def save_once():
                barrier.wait()
                return FilesystemTechnicalCloseSeriesStore(config).save(series).status

            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = sorted(result.value for result in executor.map(lambda _: save_once(), range(2)))

            self.assertEqual(statuses, ["IDEMPOTENT", "INSERTED"])

    def test_concurrent_same_revision_different_fetched_at_one_inserted_one_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config(temp_dir)
            first = self.series(fetched_at=datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc))
            second = self.series(fetched_at=datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc))
            barrier = threading.Barrier(2)

            self.assertEqual(first.market_revision_id, second.market_revision_id)

            def save_once(series):
                barrier.wait()
                return FilesystemTechnicalCloseSeriesStore(config).save(series).status

            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = sorted(result.value for result in executor.map(save_once, (first, second)))

            stored = FilesystemTechnicalCloseSeriesStore(config).get(self.identity(first))
            self.assertEqual(statuses, ["IDEMPOTENT", "INSERTED"])
            self.assertIn(stored.fetched_at, {first.fetched_at, second.fetched_at})

    def test_concurrent_different_revisions_are_both_inserted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self.config(temp_dir)
            first = self.series()
            second = self.series(
                observations=(
                    self.observation(date(2026, 8, 12), 98.0),
                    self.observation(date(2026, 8, 13), 99.5),
                    self.observation(date(2026, 8, 14), 101.25),
                )
            )
            barrier = threading.Barrier(2)

            def save_once(series):
                barrier.wait()
                return FilesystemTechnicalCloseSeriesStore(config).save(series).status

            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = [result.value for result in executor.map(save_once, (first, second))]

            self.assertEqual(statuses, ["INSERTED", "INSERTED"])

    def test_no_latest_list_history_delete_update_api(self):
        forbidden = ("latest", "list", "history", "delete", "update", "replace", "cleanup", "scan")
        for name in forbidden:
            with self.subTest(name=name):
                self.assertFalse(hasattr(FilesystemTechnicalCloseSeriesStore, name))

    def test_source_boundary_and_gitignore_runtime_protection(self):
        source = (SRC_PATH / "market_inputs" / "filesystem_technical_close_series_store.py").read_text()
        forbidden = (
            "yfinance",
            "requests",
            "urllib",
            "HistoricalPriceService",
            "LiveDataStore",
            "ResearchDataStore",
            "risk_persistence",
            "RiskEvaluationInput",
            "glob(",
            "rglob(",
            "iterdir(",
            "os.replace",
        )
        for term in forbidden:
            with self.subTest(term=term):
                self.assertNotIn(term, source)
        self.assertIn("data/production/", (PROJECT_ROOT / ".gitignore").read_text())

    def test_real_production_path_untouched(self):
        self.assertFalse((PROJECT_ROOT / "data" / "production").exists())

    def _wrong_codec_version_payload(self):
        payload = json.loads(TechnicalCloseObservationSeriesCodec().encode(self.series()))
        payload["codec_version"] = "2"
        return json.dumps(payload).encode("utf-8")

    def file_sha256(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
