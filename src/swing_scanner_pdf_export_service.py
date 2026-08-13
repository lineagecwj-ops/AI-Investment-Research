from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from io import BytesIO
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle

from swing_research_dashboard import CandidateDisplayDashboardProjection
from swing_research_dashboard import ScannerConditionCoverageView


PDF_DISCLAIMER = (
    "本報告為技術條件掃描與研究分類結果，不代表個別股票未來上漲機率，亦不構成投資建議。"
)
FROZEN_TWSE_UNIVERSE_VERSION = "2026-08-current-etf-constituent-v1"
FROZEN_TWSE_UNIVERSE_ID = "frozen_twse_research_universe_2026_08_09"
FROZEN_TWSE_SOURCE_TYPE = "Frozen TWSE Research Universe"
SOURCE_FILENAME_LABELS = {
    "Manual Input": "Manual",
    "Watchlist": "Watchlist",
    "Saved Universe": "Saved_Universe",
    FROZEN_TWSE_SOURCE_TYPE: "Frozen_TWSE_218",
}
SOURCE_DISPLAY_LABELS = {
    "Manual Input": "手動輸入",
    "Watchlist": "觀察清單",
    "Saved Universe": "已儲存股票池",
    FROZEN_TWSE_SOURCE_TYPE: "研究股票池（Frozen TWSE 218）",
}
FORBIDDEN_EXPORT_FIELD_FRAGMENTS = (
    "score",
    "rank",
    "probability",
    "confidence",
    "recommendation",
    "expected_return",
    "individual_hhr",
)


class SwingScannerPdfExportError(Exception):
    """Raised when the current scan snapshot cannot be exported safely."""


@dataclass(frozen=True)
class SwingScannerPdfExportMetadata:

    generated_at: datetime

    market_data_as_of: str

    scan_mode: str

    source_type: str

    source_label: str

    universe_name: str

    universe_version: str | None

    universe_id: str | None

    scanned_count: int

    evaluated_count: int

    production_signal_definition_id: str

    formal_symbols: tuple[str, ...]

    filename: str

    font_name: str

    font_path: str


@dataclass(frozen=True)
class SwingScannerPdfExport:

    pdf_bytes: bytes

    filename: str

    metadata: SwingScannerPdfExportMetadata


def export_swing_scanner_pdf(
    *,
    scanner_result,
    coverage_view: ScannerConditionCoverageView,
    source_context: dict[str, object] | None = None,
    generated_at: datetime | None = None,
) -> SwingScannerPdfExport:
    if scanner_result is None:
        raise SwingScannerPdfExportError("請先執行波段掃描。")
    if coverage_view is None:
        raise SwingScannerPdfExportError("缺少本次掃描的條件覆蓋 snapshot。")
    if getattr(scanner_result, "current_signal_details", None) is None:
        raise SwingScannerPdfExportError("目前掃描結果缺少技術條件明細，無法產生 PDF。")
    projection = coverage_view.experimental_candidate_projection
    if projection is None:
        raise SwingScannerPdfExportError("缺少本次掃描的實驗候選顯示 snapshot。")

    generated_at = generated_at or datetime.now(UTC)
    font_name, font_path = resolve_traditional_chinese_font()
    pdfmetrics.registerFont(TTFont(font_name, font_path))
    metadata = build_pdf_export_metadata(
        scanner_result=scanner_result,
        formal_rows=coverage_view.formal_v1_rows,
        projection=projection,
        source_context=source_context,
        generated_at=generated_at,
        font_name=font_name,
        font_path=font_path,
    )
    pdf_bytes = _build_pdf_bytes(
        scanner_result=scanner_result,
        formal_rows=coverage_view.formal_v1_rows,
        projection=projection,
        metadata=metadata,
        font_name=font_name,
    )
    return SwingScannerPdfExport(
        pdf_bytes=pdf_bytes,
        filename=metadata.filename,
        metadata=metadata,
    )


def resolve_traditional_chinese_font() -> tuple[str, str]:
    candidates = (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/Library/Fonts/NotoSansCJKtc-Regular.otf",
        "/Library/Fonts/Noto Sans CJK TC Regular.otf",
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return "SwingScannerCJK", str(path)
    raise SwingScannerPdfExportError("目前環境缺少可用的繁體中文字型，無法產生 PDF。")


def build_pdf_export_metadata(
    *,
    scanner_result,
    formal_rows: list[dict[str, object]],
    projection: CandidateDisplayDashboardProjection,
    source_context: dict[str, object] | None,
    generated_at: datetime,
    font_name: str,
    font_path: str,
) -> SwingScannerPdfExportMetadata:
    source_type = str((source_context or {}).get("source_type") or "Manual Input")
    source_label = _source_label(source_type, source_context)
    universe_name = _universe_name(source_type, source_context)
    universe_version = FROZEN_TWSE_UNIVERSE_VERSION if source_type == FROZEN_TWSE_SOURCE_TYPE else None
    universe_id = (
        str((source_context or {}).get("source_universe_id") or FROZEN_TWSE_UNIVERSE_ID)
        if source_type == FROZEN_TWSE_SOURCE_TYPE
        else _optional_string((source_context or {}).get("source_universe_id"))
    )
    market_data_as_of = _market_data_as_of(scanner_result, projection)
    filename = build_pdf_filename(
        source_type=source_type,
        market_data_as_of=market_data_as_of,
        generated_at=generated_at,
    )
    return SwingScannerPdfExportMetadata(
        generated_at=generated_at,
        market_data_as_of=market_data_as_of,
        scan_mode="Current",
        source_type=source_type,
        source_label=source_label,
        universe_name=universe_name,
        universe_version=universe_version,
        universe_id=universe_id,
        scanned_count=int(getattr(scanner_result, "scanned_count", len(getattr(scanner_result, "normalized_symbols", ())))),
        evaluated_count=int(getattr(projection, "evaluated_symbol_count", 0)),
        production_signal_definition_id=scanner_result.config.signal_definition.id,
        formal_symbols=tuple(str(row.get("股票", "")) for row in formal_rows),
        filename=filename,
        font_name=font_name,
        font_path=font_path,
    )


def build_pdf_filename(
    *,
    source_type: str,
    market_data_as_of: str,
    generated_at: datetime,
) -> str:
    source_label = SOURCE_FILENAME_LABELS.get(source_type, source_type.replace(" ", "_"))
    source_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_label).strip("_") or "Scan"
    data_date = re.sub(r"[^0-9A-Za-z_.-]+", "_", market_data_as_of).strip("_") or "NA"
    generated_label = generated_at.strftime("%H%M")
    return f"Swing_Scanner_{source_label}_{data_date}_{generated_label}.pdf"


def _build_pdf_bytes(
    *,
    scanner_result,
    formal_rows: list[dict[str, object]],
    projection: CandidateDisplayDashboardProjection,
    metadata: SwingScannerPdfExportMetadata,
    font_name: str,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title="波段股票掃描報告",
        author="AI-Investment-Research",
    )
    styles = _styles(font_name)
    elements = [
        Paragraph("波段股票掃描報告", styles["Title"]),
        Paragraph("Swing Scanner", styles["Subtitle"]),
        Spacer(1, 6),
        _metadata_table(metadata, styles),
        Spacer(1, 8),
        _summary_table(projection, styles),
        Spacer(1, 8),
        Paragraph(PDF_DISCLAIMER, styles["Disclaimer"]),
        PageBreak(),
    ]

    snapshot_by_symbol = _snapshot_by_symbol(scanner_result)
    elements.extend(
        _section(
            "1. 正式 V1 命中",
            None,
            _formal_rows(formal_rows, snapshot_by_symbol),
            ("股票代號", "Coverage", "Production V1", "As-of date", "Analysis Close", "SMA20", "SMA60", "Volume Ratio", "RSI", "Distance 60d High"),
            styles,
        )
    )
    elements.extend(
        _section(
            "2. 研究優先觀察 A",
            "4/5，唯一未符合 RSI。Experimental / Research。",
            _priority_a_rows(projection.priority_a_rows),
            ("股票代號", "Coverage", "Missing condition", "RSI value", "Production V1"),
            styles,
        )
    )
    elements.extend(
        _section(
            "3. 研究優先觀察 B",
            "4/5，唯一未符合成交量。Experimental / Research。",
            _priority_b_rows(projection.priority_b_rows),
            ("股票代號", "Coverage", "Missing condition", "Volume Ratio", "Production V1", "V1.1"),
            styles,
        )
    )
    elements.extend(
        _section(
            "4. 研究觀察",
            "4/5，唯一未符合距離前高條件。Experimental / Research。",
            _watch_rows(projection.watch_rows),
            ("股票代號", "Coverage", "Distance 60d High", "Production V1"),
            styles,
        )
    )
    elements.extend(
        _section(
            "5. 其他 4/5 探索觀察",
            "Experimental / Research。",
            _other_four_rows(projection.other_four_of_five_rows),
            ("股票代號", "Coverage", "Missing condition", "Production V1"),
            styles,
        )
    )
    elements.extend(
        _section(
            "6. 3/5 探索觀察",
            "Experimental / Research。",
            _three_of_five_rows(projection.three_of_five_rows),
            ("股票代號", "Coverage", "Missing conditions", "Production V1"),
            styles,
        )
    )
    elements.extend(
        [
            Spacer(1, 8),
            Paragraph("7. 0-2/5", styles["Heading"]),
            Paragraph(f"Phase 1 僅顯示 count：{projection.below_display_scope_count}", styles["Body"]),
            Spacer(1, 10),
            Paragraph(PDF_DISCLAIMER, styles["Disclaimer"]),
        ]
    )
    doc.build(elements, onFirstPage=_footer(metadata, font_name), onLaterPages=_footer(metadata, font_name))
    return buffer.getvalue()


def _styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "SwingTitle",
            parent=base["Title"],
            fontName=font_name,
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "Subtitle": ParagraphStyle(
            "SwingSubtitle",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
        ),
        "Heading": ParagraphStyle(
            "SwingHeading",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=12,
            leading=15,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "Body": ParagraphStyle(
            "SwingBody",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        ),
        "Table": ParagraphStyle(
            "SwingTable",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=7,
            leading=9,
            alignment=TA_LEFT,
        ),
        "Disclaimer": ParagraphStyle(
            "SwingDisclaimer",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#555555"),
        ),
    }


def _metadata_table(metadata: SwingScannerPdfExportMetadata, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ("報告產生時間", _format_datetime(metadata.generated_at)),
        ("掃描模式", metadata.scan_mode),
        ("股票來源", metadata.source_label),
        ("股票池名稱", metadata.universe_name),
        ("掃描股票數", str(metadata.scanned_count)),
        ("資料日期 / as-of date", metadata.market_data_as_of),
        ("Production signal definition id", metadata.production_signal_definition_id),
    ]
    if metadata.universe_version:
        rows.append(("Universe version", metadata.universe_version))
    if metadata.universe_id:
        rows.append(("Universe id", metadata.universe_id))
    return _make_table(rows, styles, col_widths=(48 * mm, 132 * mm))


def _summary_table(projection: CandidateDisplayDashboardProjection, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ("Evaluated", projection.evaluated_symbol_count),
        ("Formal V1", len(projection.formal_v1_rows)),
        ("Priority A", len(projection.priority_a_rows)),
        ("Priority B", len(projection.priority_b_rows)),
        ("Research Watch", len(projection.watch_rows)),
        ("Other 4/5", len(projection.other_four_of_five_rows)),
        ("3/5", len(projection.three_of_five_rows)),
        ("Below scope", projection.below_display_scope_count),
    ]
    return _make_table(rows, styles, headers=("分類", "數量"), col_widths=(90 * mm, 30 * mm))


def _section(
    title: str,
    subtitle: str | None,
    rows: list[tuple[object, ...]],
    headers: tuple[str, ...],
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    elements: list[object] = [Paragraph(title, styles["Heading"])]
    if subtitle:
        elements.append(Paragraph(subtitle, styles["Disclaimer"]))
    if rows:
        elements.append(_make_table(rows, styles, headers=headers))
    else:
        elements.append(Paragraph("本次無符合項目。", styles["Body"]))
    return elements


def _make_table(
    rows,
    styles: dict[str, ParagraphStyle],
    headers: tuple[str, ...] | None = None,
    col_widths=None,
) -> Table:
    table_rows = []
    if headers:
        table_rows.append([_cell(header, styles) for header in headers])
    table_rows.extend([[_cell(value, styles) for value in row] for row in rows])
    table = Table(table_rows, colWidths=col_widths, repeatRows=1 if headers else 0, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), styles["Table"].fontName),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BBBBBB")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#222222")),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _cell(value, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(_escape_pdf_text(value), styles["Table"])


def _formal_rows(rows: list[dict[str, object]], snapshot_by_symbol: dict[str, object]) -> list[tuple[object, ...]]:
    result = []
    for row in rows:
        symbol = str(row.get("股票", ""))
        snapshot = snapshot_by_symbol.get(symbol)
        result.append(
            (
                symbol,
                row.get("條件覆蓋", ""),
                row.get("Production V1", row.get("V1 狀態", "")),
                row.get("最新交易日", ""),
                _format_number(getattr(snapshot, "analysis_close", None)),
                _format_number(getattr(snapshot, "sma_20", None)),
                _format_number(getattr(snapshot, "sma_60", None)),
                row.get("volume_ratio_20", _format_number(getattr(snapshot, "volume_ratio_20", None))),
                row.get("RSI 14", _format_number(getattr(snapshot, "rsi_14", None))),
                row.get(
                    "distance_to_prior_60d_high",
                    _format_percent(getattr(snapshot, "distance_to_prior_60d_high", None)),
                ),
            )
        )
    return result


def _priority_a_rows(rows: list[dict[str, object]]) -> list[tuple[object, ...]]:
    return [
        (
            row.get("股票", ""),
            row.get("條件覆蓋", ""),
            row.get("未符合條件", ""),
            row.get("RSI 14", ""),
            row.get("Production V1", ""),
        )
        for row in rows
    ]


def _priority_b_rows(rows: list[dict[str, object]]) -> list[tuple[object, ...]]:
    return [
        (
            row.get("股票", ""),
            row.get("條件覆蓋", ""),
            row.get("未符合條件", ""),
            row.get("volume_ratio_20", ""),
            row.get("Production V1", ""),
            row.get("V1.1 實驗版", ""),
        )
        for row in rows
    ]


def _watch_rows(rows: list[dict[str, object]]) -> list[tuple[object, ...]]:
    return [
        (
            row.get("股票", ""),
            row.get("條件覆蓋", ""),
            row.get("distance_to_prior_60d_high", ""),
            row.get("Production V1", ""),
        )
        for row in rows
    ]


def _other_four_rows(rows: list[dict[str, object]]) -> list[tuple[object, ...]]:
    return [
        (
            row.get("股票", ""),
            row.get("條件覆蓋", ""),
            row.get("未符合條件", ""),
            row.get("Production V1", ""),
        )
        for row in rows
    ]


def _three_of_five_rows(rows: list[dict[str, object]]) -> list[tuple[object, ...]]:
    return [
        (
            row.get("股票", ""),
            row.get("條件覆蓋", ""),
            row.get("未符合條件", ""),
            row.get("Production V1", ""),
        )
        for row in rows
    ]


def _snapshot_by_symbol(scanner_result) -> dict[str, object]:
    return {
        signal_match.symbol: signal_match.feature_snapshot
        for signal_match in getattr(scanner_result, "current_signal_details", tuple())
    }


def _market_data_as_of(scanner_result, projection: CandidateDisplayDashboardProjection) -> str:
    dates = [
        str(getattr(signal_match, "trading_date"))
        for signal_match in getattr(scanner_result, "current_signal_details", tuple())
        if getattr(signal_match, "trading_date", None) is not None
    ]
    for rows in (
        projection.formal_v1_rows,
        projection.priority_a_rows,
        projection.priority_b_rows,
        projection.watch_rows,
        projection.other_four_of_five_rows,
        projection.three_of_five_rows,
    ):
        dates.extend(str(row["最新交易日"]) for row in rows if row.get("最新交易日"))
    return max(dates) if dates else "N/A"


def _source_label(source_type: str, source_context: dict[str, object] | None) -> str:
    if source_type == "Saved Universe" and (source_context or {}).get("source_universe_name"):
        return f"已儲存股票池 - {source_context['source_universe_name']}"
    return SOURCE_DISPLAY_LABELS.get(source_type, source_type)


def _universe_name(source_type: str, source_context: dict[str, object] | None) -> str:
    if source_type == FROZEN_TWSE_SOURCE_TYPE:
        return "研究股票池（Frozen TWSE 218）"
    return str((source_context or {}).get("source_universe_name") or _source_label(source_type, source_context))


def _optional_string(value) -> str | None:
    return None if value in (None, "") else str(value)


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _format_number(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.2f}"


def _format_percent(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.2%}"


def _escape_pdf_text(value) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _footer(metadata: SwingScannerPdfExportMetadata, font_name: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 7)
        footer = (
            f"資料日期：{metadata.market_data_as_of} · "
            f"Generated by AI-Investment-Research · "
            f"Page {doc.page}"
        )
        canvas.drawString(doc.leftMargin, 8 * mm, footer)
        canvas.restoreState()

    return draw
