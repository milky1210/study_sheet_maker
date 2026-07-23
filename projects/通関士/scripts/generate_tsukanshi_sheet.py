#!/usr/bin/env python3
"""Generate the A4 portrait 1:2 memorization sheet from the canonical Q&A JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "qa" / "通関業法_暗記シート.json"
DEFAULT_OUTPUT = ROOT / "pdf" / "通関業法_暗記シート.pdf"
FONT_NAME = "HeiseiKakuGo-W5"


def read_cards(path: Path) -> tuple[dict, list[dict]]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data.get("items"), list) or not data["items"]:
        raise ValueError("items must be a non-empty array")
    ids: set[str] = set()
    for number, card in enumerate(data["items"], start=1):
        for key in ("id", "q", "a", "source_id", "article"):
            if not isinstance(card.get(key), str) or not card[key].strip():
                raise ValueError(f"Item {number} must contain a non-empty {key!r}")
        if card["id"] in ids:
            raise ValueError(f"Duplicate item id: {card['id']}")
        ids.add(card["id"])
    return data, data["items"]


def make_paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


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
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=15 * mm, bottomMargin=18 * mm, title=data["title"], author="study_sheet_maker")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], fontName=FONT_NAME, fontSize=17, leading=22,
                           textColor=colors.HexColor("#0F172A"), alignment=TA_LEFT, spaceAfter=1.5 * mm)
    subtitle = ParagraphStyle("subtitle", parent=styles["Normal"], fontName=FONT_NAME, fontSize=8.5, leading=12,
                              textColor=colors.HexColor("#475569"), spaceAfter=4 * mm)
    header = ParagraphStyle("header", parent=styles["Normal"], fontName=FONT_NAME, fontSize=10, leading=13,
                            alignment=TA_CENTER, textColor=colors.white)
    question = ParagraphStyle("question", parent=styles["Normal"], fontName=FONT_NAME, fontSize=9.2, leading=13.2,
                              textColor=colors.HexColor("#0F172A"))
    answer = ParagraphStyle("answer", parent=styles["Normal"], fontName=FONT_NAME, fontSize=8.8, leading=12.7,
                            textColor=colors.HexColor("#1E293B"))

    width = A4[0] - doc.leftMargin - doc.rightMargin
    rows = [[make_paragraph("問い・キーワード", header), make_paragraph("答え・周辺知識", header)]]
    rows.extend([make_paragraph(f"{n:02d}. {card['q']}", question), make_paragraph(card["a"], answer)]
                for n, card in enumerate(cards, start=1))
    table = Table(rows, colWidths=[width / 3, width * 2 / 3], repeatRows=1, splitByRow=1, hAlign="LEFT")
    commands = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), .8, colors.HexColor("#1E3A8A")),
                ("LINEBEFORE", (1, 0), (1, -1), .65, colors.HexColor("#94A3B8")),
                ("GRID", (0, 1), (-1, -1), .3, colors.HexColor("#CBD5E1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4.3 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4.3 * mm),
                ("TOPPADDING", (0, 1), (-1, -1), 2.7 * mm), ("BOTTOMPADDING", (0, 1), (-1, -1), 2.7 * mm),
                ("TOPPADDING", (0, 0), (-1, 0), 2.2 * mm), ("BOTTOMPADDING", (0, 0), (-1, 0), 2.2 * mm)]
    commands.extend(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#F8FAFC")) for row in range(2, len(rows), 2))
    table.setStyle(TableStyle(commands))
    doc.build([Paragraph(data["title"], title), Paragraph(f"{data['scope']}　｜　基準日: {data['as_of']}　｜　全{len(cards)}問", subtitle), table], onFirstPage=footer, onLaterPages=footer)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    data, cards = read_cards(args.input)
    build_pdf(data, cards, args.output)
    print(f"Generated {args.output} ({len(cards)} cards)")


if __name__ == "__main__":
    main()
