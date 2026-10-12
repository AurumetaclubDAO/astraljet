from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "architektura" / "ASTRA_JET_ARCHITEKTURA_OD_A_DO_Z.md"
TARGET = ROOT / "docs" / "architektura" / "ASTRA_JET_ARCHITEKTURA_OD_A_DO_Z.pdf"

REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")
BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
pdfmetrics.registerFont(TTFont("Astra", str(REGULAR)))
pdfmetrics.registerFont(TTFont("AstraBold", str(BOLD)))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    "TitleAstra", parent=styles["Title"], fontName="AstraBold", fontSize=26,
    leading=31, textColor=colors.HexColor("#A77B20"), alignment=TA_CENTER,
    spaceAfter=16,
))
styles.add(ParagraphStyle(
    "H1Astra", parent=styles["Heading1"], fontName="AstraBold", fontSize=17,
    leading=22, textColor=colors.HexColor("#201A12"), spaceBefore=15, spaceAfter=9,
))
styles.add(ParagraphStyle(
    "H2Astra", parent=styles["Heading2"], fontName="AstraBold", fontSize=12,
    leading=16, textColor=colors.HexColor("#6C4C0B"), spaceBefore=11, spaceAfter=5,
))
styles.add(ParagraphStyle(
    "BodyAstra", parent=styles["BodyText"], fontName="Astra", fontSize=9.2,
    leading=13.2, spaceAfter=6,
))
styles.add(ParagraphStyle(
    "CodeAstra", fontName="Astra", fontSize=7.5, leading=10,
    leftIndent=8, rightIndent=8, backColor=colors.HexColor("#F4F0E8"),
    borderColor=colors.HexColor("#D5C8A8"), borderWidth=0.5, borderPadding=7,
    spaceAfter=9,
))


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r"<font name='AstraBold' color='#6C4C0B'>\1</font>", text)
    return text


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D5C8A8"))
    canvas.line(1.7 * cm, 1.35 * cm, A4[0] - 1.7 * cm, 1.35 * cm)
    canvas.setFont("Astra", 7.5)
    canvas.setFillColor(colors.HexColor("#6B6257"))
    canvas.drawString(1.7 * cm, 0.9 * cm, "ASTRA JET — architektura systemu")
    canvas.drawRightString(A4[0] - 1.7 * cm, 0.9 * cm, f"strona {doc.page}")
    canvas.restoreState()


def render_table(rows):
    data = [[Paragraph(inline(cell.strip()), styles["BodyAstra"]) for cell in row] for row in rows]
    widths = [15.5 * cm / len(rows[0])] * len(rows[0])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6C4C0B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "AstraBold"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5C8A8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBF8F1")]),
    ]))
    return table


def build():
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    story, index = [], 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line == "---":
            index += 1
            continue
        if line.startswith("```"):
            code, index = [], index + 1
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            story.append(Preformatted("\n".join(code), styles["CodeAstra"]))
            index += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                if not re.match(r"^\|[\s:|-]+\|$", lines[index]):
                    table_lines.append([part.strip() for part in lines[index].strip("|").split("|")])
                index += 1
            if table_lines:
                story.append(render_table(table_lines))
                story.append(Spacer(1, 7))
            continue
        if line.startswith("# "):
            story.append(Spacer(1, 2.0 * cm))
            story.append(Paragraph(inline(line[2:]), styles["TitleAstra"]))
            index += 1
            continue
        if line.startswith("## "):
            if story and len(story) > 4:
                story.append(PageBreak())
            story.append(Paragraph(inline(line[3:]), styles["H1Astra"]))
            index += 1
            continue
        if line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), styles["H2Astra"]))
            index += 1
            continue
        if re.match(r"^\d+\. ", line):
            story.append(Paragraph(inline(line), styles["BodyAstra"]))
            index += 1
            continue
        if line.startswith("- "):
            story.append(Paragraph("• " + inline(line[2:]), styles["BodyAstra"]))
            index += 1
            continue
        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not re.match(r"^(#|\||```|- |\d+\. )", lines[index]):
            paragraph.append(lines[index])
            index += 1
        story.append(Paragraph(inline(" ".join(paragraph)), styles["BodyAstra"]))

    doc = SimpleDocTemplate(
        str(TARGET), pagesize=A4, title="Astra Jet — architektura systemu od A do Z",
        author="AstralJet", leftMargin=1.7 * cm, rightMargin=1.7 * cm,
        topMargin=1.5 * cm, bottomMargin=1.8 * cm,
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(TARGET)


if __name__ == "__main__":
    build()
