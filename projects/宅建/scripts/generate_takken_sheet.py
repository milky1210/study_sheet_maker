#!/usr/bin/env python3
"""Generate the A4 portrait 1:2 memorization sheet from the canonical Q&A JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "qa" / "宅建業法_暗記シート.json"
DEFAULT_OUTPUT = ROOT / "pdf" / "宅建業法_暗記シート.pdf"
FONT_NAME = "HeiseiKakuGo-W5"


def read_cards(path: Path) -> tuple[dict, list[dict]]:
    """Read and minimally validate the canonical Q&A data."""
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data.get("items"), list) or not data["items"]:
        raise ValueError("items must be a non-empty array")

    ids: set[str] = set()
    for index, card in enumerate(data["items"], start=1):
        for key in ("id", "q", "a", "source_id", "article"):
            if not isinstance(card.get(key), str) or not card[key].strip():
                raise ValueError(f"Item {index} must contain a non-empty {key!r}")
        if card["id"] in ids:
            raise ValueError(f"Duplicate item id: {card['id']}")
        ids.add(card["id"])
    return data, data["items"]


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    return Paragraph(safe.replace("\n", "<br/>"), style)


TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def _parse_table_row(line: str) -> list[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def answer_flowables(
    text: str,
    text_style: ParagraphStyle,
    table_header_style: ParagraphStyle,
    table_cell_style: ParagraphStyle,
    available_width: float,
) -> list:
    """Convert answer text to flowables, including markdown-like tables."""
    lines = text.splitlines() if "\n" in text else [text]
    flowables: list = []
    buffer: list[str] = []
    index = 0

    def flush_buffer() -> None:
        if not buffer:
            return
        merged = "\n".join(line for line in buffer if line.strip())
        buffer.clear()
        if merged:
            flowables.append(paragraph(merged, text_style))

    while index < len(lines):
        line = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if "|" in line and TABLE_SEPARATOR_RE.match(next_line):
            flush_buffer()
            table_lines = [line, next_line]
            index += 2
            while index < len(lines) and "|" in lines[index]:
                table_lines.append(lines[index])
                index += 1

            raw_rows = [_parse_table_row(table_line) for table_line in table_lines if table_line.strip()]
            if len(raw_rows) >= 2:
                headers = raw_rows[0]
                body_rows = raw_rows[2:]
                column_count = max(len(headers), *(len(row) for row in body_rows))
                headers += [""] * (column_count - len(headers))

                formatted_rows = [[paragraph(cell, table_header_style) for cell in headers]]
                for row in body_rows:
                    padded = row + [""] * (column_count - len(row))
                    formatted_rows.append([paragraph(cell, table_cell_style) for cell in padded])

                nested_table = Table(
                    formatted_rows,
                    colWidths=[available_width / column_count] * column_count,
                    hAlign="LEFT",
                    splitByRow=1,
                )
                nested_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DBEAFE")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#93C5FD")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1.8 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 1.8 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 1.2 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2 * mm),
                ]))
                flowables.append(nested_table)
                flowables.append(Spacer(1, 0.7 * mm))
            continue

        if line.strip():
            buffer.append(line)
        else:
            flush_buffer()
        index += 1

    flush_buffer()
    return flowables if flowables else [paragraph(text, text_style)]


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(FONT_NAME, 7.5)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(doc.leftMargin, 10 * mm, f"{doc.title} | 左の問いを見て右の答えを想起する")
    canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"{doc.page} ページ")
    canvas.restoreState()


def build_pdf(data: dict, cards: list[dict], output: Path) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
    output.parent.mkdir(parents=True, exist_ok=True)

    document = SimpleDocTemplate(
        str(output), pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm,
        title=data["title"], author="study_sheet_maker",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SheetTitle", parent=styles["Title"], fontName=FONT_NAME, fontSize=17,
        leading=22, textColor=colors.HexColor("#0F172A"), alignment=TA_LEFT, spaceAfter=1.5 * mm,
    )
    subtitle_style = ParagraphStyle(
        "SheetSubtitle", parent=styles["Normal"], fontName=FONT_NAME, fontSize=8.5,
        leading=12, textColor=colors.HexColor("#475569"), spaceAfter=4 * mm,
    )
    header_style = ParagraphStyle(
        "ColumnHeader", parent=styles["Normal"], fontName=FONT_NAME, fontSize=10,
        leading=13, alignment=TA_CENTER, textColor=colors.white,
    )
    question_style = ParagraphStyle(
        "Question", parent=styles["Normal"], fontName=FONT_NAME, fontSize=9.2,
        leading=13.2, textColor=colors.HexColor("#0F172A"),
    )
    answer_style = ParagraphStyle(
        "Answer", parent=styles["Normal"], fontName=FONT_NAME, fontSize=8.8,
        leading=12.7, textColor=colors.HexColor("#1E293B"),
    )
    answer_table_header_style = ParagraphStyle(
        "AnswerTableHeader", parent=answer_style, fontName=FONT_NAME, fontSize=8.2,
        leading=10.8, textColor=colors.HexColor("#1E3A8A"),
    )
    answer_table_cell_style = ParagraphStyle(
        "AnswerTableCell", parent=answer_style, fontName=FONT_NAME, fontSize=8.0,
        leading=10.6, textColor=colors.HexColor("#1E293B"),
    )

    usable_width = A4[0] - document.leftMargin - document.rightMargin
    question_width = usable_width / 3
    answer_width = usable_width - question_width
    rows = [[paragraph("問い・キーワード", header_style), paragraph("答え・周辺知識", header_style)]]
    for number, card in enumerate(cards, start=1):
        question = f"{number:02d}. {card['q']}"
        answer = card["a"]
        rows.append([
            paragraph(question, question_style),
            answer_flowables(
                answer,
                answer_style,
                answer_table_header_style,
                answer_table_cell_style,
                answer_width - (8.6 * mm),
            ),
        ])

    table = Table(rows, colWidths=[question_width, answer_width], repeatRows=1, splitByRow=1, hAlign="LEFT")
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#1E3A8A")),
        ("LINEBEFORE", (1, 0), (1, -1), 0.65, colors.HexColor("#94A3B8")),
        ("GRID", (0, 1), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4.3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4.3 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 2.7 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2.7 * mm),
        ("TOPPADDING", (0, 0), (-1, 0), 2.2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2.2 * mm),
    ]
    for row in range(1, len(rows)):
        if row % 2 == 0:
            style_commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#F8FAFC")))
    table.setStyle(TableStyle(style_commands))

    story = [
        Paragraph(data["title"], title_style),
        Paragraph(f"{data['scope']}　｜　基準日: {data['as_of']}　｜　全{len(cards)}問", subtitle_style),
        table,
    ]
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Canonical Q&A JSON path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output PDF path")
    args = parser.parse_args()

    data, cards = read_cards(args.input)
    build_pdf(data, cards, args.output)
    print(f"Generated {args.output} ({len(cards)} cards)")


if __name__ == "__main__":
    main()
