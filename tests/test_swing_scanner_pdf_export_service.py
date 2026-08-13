import subprocess
import sys
import tempfile
import unittest
from dataclasses import fields
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from models import OutcomeDefinition
from models import OutcomeType
from models import OverlappingSignalPolicy
from models import TechnicalIndicatorSnapshot
from signal_outcome_service import RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1
from signal_outcome_service import TECHNICAL_EXAMPLE_SIGNAL_V1
from signal_outcome_service import evaluate_signal_conditions
from swing_research_dashboard import build_scanner_condition_coverage_view
from swing_scanner_pdf_export_service import FORBIDDEN_EXPORT_FIELD_FRAGMENTS
from swing_scanner_pdf_export_service import PDF_DISCLAIMER
from swing_scanner_pdf_export_service import SwingScannerPdfExportError
from swing_scanner_pdf_export_service import SwingScannerPdfExportMetadata
from swing_scanner_pdf_export_service import build_pdf_filename
from swing_scanner_pdf_export_service import export_swing_scanner_pdf
from swing_scanner_service import SwingScannerConfig
from swing_scanner_service import SwingScannerResult


GENERATED_AT = datetime(2026, 8, 11, 1, 15, tzinfo=UTC)


class SwingScannerPdfExportServiceTestCase(unittest.TestCase):

    def config(self):
        return SwingScannerConfig(
            signal_definition=TECHNICAL_EXAMPLE_SIGNAL_V1,
            outcome_definition=RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1,
            overlap_policy=OverlappingSignalPolicy.ALLOW_ALL,
            minimum_resolved_samples=20,
        )

    def test_pdf_export_service_remains_db_agnostic(self):
        source = (SRC_PATH / "swing_scanner_pdf_export_service.py").read_text(encoding="utf-8")

        self.assertNotIn("sqlite3", source)
        self.assertNotIn("LiveDataStore", source)
        self.assertNotIn("ResearchDataStore", source)
        self.assertNotIn("DEFAULT_DB_PATH", source)

    def snapshot(self, symbol: str, **overrides):
        params = {field.name: None for field in fields(TechnicalIndicatorSnapshot)}
        params.update(
            symbol=symbol,
            trading_date=date(2026, 8, 11),
            analysis_close=110.0,
            sma_20=100.0,
            sma_60=90.0,
            sma_120=80.0,
            sma_200=70.0,
            rsi_14=61.0,
            macd=1.2,
            macd_signal=0.8,
            macd_histogram=0.4,
            atr_14=2.0,
            atr_14_pct=0.03,
            volume_sma_20=1000.0,
            volume_ratio_20=1.4,
            return_20d=0.05,
            return_60d=0.12,
            high_60d=116.0,
            prior_high_60d=115.0,
            distance_to_prior_60d_high=-0.04,
            close_above_sma20=True,
            close_above_sma60=True,
            sma20_above_sma60=True,
        )
        params.update(overrides)
        return TechnicalIndicatorSnapshot(**params)

    def signal_match(self, symbol: str, **snapshot_overrides):
        return evaluate_signal_conditions(
            self.snapshot(symbol, **snapshot_overrides),
            TECHNICAL_EXAMPLE_SIGNAL_V1,
        )

    def fixture_result_and_view(self, *, empty_groups=False):
        if empty_groups:
            formal = self.signal_match("2330.TW")
            result = SwingScannerResult(
                config=self.config(),
                requested_symbols=("2330.TW",),
                normalized_symbols=("2330.TW",),
                matched_candidates=(SimpleNamespace(symbol="2330.TW"),),
                no_match_symbols=tuple(),
                no_match_details=tuple(),
                not_evaluable_symbols=tuple(),
                failed_symbols=tuple(),
                generated_at=GENERATED_AT,
                current_signal_details=(formal,),
            )
            return result, build_scanner_condition_coverage_view(result)

        signals = (
            self.signal_match("1001.TW"),
            self.signal_match("1002.TW"),
            self.signal_match("1003.TW", rsi_14=72.0),
            self.signal_match("2368.TW", volume_ratio_20=1.10),
            self.signal_match("2369.TW", volume_ratio_20=1.10),
            self.signal_match("1006.TW", distance_to_prior_60d_high=-0.08),
            self.signal_match("1007.TW", sma_20=80.0),
            self.signal_match("1008.TW", volume_ratio_20=1.10, rsi_14=72.0),
            self.signal_match("1009.TW", volume_ratio_20=1.10, distance_to_prior_60d_high=-0.08),
            self.signal_match("1010.TW", analysis_close=90.0, volume_ratio_20=1.10, rsi_14=72.0),
        )
        result = SwingScannerResult(
            config=self.config(),
            requested_symbols=tuple(signal.symbol for signal in signals),
            normalized_symbols=tuple(signal.symbol for signal in signals),
            matched_candidates=(
                SimpleNamespace(symbol="1002.TW"),
                SimpleNamespace(symbol="1001.TW"),
            ),
            no_match_symbols=tuple(signal.symbol for signal in signals if not signal.matched),
            no_match_details=tuple(),
            not_evaluable_symbols=tuple(),
            failed_symbols=tuple(),
            generated_at=GENERATED_AT,
            current_signal_details=signals,
        )
        return result, build_scanner_condition_coverage_view(result)

    def test_export_returns_pdf_bytes_filename_and_metadata(self):
        result, view = self.fixture_result_and_view()

        export = export_swing_scanner_pdf(
            scanner_result=result,
            coverage_view=view,
            source_context={
                "source_type": "Frozen TWSE Research Universe",
                "source_universe_id": "frozen_twse_research_universe_2026_08_09",
                "symbol_count": 218,
            },
            generated_at=GENERATED_AT,
        )

        self.assertTrue(export.pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(export.pdf_bytes), 5000)
        self.assertEqual(export.filename, "Swing_Scanner_Frozen_TWSE_218_2026-08-11_0115.pdf")
        self.assertEqual(export.metadata.market_data_as_of, "2026-08-11")
        self.assertEqual(export.metadata.scanned_count, 10)
        self.assertEqual(export.metadata.evaluated_count, 10)
        self.assertEqual(export.metadata.formal_symbols, ("1002.TW", "1001.TW"))
        self.assertEqual(export.metadata.universe_version, "2026-08-current-etf-constituent-v1")

    def test_pdf_text_contains_required_sections_and_disclaimer(self):
        from pypdf import PdfReader

        result, view = self.fixture_result_and_view()
        export = export_swing_scanner_pdf(
            scanner_result=result,
            coverage_view=view,
            source_context={"source_type": "Manual Input", "symbol_count": 10},
            generated_at=GENERATED_AT,
        )

        reader = PdfReader(io_bytes(export.pdf_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        self.assertIn("波段股票掃描報告", text)
        self.assertIn("正式 V1 命中", text)
        self.assertIn("研究優先觀察 A", text)
        self.assertIn("研究優先觀察 B", text)
        self.assertIn("研究觀察", text)
        self.assertIn("探索觀察", text)
        self.assertIn("不構成投資建議", text)
        self.assertNotIn("股票推薦報告", text)
        self.assertNotIn("投資建議報告", text)

    def test_formal_rows_preserve_production_scanner_order(self):
        result, view = self.fixture_result_and_view()

        export = export_swing_scanner_pdf(
            scanner_result=result,
            coverage_view=view,
            source_context={"source_type": "Manual Input", "symbol_count": 10},
            generated_at=GENERATED_AT,
        )

        self.assertEqual(export.metadata.formal_symbols, ("1002.TW", "1001.TW"))

    def test_priority_b_displays_v1_1_experimental_badge_and_v1_not_match(self):
        from pypdf import PdfReader

        result, view = self.fixture_result_and_view()
        export = export_swing_scanner_pdf(
            scanner_result=result,
            coverage_view=view,
            source_context={"source_type": "Manual Input", "symbol_count": 10},
            generated_at=GENERATED_AT,
        )

        text = "\n".join(page.extract_text() or "" for page in PdfReader(io_bytes(export.pdf_bytes)).pages)

        self.assertIn("2368.TW", text)
        self.assertIn("V1.1 實驗版符合", text)
        self.assertIn("不符合", text)

    def test_no_forbidden_export_model_fields(self):
        field_names = {field.name for field in fields(SwingScannerPdfExportMetadata)}

        self.assertTrue(
            all(
                fragment not in field_name.lower()
                for field_name in field_names
                for fragment in FORBIDDEN_EXPORT_FIELD_FRAGMENTS
            )
        )

    def test_empty_groups_generate_non_blank_pdf(self):
        from pypdf import PdfReader

        result, view = self.fixture_result_and_view(empty_groups=True)
        export = export_swing_scanner_pdf(
            scanner_result=result,
            coverage_view=view,
            source_context={"source_type": "Watchlist", "symbol_count": 1},
            generated_at=GENERATED_AT,
        )
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io_bytes(export.pdf_bytes)).pages)

        self.assertTrue(export.pdf_bytes.startswith(b"%PDF"))
        self.assertIn("本次無符合項目", text)

    def test_no_result_raises_actionable_error(self):
        with self.assertRaisesRegex(SwingScannerPdfExportError, "請先執行波段掃描"):
            export_swing_scanner_pdf(
                scanner_result=None,
                coverage_view=None,
                generated_at=GENERATED_AT,
            )

    def test_pdf_export_does_not_call_scanner_fetch_builder_or_db_writer(self):
        result, view = self.fixture_result_and_view()

        with patch("swing_scanner_service.SwingScannerService.scan") as scan_mock:
            with patch("technical_indicator_service.build_technical_indicator_series") as builder_mock:
                with patch("historical_price_service.get_historical_prices") as fetch_mock:
                    with patch("sqlite3.connect") as sqlite_mock:
                        export_swing_scanner_pdf(
                            scanner_result=result,
                            coverage_view=view,
                            source_context={"source_type": "Manual Input", "symbol_count": 10},
                            generated_at=GENERATED_AT,
                        )

        scan_mock.assert_not_called()
        builder_mock.assert_not_called()
        fetch_mock.assert_not_called()
        sqlite_mock.assert_not_called()

    def test_filename_is_filesystem_safe(self):
        filename = build_pdf_filename(
            source_type="Saved Universe",
            market_data_as_of="2026/08/11",
            generated_at=GENERATED_AT,
        )

        self.assertEqual(filename, "Swing_Scanner_Saved_Universe_2026_08_11_0115.pdf")
        self.assertNotIn(":", filename)
        self.assertNotIn("/", filename)

    def test_fixture_pdf_renders_with_poppler(self):
        result, view = self.fixture_result_and_view()
        export = export_swing_scanner_pdf(
            scanner_result=result,
            coverage_view=view,
            source_context={"source_type": "Manual Input", "symbol_count": 10},
            generated_at=GENERATED_AT,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "fixture.pdf"
            png_prefix = Path(temp_dir) / "fixture"
            pdf_path.write_bytes(export.pdf_bytes)
            completed = subprocess.run(
                ["pdftoppm", "-png", "-f", "1", "-singlefile", str(pdf_path), str(png_prefix)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertGreater((Path(temp_dir) / "fixture.png").stat().st_size, 1000)


def io_bytes(value: bytes):
    from io import BytesIO

    return BytesIO(value)


if __name__ == "__main__":
    unittest.main()
