#!/usr/bin/env python3
"""Build the decision brief and detailed DOCX report from the included snapshot.

Run from this directory after installing requirements:
    python build_report.py

It reruns the deterministic analysis from reviews.csv, regenerates chart assets,
then creates the Word reports. Export the DOCX files to PDF using Word or LibreOffice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).parent
OUT = ROOT / "output"
CHARTS = OUT / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from moveinsync_ratings_monitor import analyze, prepare  # noqa: E402

NAVY = "17324D"
NAVY2 = "214761"
TEAL = "0F766E"
MINT = "E4F4F1"
PALE = "F1F5F8"
LIGHT_BLUE = "E7EFF5"
GOLD = "C58B28"
CORAL = "C65D4B"
INK = "202B36"
GRAY = "5E6B78"
MID_GRAY = "D8E1E8"
WHITE = "FFFFFF"
FONT = "Aptos"
DISPLAY = "Aptos Display"
PAGE_W = 7.2


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=95, start=110, bottom=95, end=110) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def set_table_borders(table, color=MID_GRAY, size="4") -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def format_run(run, size=9, bold=False, color=INK, font=FONT, italic=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = rgb(color)


def clear_cell(cell):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    return p


def add_field(paragraph, code: str):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = code
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, separate, text, end])
    format_run(run, size=8, color=GRAY)


def add_hyperlink(paragraph, text: str, url: str, color=TEAL):
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    rpr.append(c)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rpr.append(u)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)
    return hyperlink


def setup_doc(doc: Document, compact=False, footer_note="PUBLIC REVIEW ANALYSIS  |  SNAPSHOT: 13 OCT 2026"):
    sec = doc.sections[0]
    sec.page_width = Inches(8.5)
    sec.page_height = Inches(11)
    sec.top_margin = Inches(0.55 if compact else 0.62)
    sec.bottom_margin = Inches(0.55 if compact else 0.62)
    sec.left_margin = Inches(0.64 if compact else 0.68)
    sec.right_margin = Inches(0.64 if compact else 0.68)
    sec.header_distance = Inches(0.25)
    sec.footer_distance = Inches(0.25)
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(9.1 if not compact else 8.8)
    normal.font.color.rgb = rgb(INK)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.06
    for sty, size, color in (("Title", 28, NAVY), ("Heading 1", 19, NAVY), ("Heading 2", 12, TEAL), ("Heading 3", 10, NAVY2)):
        s = styles[sty]
        s.font.name = DISPLAY
        s.font.size = Pt(size)
        s.font.bold = True
        s.font.color.rgb = rgb(color)
        s.paragraph_format.space_before = Pt(10 if sty != "Title" else 0)
        s.paragraph_format.space_after = Pt(5)
        s.paragraph_format.keep_with_next = True
    header = sec.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    header.paragraph_format.space_after = Pt(0)
    r = header.add_run("MOVEINSYNC  /  EMPLOYEE APP EXPERIENCE")
    format_run(r, 7.5, True, TEAL, DISPLAY)
    # Fine rule beneath the header.
    p_pr = header._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "8")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), TEAL)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.paragraph_format.space_before = Pt(0)
    r = footer.add_run(footer_note + "     •     ")
    format_run(r, 7.3, False, GRAY)
    add_field(footer, "PAGE")
    doc.core_properties.title = "MoveInSync Play Store Ratings: Diagnosis & Action Plan"
    doc.core_properties.subject = "Forward Deployed Engineer candidate assignment"
    doc.core_properties.author = "Candidate Submission"
    doc.core_properties.keywords = "MoveInSync, Play Store reviews, product operations, review monitoring"


def kicker(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text.upper())
    format_run(r, 8, True, TEAL, DISPLAY)
    return p


def section_heading(doc, number, title, subtitle=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(f"{number}  /  ")
    format_run(r, 10, True, TEAL, DISPLAY)
    r = p.add_run(title)
    format_run(r, 18, True, NAVY, DISPLAY)
    if subtitle:
        p2 = doc.add_paragraph(subtitle)
        p2.paragraph_format.space_after = Pt(7)
        for rr in p2.runs:
            format_run(rr, 9, False, GRAY)
    return p



def page_heading(doc, number, title, subtitle=None):
    """Create a section heading that starts a new page without orphaning a break paragraph."""
    heading = section_heading(doc, number, title, subtitle)
    heading.paragraph_format.page_break_before = True
    return heading

def add_para(doc, text, size=9.2, color=INK, bold_lead=None, italic=False, after=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        format_run(r, size, True, color, italic=italic)
        r = p.add_run(text[len(bold_lead):])
        format_run(r, size, False, color, italic=italic)
    else:
        r = p.add_run(text)
        format_run(r, size, False, color, italic=italic)
    return p


def add_bullet(doc, text, size=9.1, color=INK, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.20)
    p.paragraph_format.first_line_indent = Inches(-0.12)
    p.paragraph_format.space_after = Pt(2.5)
    # Keep list bullets independent of the next page-breaking section heading.
    # This prevents a final bullet from being stranded on a nearly blank page.
    p.paragraph_format.keep_with_next = False
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        format_run(r, size, True, color)
        r = p.add_run(text[len(bold_lead):])
        format_run(r, size, False, color)
    else:
        r = p.add_run(text)
        format_run(r, size, False, color)
    return p


def callout(doc, title, body, fill=LIGHT_BLUE, accent=TEAL, title_size=9, body_size=9.3):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    t.columns[0].width = Inches(PAGE_W)
    c = t.cell(0, 0)
    set_cell_shading(c, fill)
    set_cell_margins(c, 130, 160, 130, 160)
    p = clear_cell(c)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(title.upper())
    format_run(r, title_size, True, accent, DISPLAY)
    p2 = c.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    p2.paragraph_format.line_spacing = 1.04
    r = p2.add_run(body)
    format_run(r, body_size, False, INK)
    prevent_row_split(t.rows[0])
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return t


def metric_tiles(doc, items, small=False):
    t = doc.add_table(rows=1, cols=len(items))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    widths = PAGE_W / len(items)
    for i, (value, label, note) in enumerate(items):
        c = t.cell(0, i)
        c.width = Inches(widths)
        set_cell_shading(c, NAVY if i == 0 else (NAVY2 if i == 1 else PALE))
        set_cell_margins(c, 135 if not small else 105, 115, 120 if not small else 90, 115)
        p = clear_cell(c)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(value)
        format_run(r, 18 if not small else 15, True, WHITE if i < 2 else NAVY, DISPLAY)
        p2 = c.add_paragraph()
        p2.paragraph_format.space_after = Pt(2)
        r = p2.add_run(label.upper())
        format_run(r, 7.3, True, "CDE5E1" if i < 2 else TEAL, DISPLAY)
        p3 = c.add_paragraph()
        p3.paragraph_format.space_after = Pt(0)
        r = p3.add_run(note)
        format_run(r, 7.4, False, WHITE if i < 2 else GRAY)
        c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    prevent_row_split(t.rows[0])
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return t


def styled_table(doc, headers, rows, widths=None, font_size=8.4, header_size=8.0, row_shading=True):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    if widths:
        for i, w in enumerate(widths):
            t.columns[i].width = Inches(w)
    header = t.rows[0]
    set_repeat_table_header(header)
    prevent_row_split(header)
    for i, text in enumerate(headers):
        c = header.cells[i]
        if widths:
            c.width = Inches(widths[i])
        set_cell_shading(c, NAVY)
        set_cell_margins(c, 90, 100, 90, 100)
        p = clear_cell(c)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(str(text))
        format_run(r, header_size, True, WHITE, DISPLAY)
        c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        prevent_row_split(t.rows[-1])
        for i, val in enumerate(row):
            c = cells[i]
            if widths:
                c.width = Inches(widths[i])
            if row_shading and ri % 2 == 1:
                set_cell_shading(c, PALE)
            set_cell_margins(c, 65, 100, 65, 100)
            p = clear_cell(c)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            r = p.add_run(str(val))
            format_run(r, font_size, False, INK)
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    set_table_borders(t)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return t


def action_card(doc, phase, title, evidence, next_step, owner, measure, accent=TEAL):
    t = doc.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    t.columns[0].width = Inches(1.18)
    t.columns[1].width = Inches(PAGE_W - 1.18)
    left, right = t.rows[0].cells
    left.width = Inches(1.18)
    right.width = Inches(PAGE_W - 1.18)
    set_cell_shading(left, accent)
    set_cell_margins(left, 100, 95, 100, 95)
    lp = clear_cell(left)
    lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = lp.add_run(phase.upper())
    format_run(r, 8, True, WHITE, DISPLAY)
    lp2 = left.add_paragraph()
    lp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    lp2.paragraph_format.space_after = Pt(0)
    r = lp2.add_run(evidence)
    format_run(r, 7.2, False, WHITE)
    set_cell_shading(right, PALE)
    set_cell_margins(right, 100, 140, 100, 140)
    rp = clear_cell(right)
    rp.paragraph_format.space_after = Pt(2)
    r = rp.add_run(title)
    format_run(r, 10, True, NAVY, DISPLAY)
    for label, value in (("Do next: ", next_step), ("Owner: ", owner), ("Measure: ", measure)):
        p = right.add_paragraph()
        p.paragraph_format.space_after = Pt(1.3)
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(label)
        format_run(r, 8.1, True, TEAL)
        r = p.add_run(value)
        format_run(r, 8.1, False, INK)
    prevent_row_split(t.rows[0])
    set_table_borders(t, color="DCE6EC", size="5")
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return t


def setup_chart_style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.labelcolor": "#5E6B78",
        "xtick.color": "#5E6B78",
        "ytick.color": "#5E6B78",
        "text.color": "#202B36",
        "axes.edgecolor": "#D8E1E8",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    })


def make_monthly_chart(monthly: pd.DataFrame) -> Path:
    m = monthly.copy()
    m["month"] = pd.to_datetime(m["month"])
    labels = [x.strftime("%b '%y") for x in m["month"]]
    x = np.arange(len(m))
    score = m["mean_score"].astype(float).to_numpy()
    one = m["one_star_share"].astype(float).to_numpy() * 100
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9.2, 4.6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    fig.subplots_adjust(left=0.08, right=0.97, top=0.91, bottom=0.16, hspace=0.12)
    ax1.plot(x, score, color="#0F766E", lw=2.4, marker="o", markersize=5.5, zorder=3)
    ax1.fill_between(x, score, 3.4, color="#0F766E", alpha=0.08)
    ax1.axhline(3.84, color="#8796A4", lw=1, ls=(0, (4, 3)))
    ax1.text(11.35, 3.855, "365-day mean 3.84", ha="right", va="bottom", fontsize=7.5, color="#5E6B78")
    ax1.set_ylim(3.35, 4.2)
    ax1.set_ylabel("Mean star score")
    ax1.set_yticks([3.4, 3.6, 3.8, 4.0, 4.2])
    ax1.grid(axis="y", color="#E7EDF1", lw=0.8)
    # Label only the lowest month and the latest month to protect legibility.
    low_i = int(np.argmin(score))
    last_i = len(score) - 1
    for idx, dy in [(low_i, -15), (last_i, 8)]:
        ax1.annotate(f"{score[idx]:.2f}", (x[idx], score[idx]), xytext=(0, dy), textcoords="offset points", ha="center", fontsize=8, fontweight="bold", color="#17324D")
    ax2.bar(x, one, color=["#C65D4B" if v >= 27 else "#A8B8C6" for v in one], width=0.62)
    ax2.set_ylim(0, max(35, float(np.ceil(one.max() / 5) * 5)))
    ax2.set_ylabel("1-star (%)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=0, fontsize=7.4)
    ax2.grid(axis="y", color="#E7EDF1", lw=0.8)
    ax2.set_axisbelow(True)
    fig.suptitle("Written-review sentiment fluctuates; low-star share remains material", x=0.08, y=0.99, ha="left", fontsize=11.3, fontweight="bold", color="#17324D")
    path = CHARTS / "monthly_review_trend.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def make_theme_chart(mentions: pd.DataFrame) -> Path:
    xdf = mentions.head(8).copy().sort_values("reviews_with_mention", ascending=True)
    labels = [x.replace(" / ", " /\n") if len(x) > 27 else x for x in xdf["theme"].tolist()]
    vals = xdf["reviews_with_mention"].astype(int).to_numpy()
    share = xdf["share_of_low_reviews"].astype(float).to_numpy() * 100
    colors = ["#0F766E" if name in ("OTP / login / session", "Booking / schedule / roster") else "#9FB4C4" for name in xdf["theme"].tolist()]
    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    fig.subplots_adjust(left=0.31, right=0.95, top=0.88, bottom=0.15)
    y = np.arange(len(xdf))
    bars = ax.barh(y, vals, color=colors, height=0.62)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.1)
    ax.set_xlabel("Number of low-rated reviews with a keyword hit")
    ax.grid(axis="x", color="#E7EDF1", lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(vals) * 1.22)
    for bar, n, pctv in zip(bars, vals, share):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2, f"{n}  |  {pctv:.1f}%", va="center", fontsize=8, color="#17324D", fontweight="bold")
    fig.suptitle("Recurring signals in 843 low-rated reviews", x=0.03, y=0.98, ha="left", fontsize=11.3, fontweight="bold", color="#17324D")
    path = CHARTS / "theme_mentions.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path



def make_monthly_theme_chart() -> Path:
    """Plot monthly overlapping mention shares for the core chronic themes."""
    d = pd.read_csv(OUT / "monthly_theme_mentions.csv")
    chosen = [
        "OTP / login / session",
        "Booking / schedule / roster",
        "ETA / tracking / location",
        "Transport operations / driver / route",
        "General app reliability / performance",
    ]
    color_map = {
        "OTP / login / session": "#0F766E",
        "Booking / schedule / roster": "#214761",
        "ETA / tracking / location": "#C58B28",
        "Transport operations / driver / route": "#C65D4B",
        "General app reliability / performance": "#8098AC",
    }
    pivot = d[d.theme.isin(chosen)].pivot(index="month", columns="theme", values="share_of_low_reviews").fillna(0)
    pivot = pivot.sort_index()
    fig, ax = plt.subplots(figsize=(9.2, 4.25))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.82, bottom=0.18)
    x = np.arange(len(pivot))
    for name in chosen:
        if name not in pivot.columns:
            continue
        ax.plot(x, pivot[name].values * 100, marker="o", markersize=3.7, lw=1.9, label=name,
                color=color_map[name])
    ax.set_xticks(x)
    ax.set_xticklabels([pd.Period(v, freq="M").strftime("%b '%y") for v in pivot.index], fontsize=7.6)
    ax.set_ylabel("Share of month's low-rated reviews (%)")
    ax.grid(axis="y", color="#E7EDF1", lw=0.8)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=7.4, ncol=2, loc="upper left", bbox_to_anchor=(0, 1.02))
    fig.suptitle("Chronic complaint themes recur across the year", x=0.02, y=0.99, ha="left",
                 fontsize=11.1, fontweight="bold", color="#17324D")
    path = CHARTS / "monthly_theme_mentions.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def make_impact_chart(impact: pd.DataFrame) -> Path:
    """Chart counterfactual per-theme changes to the written-review sample mean."""
    d = impact[impact.actionable_theme.astype(bool)].sort_values("sample_mean_uplift_if_to_4", ascending=False).head(5).copy()
    d = d.sort_values("sample_mean_uplift_if_to_4", ascending=True)
    labels = [x.replace(" / ", " /\n") if len(x) > 28 else x for x in d["primary_theme"]]
    vals = d["sample_mean_uplift_if_to_4"].astype(float).to_numpy()
    fig, ax = plt.subplots(figsize=(9.2, 3.25))
    fig.subplots_adjust(left=0.31, right=0.95, top=0.84, bottom=0.16)
    y = np.arange(len(d))
    bars = ax.barh(y, vals, color=["#0F766E" if v == vals.max() else "#9FB4C4" for v in vals], height=0.62)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.0)
    ax.set_xlabel("Arithmetic uplift in 365-day written-review mean (points)")
    ax.grid(axis="x", color="#E7EDF1", lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(vals) * 1.28 if len(vals) else 0.1)
    for bar, value in zip(bars, vals):
        ax.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height()/2, f"+{value:.3f}", va="center", fontsize=8.0,
                fontweight="bold", color="#17324D")
    fig.suptitle("Which category could move the written mean most?", x=0.02, y=0.99, ha="left",
                 fontsize=11.1, fontweight="bold", color="#17324D")
    path = CHARTS / "theme_impact_sensitivity.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path

def make_brief_impact_chart(impact: pd.DataFrame) -> Path:
    """Compact top-three impact chart for the one-page decision brief."""
    d = impact[impact.actionable_theme.astype(bool)].sort_values(
        "sample_mean_uplift_if_to_4", ascending=False
    ).head(3).copy().sort_values("sample_mean_uplift_if_to_4", ascending=True)
    short = {
        "OTP / login / session": "OTP / login",
        "Booking / schedule / roster": "Booking / roster",
        "ETA / tracking / location": "ETA / tracking",
    }
    labels = [short.get(str(x), str(x)) for x in d["primary_theme"]]
    vals = d["sample_mean_uplift_if_to_4"].astype(float).to_numpy()
    fig, ax = plt.subplots(figsize=(8.0, 1.12))
    fig.subplots_adjust(left=0.20, right=0.96, top=0.93, bottom=0.28)
    y = np.arange(len(d))
    bars = ax.barh(y, vals, color=["#0F766E" if v == vals.max() else "#9FB4C4" for v in vals], height=0.55)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.0)
    ax.set_xlim(0, max(vals) * 1.25 if len(vals) else 0.1)
    ax.set_xlabel("Counterfactual lift in 365-day written-review mean (points)", fontsize=7.0, labelpad=1)
    ax.grid(axis="x", color="#E7EDF1", lw=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=7.0, length=0)
    for bar, value in zip(bars, vals):
        ax.text(bar.get_width() + 0.0015, bar.get_y() + bar.get_height()/2, f"+{value:.3f}",
                va="center", fontsize=8.1, fontweight="bold", color="#17324D")
    for spine in ax.spines.values():
        spine.set_visible(False)
    path = CHARTS / "brief_theme_impact.png"
    fig.savefig(path, dpi=240, bbox_inches="tight", transparent=False)
    plt.close(fig)
    return path


def write_store_score_bridge(metadata: dict, df: pd.DataFrame, out_dir: Path | None = None) -> pd.DataFrame:
    """Estimate a crude equal-weight whole-listing score shift from affected star points.

    This is deliberately NOT a Google Play forecast: the public denominator is rounded and
    Google's visible score is recency-weighted. It avoids the erroneous shortcut of multiplying
    the written-sample mean change by the fraction of all historical written texts.
    """
    destination = out_dir or OUT
    impact = pd.read_csv(destination / "theme_impact_scenarios.csv")
    approximate_listing_count = int(metadata.get("store_reviews_count_approx", 115000))
    by_theme = impact.set_index("primary_theme")
    scenarios = [
        ("OTP/login primary theme only", ["OTP / login / session"]),
        ("OTP/login + booking primary themes", ["OTP / login / session", "Booking / schedule / roster"]),
    ]
    rows = []
    for label, theme_names in scenarios:
        selected = by_theme.loc[theme_names]
        written_mean_uplift = float(selected["sample_mean_uplift_if_to_4"].sum())
        affected_reviews = int(selected["low_reviews"].sum())
        star_points_added = int(selected["star_deficit_points_to_4"].sum())
        # Under a simple equal-weight mean only, each extra star-point contributes 1/N.
        naive_public_points = star_points_added / approximate_listing_count if approximate_listing_count else float("nan")
        rows.append({
            "scenario": label,
            "primary_theme_reviews_affected": affected_reviews,
            "star_points_added_if_all_affected_reviews_became_4": star_points_added,
            "written_sample_uplift_if_current_low_ratings_became_4": written_mean_uplift,
            "rounded_store_listing_count_used_as_approx_denominator": approximate_listing_count,
            "naive_equal_weight_whole_listing_score_points": naive_public_points,
            "interpretation": "Equal-weight arithmetic only: sum(4 - current star score) for affected written reviews divided by the rounded whole-listing rating count. The real Play score is recency-weighted; displayed count and rating are rounded, so this is an order-of-magnitude bridge, not a forecast.",
        })
    result = pd.DataFrame(rows)
    result.to_csv(destination / "store_score_bridge.csv", index=False)
    return result


def make_reply_chart(reply: pd.DataFrame) -> Path:
    xdf = reply[(reply["year"] >= 2023) & (reply["year"] <= 2026)].copy()
    x = np.arange(len(xdf))
    vals = xdf["reply_rate"].astype(float).to_numpy() * 100
    fig, ax = plt.subplots(figsize=(9.2, 3.8))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.84, bottom=0.2)
    bars = ax.bar(x, vals, width=0.56, color=["#0F766E" if int(y) == 2023 else ("#C65D4B" if int(y) == 2026 else "#9FB4C4") for y in xdf["year"]])
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(v)) + ("*" if str(int(v)) == "2026" else "") for v in xdf["year"]])
    ax.set_ylabel("Share of 1–2 star reviews with a developer reply")
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(axis="y", color="#E7EDF1", lw=0.8)
    ax.set_axisbelow(True)
    for bar, r in zip(bars, xdf.itertuples()):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 3, f"{r.reply_rate:.1%}\nn={int(r.low_reviews):,}", ha="center", va="bottom", fontsize=8.2, fontweight="bold", color="#17324D")
    ax.text(0.99, -0.19, "*2026 is year-to-date through 11 Oct", transform=ax.transAxes, ha="right", va="top", fontsize=7.5, color="#5E6B78")
    fig.suptitle("Public replies to negative reviews have nearly stopped", x=0.03, y=0.99, ha="left", fontsize=11.3, fontweight="bold", color="#17324D")
    path = CHARTS / "developer_response_trend.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_in_doc(doc, path: Path, width=6.85, caption=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(1)
    p.add_run().add_picture(str(path), width=Inches(width))
    if caption:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_after = Pt(5)
        r = cap.add_run(caption)
        format_run(r, 7.5, False, GRAY, italic=True)


def add_source_line(doc, metadata):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("Sources: ")
    format_run(r, 8, True, GRAY)
    add_hyperlink(p, "Google Play listing", metadata["store_source_url"])
    r = p.add_run("  |  ")
    format_run(r, 8, False, GRAY)
    add_hyperlink(p, "Google Play rating methodology", metadata["google_play_ratings_methodology_url"])
    r = p.add_run("  |  ")
    format_run(r, 8, False, GRAY)
    add_hyperlink(p, "iOS App Store listing", metadata["ios_listing_url"])
    r = p.add_run("  |  ")
    format_run(r, 8, False, GRAY)
    add_hyperlink(p, "Android version context (AppBrain)", metadata["android_version_tracker_url"])
    r = p.add_run(f"  |  Checked {metadata['store_listing_snapshot_date']}; displayed values are dated captures.")
    format_run(r, 8, False, GRAY)


def get_data():
    metadata = json.loads((ROOT / "snapshot_metadata.json").read_text(encoding="utf-8"))
    df_raw = pd.read_csv(ROOT / "reviews.csv")
    df = prepare(df_raw)
    result = analyze(df, meta=None, live=False, out_dir=OUT)
    windows = pd.read_csv(OUT / "rating_windows.csv")
    monthly = pd.read_csv(OUT / "monthly_trend.csv", parse_dates=["month"])
    themes = pd.read_csv(OUT / "theme_summary.csv")
    mentions = pd.read_csv(OUT / "theme_mentions.csv")
    replies = pd.read_csv(OUT / "developer_response_trend.csv")
    versions = pd.read_csv(OUT / "version_summary.csv", parse_dates=["last_seen"])
    write_store_score_bridge(metadata, df, OUT)
    return metadata, df, result, windows, monthly, themes, mentions, replies, versions


def create_main_report(metadata, df, windows, monthly, themes, mentions, replies, versions):
    doc = Document()
    setup_doc(doc)
    low_n = int(len(df[(df["at"] > df["at"].max() - pd.Timedelta(days=365)) & (df["score"] <= 3)]))
    theme = themes.set_index("theme")
    mention = mentions.set_index("theme")
    m30 = windows.loc[windows.window_days.eq(30)].iloc[0]
    m90 = windows.loc[windows.window_days.eq(90)].iloc[0]
    m365 = windows.loc[windows.window_days.eq(365)].iloc[0]
    impact_source = pd.read_csv(OUT / "theme_impact_scenarios.csv")
    otp_sensitivity = impact_source.loc[impact_source.primary_theme.eq("OTP / login / session")].iloc[0]
    booking_sensitivity = impact_source.loc[impact_source.primary_theme.eq("Booking / schedule / roster")].iloc[0]
    response_2023 = replies.loc[replies.year.eq(2023)].iloc[0]
    response_2026 = replies.loc[replies.year.eq(2026)].iloc[0]

    # PAGE 1: executive decision memo.
    kicker(doc, "Forward Deployed Engineer | Candidate Assignment")
    title = doc.add_paragraph(style="Title")
    title.paragraph_format.space_after = Pt(4)
    r = title.add_run("Make the commute\nfeel dependable again")
    format_run(r, 27, True, NAVY, DISPLAY)
    sub = doc.add_paragraph()
    sub.paragraph_format.space_after = Pt(7)
    r = sub.add_run("MoveInSync Employee App  |  Play Store ratings diagnosis & action plan")
    format_run(r, 11.2, True, GRAY)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    r = p.add_run(f"Review snapshot: {metadata['review_collection_window_start']} to {metadata['latest_review_timestamp']}  •  Collected {metadata['store_listing_snapshot_date']}")
    format_run(r, 8.2, False, GRAY)
    opening = doc.add_paragraph()
    opening.paragraph_format.space_after = Pt(6)
    bridge = pd.read_csv(OUT / "store_score_bridge.csv").set_index("scenario")
    otp_public_bridge = float(bridge.loc["OTP/login primary theme only", "naive_equal_weight_whole_listing_score_points"])
    add_opening = opening.add_run(f"DO FIRST: reply to negative reviews today; investigate OTP/login first. If all {int(otp_sensitivity.low_reviews)} OTP-primary low-rated reviews became 4 stars, the 365-day written mean would rise +{otp_sensitivity.sample_mean_uplift_if_to_4:.3f}; a crude equal-weight whole-listing bridge is only about +{otp_public_bridge:.3f} points (not a forecast).")
    format_run(add_opening, 8.6, True, NAVY2)

    metric_tiles(doc, [
        (f"{m30.mean_score:.2f}/5", "30-DAY WRITTEN MEAN", f"n = {int(m30.reviews):,} reviews"),
        (f"{m30.one_star_share:.1%}", "ONE-STAR SHARE", "Latest 30-day window"),
        (f"{m30.low_1_2_star_reply_rate:.1%}", "1–2 STAR REPLY RATE", f"{int(m30.low_1_2_star_replies)}/{int(m30.low_1_2_star_reviews)} replied"),
        (f"{int(mention.loc['OTP / login / session', 'reviews_with_mention'])}", "OTP / LOGIN MENTIONS", f"{mention.loc['OTP / login / session', 'share_of_low_reviews']:.1%} of {low_n:,} low-rated reviews"),
    ])

    callout(doc, "The decision", "The priority is to make the commute experience reliable, not to chase a higher star rating. Start by replying to recent negative reviews, then investigate sign-in and app-access failures. Reviews are useful clues, but app, booking and transport data should confirm the problem before the team commits to a fix.", fill=MINT, accent=TEAL, body_size=9.4)
    heading = doc.add_paragraph()
    heading.paragraph_format.space_after = Pt(4)
    r = heading.add_run("The first three moves")
    format_run(r, 12.2, True, NAVY, DISPLAY)
    moves = [
        ("01", "Reply and route", "Assign a daily owner for 1–2 star reviews; give people a real support path and escalate safety reports the same day."),
        ("02", "Protect the core journey", "Audit OTP/session delivery and reproduce the app-opening / installation-verification failures on affected device and OS combinations."),
        ("03", "Remove uncertainty", "Make booking status explicit, compare planned vs actual pickups and route performance, and never block app use behind a rating prompt."),
    ]
    styled_table(doc, ["ORDER", "MOVE", "WHAT TO DO"], moves, [0.55, 1.38, 5.27], font_size=8.6, header_size=7.8)
    add_para(doc, f"Listing context (captured {metadata['store_listing_snapshot_date']}): {metadata['store_score_display']}; {metadata['store_reviews_count_display']}. This is a rounded public listing snapshot, not an exact downloadable rating count. The written-review sample below is a separate, self-selected text dataset.", size=8.3, color=GRAY, after=2)

    # PAGE 2: rating signals.
    page_heading(doc, "01", "What the rating data says", "The store score tends to move slowly. Recent written reviews offer a more immediate view of what employees are reporting, although this sample has important limits.")
    chart = make_monthly_chart(monthly)
    chart_in_doc(doc, chart, width=6.85, caption="Monthly written-review mean and one-star share, Nov 2025–Oct 2026. October is partial through 11 Oct.")
    rows = []
    for _, r in windows.iterrows():
        rows.append([
            f"Last {int(r.window_days)} days",
            f"{int(r.reviews):,}",
            f"{r.mean_score:.2f}/5",
            f"{r.one_star_share:.1%}",
            f"{int(r.low_1_2_star_replies)}/{int(r.low_1_2_star_reviews)} ({r.low_1_2_star_reply_rate:.1%})",
        ])
    styled_table(doc, ["Window", "Reviews", "Mean score", "1 star", "1–2 star replies"], rows,
                 [1.20, 0.78, 1.0, 0.72, 2.85], font_size=8.4, header_size=7.7)
    all_time_written_mean = float(df["score"].mean())
    callout(doc, "Why the store score looks higher than the written reviews", f"The official India listing displayed {metadata['store_score_display']} and {metadata['store_reviews_count_display']} when checked on {metadata['store_listing_snapshot_date']}; the latest 365-day written-review sample averages {m365.mean_score:.2f}/5 and all 24,315 collected texts average {all_time_written_mean:.2f}/5. These are different measures: Google says the displayed Play rating is weighted toward recent ratings, most raters do not necessarily write text, this sample is self-selected and English-only, and reviews older than 365 days average {df.loc[df['at'] < (df['at'].max() - pd.Timedelta(days=365)), 'score'].mean():.2f}/5. The main warning sign is the lower 30-day mean ({m30.mean_score:.2f}) compared with the 90-day ({m90.mean_score:.2f}) and 365-day ({m365.mean_score:.2f}) means. Month-to-month figures vary, so this is not proof of a steady decline. Context: iOS displays {metadata['ios_store_score_display']} from {metadata['ios_ratings_count_display'].split(' (')[0]}, versus Android {metadata['store_score_display']} - a 0.4-star gap that supports investigating Android auth/install/launch friction, but is not proof of Android causality. The text-row/listing-count ratio (~21%) is only a rough scale comparison, not a measured coverage rate.", fill=LIGHT_BLUE, accent=NAVY2, body_size=8.05)
    callout(doc, "Interpretation", f"{m30.one_star_share:.1%} of the latest 30-day written reviews are one star. Investigate dips alongside release history and operational context rather than assuming a cause.", fill=MINT, accent=TEAL, body_size=8.8)
    v = versions[versions.appVersion.astype(str).eq("12.19.0")]
    if not v.empty:
        vr = v.iloc[0]
        add_para(doc, f"Platform version context (not a causal claim): {int(vr.reviews)} review rows carry Android review metadata label `12.19.0` (mean {vr.mean_score:.2f}/5; {vr.one_star_share:.1%} one star). A third-party Android listing tracker showed `12.20.0` as the available Android version on 12 Oct 2026, while the Apple App Store release history showed iOS `10.50.0` around 6 Oct. These appear to be separate Android and iOS release-numbering sequences; the 12.19.0 reviews likely refer to a preceding Android build, but confirm against Play Console rollout metadata before tying a spike to a release.", size=8.3, color=INK, bold_lead="Platform version context (not a causal claim):", after=1)
    add_para(doc, "Appendix A pairs dated public review excerpts (without reviewer profile details) with suggested engineering and operations tickets. The excerpts show what people reported, not independently verified incidents.", size=8.0, color=GRAY, after=1)

    # PAGE 3: theme diagnosis.
    page_heading(doc, "02", "What low-rated reviews mention", f"This section looks at {low_n:,} one-, two- and three-star reviews from the latest 365 days. They help flag issues worth investigating, but they cannot tell us how often those problems occur across all trips.")
    chart = make_theme_chart(mentions)
    chart_in_doc(doc, chart, width=6.85, caption="Keyword matches across low-rated reviews. A review can mention more than one issue, so the percentages overlap and should not be added together.")
    top_primary = themes[~themes.theme.eq("No specific detail / other")].head(7)
    primary_rows = [[r.theme, int(r.reviews), f"{r.share_of_low_reviews:.1%}", r.owner] for r in top_primary.itertuples()]
    add_para(doc, "Largest primary themes (one label per review; selected categories)", size=8.5, color=NAVY, bold_lead="Largest primary themes", after=1)
    styled_table(doc, ["Primary theme", "Reviews", "Share of low-rated set", "Suggested owner"], primary_rows,
                 [2.42, 0.72, 1.18, 2.23], font_size=7.8, header_size=7.5)
    shown_names = set(top_primary.theme.tolist())
    smaller_primary = themes[~themes.theme.eq("No specific detail / other") & ~themes.theme.isin(shown_names)]
    if not smaller_primary.empty:
        extras = "; ".join(f"{r.theme}: {int(r.reviews)} ({r.share_of_low_reviews:.1%})" for r in smaller_primary.itertuples())
        add_para(doc, "Other labelled primary themes: " + extras + ".", size=7.5, color=GRAY, after=1)
    other_count = int((themes.theme == "No specific detail / other").map(lambda x: 0).sum())
    other_row = themes[themes.theme.eq("No specific detail / other")]
    if not other_row.empty:
        other_n = int(other_row.iloc[0].reviews)
        other_pct = float(other_row.iloc[0].share_of_low_reviews)
    else:
        other_n, other_pct = 0, 0.0
    manual = pd.read_csv(OUT / "manual_review_queue.csv")
    short_unmatched = int(manual.content.fillna("").str.split().str.len().le(3).sum())
    callout(doc, "Do not discard the unmatched bucket", f"{other_n} reviews ({other_pct:.1%}) have no primary-theme match; {short_unmatched} contain three words or fewer. Longer comments are in output/manual_review_queue.csv for manual review. No match means the rules missed the wording, not that the complaint is unimportant.", fill="FFF5E5", accent=GOLD, body_size=8.7)
    add_para(doc, "What stands out", size=9.3, color=NAVY, bold_lead="What stands out", after=2)
    add_bullet(doc, f"Login and OTP complaints can stop an employee before the commute even starts: {int(mention.loc['OTP / login / session', 'reviews_with_mention'])} reviews mention authentication. Check actual OTP delivery and verification rates before changing providers or retry logic.", size=8.5)
    add_bullet(doc, f"Booking and ETA need separate checks. {int(mention.loc['Booking / schedule / roster', 'reviews_with_mention'])} reviews mention booking or scheduling, while {int(mention.loc['ETA / tracking / location', 'reviews_with_mention'])} mention tracking, location or ETA. Compare the first with booking outcomes and the second with actual pickup times.", size=8.5)

    # PAGE 4: counterfactual impact + employee journey.
    page_heading(doc, "03", "Which fix has the largest possible rating impact?", "The scenarios below show how the mean of the same 2,848 written reviews would change under specific assumptions. They are not forecasts of how the public Play Store score would respond to an engineering fix.")
    impact = pd.read_csv(OUT / "theme_impact_scenarios.csv")
    impact_chart = make_impact_chart(impact)
    chart_in_doc(doc, impact_chart, width=6.7, caption="Counterfactual change in the 365-day written-review mean if every low-rated review in one primary-theme group were changed to 4 stars.")
    actionable = impact[impact.actionable_theme.astype(bool)].sort_values("sample_mean_uplift_if_to_4", ascending=False).head(6)
    impact_rows = [[r.primary_theme, int(r.low_reviews), f"+{r.sample_mean_uplift_if_to_4:.3f}", f"{r.sample_mean_if_to_4:.2f}", f"+{r.sample_mean_uplift_if_to_5:.3f}"] for r in actionable.itertuples()]
    styled_table(doc, ["Primary theme", "n low-rated", "Uplift if all to 4★", "Sample mean after", "Uplift if all to 5★"], impact_rows,
                 [2.45, 0.78, 1.12, 1.15, 1.18], font_size=7.2, header_size=6.8)
    recent_365 = df[df["at"] > (df["at"].max() - pd.Timedelta(days=365))].copy()
    low_365 = recent_365[recent_365["score"] <= 3]
    impact_base = float(recent_365["score"].mean())
    impact_all4 = float((recent_365["score"].sum() + (4 - low_365["score"]).sum()) / len(recent_365))
    impact_all5 = float((recent_365["score"].sum() + (5 - low_365["score"]).sum()) / len(recent_365))
    callout(doc, "The upper bound", f"The 365-day written-review mean is {impact_base:.2f}/5. If every one of the {len(low_365)} one-to-three-star reviews in that sample became 4 stars, the arithmetic mean would be {impact_all4:.2f}; if every one became 5 stars, {impact_all5:.2f}. This intentionally extreme scenario assumes all low-rated reviewers change their score and all other ratings remain fixed. It is not a forecast, and it does not calculate the public Play Store score.", fill="FFF5E5", accent=GOLD, body_size=8.0)
    stages = pd.read_csv(OUT / "journey_stage_summary.csv")
    stages = stages[~stages.journey_stage.eq("Unclear / no actionable detail")].sort_values("star_deficit_points_to_4", ascending=False).head(5)
    stage_rows = [[r.journey_stage, int(r.primary_low_reviews), f"{r.share_of_low_reviews:.1%}", int(r.star_deficit_points_to_4)] for r in stages.itertuples()]
    add_para(doc, "Where the journey is losing the most stars", size=9, color=NAVY, bold_lead="Where the journey is losing the most stars", after=1)
    styled_table(doc, ["Mapped journey stage", "Primary-tag reviews", "Share of all low-rated", "Points needed to reach 4★"], stage_rows,
                 [2.55, 1.20, 1.30, 1.63], font_size=7.4, header_size=7.0)
    otp_impact_row = impact.loc[impact.primary_theme.eq("OTP / login / session")].iloc[0]
    add_para(doc, f"Among reviews that could be assigned to a journey stage, self-booking and roster issues form the largest group. The {other_n} unmatched reviews are not included in this ranking, and none of these counts should be read as incident rates. Appendix B lists every primary theme and shows the hypothetical result if its current 1–3-star reviews became 4 or 5 stars. The largest actionable single-theme scenario is OTP/login: the written mean would rise by +{otp_impact_row.sample_mean_uplift_if_to_4:.3f} if all {int(otp_impact_row.low_reviews)} primary-theme reviews moved to 4 stars ({m365.mean_score:.2f} to {otp_impact_row.sample_mean_if_to_4:.2f}), with every other score unchanged.", size=8.0, color=GRAY, after=1)

    # PAGE 5: trend chart for primary issue mentions over time.
    page_heading(doc, "04", "Which complaints are chronic, and which are spiking?", "Each month's percentages use that month's 1–3-star written reviews as the denominator. Since the number of reviews changes, smaller months should be interpreted with extra care.")
    trend_chart = make_monthly_theme_chart()
    chart_in_doc(doc, trend_chart, width=6.75, caption="Multi-label mention share among each month's low-rated written reviews, Nov 2025–Oct 2026. Reviews may appear in multiple themes; October is partial through 11 Oct.")
    monthly_mentions = pd.read_csv(OUT / "monthly_theme_mentions.csv")
    chronic_names = ["OTP / login / session", "Booking / schedule / roster", "ETA / tracking / location", "Transport operations / driver / route", "General app reliability / performance", "Support / escalation"]
    trend_rows = []
    for name in chronic_names:
        one_theme = monthly_mentions[monthly_mentions.theme.eq(name)].copy()
        if one_theme.empty:
            continue
        peak = one_theme.loc[one_theme.share_of_low_reviews.idxmax()]
        present = int((one_theme.reviews_with_mention > 0).sum())
        trend_rows.append([name, f"{present}/12 months", f"{peak.month}: {int(peak.reviews_with_mention)}/{int(peak.low_reviews)} ({peak.share_of_low_reviews:.1%})"])
    styled_table(doc, ["Theme (multi-label mentions)", "Months present", "Peak month in sample"], trend_rows,
                 [2.85, 1.15, 2.68], font_size=7.6, header_size=7.2)
    app_launch = monthly_mentions[monthly_mentions.theme.eq("App launch / crash")].copy()
    installer = monthly_mentions[monthly_mentions.theme.eq("Install verification / Play Store error")].copy()
    if not app_launch.empty and not installer.empty:
        peak_launch = app_launch.loc[app_launch.share_of_low_reviews.idxmax()]
        peak_install = installer.loc[installer.share_of_low_reviews.idxmax()]
        add_para(doc, f"Two spikes stand out for follow-up: app launch/crash mentions peaked in {peak_launch.month} at {int(peak_launch.reviews_with_mention)}/{int(peak_launch.low_reviews)} low-rated reviews ({peak_launch.share_of_low_reviews:.1%}), while installer/Play Store-error mentions peaked in {peak_install.month} at {int(peak_install.reviews_with_mention)}/{int(peak_install.low_reviews)} ({peak_install.share_of_low_reviews:.1%}). Review metadata shows Android label `12.19.0`; a third-party Android tracker showed `12.20.0` as available on 12 Oct 2026. These are directionally compatible as prior/current Android releases, unlike iOS `10.50.0`, which belongs to the Apple listing. Confirm exact Android build and rollout dates in Play Console before associating a spike with a release.", size=8.1, color=INK, after=3)
    callout(doc, "Chronic vs spike", "OTP, booking, ETA, transport operations, broad reliability and support mentions appear in all 12 sampled months - treat them as chronic monitoring lanes. App-launch complaints appear in 11/12 months and peaked in August; installer errors are less persistent and also peaked in August, making them a focused spike to investigate first. These patterns describe what appears in written reviews; they are not confirmed incident rates.", fill=LIGHT_BLUE, accent=NAVY2, body_size=8.2)

    # PAGE 6: response gap. Use page_break_before on the heading so a full prior page
    # cannot leave behind a blank page-break paragraph.
    response_heading = section_heading(doc, "05", "A response gap the team can close now", "Public replies are not a substitute for fixing the product, and a missing reply does not prove that a support case is still open. They do show whether the team is acknowledging low ratings on the store listing.")
    response_heading.paragraph_format.page_break_before = True
    chart = make_reply_chart(replies)
    chart_in_doc(doc, chart, width=6.85, caption="Developer replies among 1–2 star reviews by calendar year. 2026 is year-to-date through 11 Oct.")
    focus_years = replies[replies.year.isin([2023, 2024, 2025, 2026])]
    response_rows = [[int(r.year), f"{int(r.low_reviews):,}", f"{int(r.replies):,}", f"{r.reply_rate:.1%}", r.period] for r in focus_years.itertuples()]
    styled_table(doc, ["Year", "1–2 star reviews", "Replies", "Reply rate", "Period"], response_rows,
                 [0.8, 1.38, 0.78, 0.90, 2.69], font_size=8.1, header_size=7.7)
    callout(doc, "The operating move", f"The public reply rate in this snapshot dropped from {response_2023.reply_rate:.1%} in 2023 to {response_2026.reply_rate:.1%} in 2026 year-to-date. Start with the newest unanswered reviews and use a useful template plus a real support route. Track reply rate separately from issue resolution; public review data cannot tell us whether a complaint was resolved privately.", fill=MINT, accent=TEAL, body_size=9)
    add_para(doc, "For the latest 30 days, only 1 of 73 one- and two-star reviews had a developer reply (1.4%). Over 90 days it was 2 of 205 (1.0%); over 365 days, 29 of 769 (3.8%).", size=8.7, color=GRAY, after=0)

    # PAGE 5: first 7 days.
    page_heading(doc, "06", "The first seven days", "This order reflects likely impact on employees, the strength of the available evidence, and how quickly the team can act. Use it as a starting point; review counts are not incident rates.")
    action_card(doc, "Today", "Restart the low-star response loop", "1.4% replied\nin 30 days", "Assign one daily owner. Reply to the newest 1–2 star reviews with a specific next step and support/ticket route; escalate any safety or harassment report the same day.", "Customer Success + Support", "Reply coverage and response time in the support workflow; track case resolution separately.", accent=TEAL)
    action_card(doc, "Days 1–2", "Instrument and fix OTP / session failures", f"{int(mention.loc['OTP / login / session', 'reviews_with_mention'])} mentions", "Break down OTP delivery, verification and session expiry by provider/carrier, device and time of day. Reproduce morning login failures; add safe resend/fallback only after checking the failure mode.", "Authentication backend + Android", "Baseline delivery/verification success and login failure rate; set an SLO with engineering once baseline is known.", accent=NAVY2)
    launch_n = int(theme.loc["App launch / crash", "reviews"]) if "App launch / crash" in theme.index else 0
    install_n = int(theme.loc["Install verification / Play Store error", "reviews"]) if "Install verification / Play Store error" in theme.index else 0
    action_card(doc, "Days 1–2", "Reproduce app-opening and installer errors", f"{launch_n + install_n} primary tags", "Use Android vitals and crash/ANR traces. Reproduce the 'not installed' message and post-update launch failure across affected device/OS combinations; verify installer/integrity checks rather than guessing at the cause.", "Android engineering", "Launch success, crash-free / ANR sessions, and install-verification error count by release/device.", accent=NAVY2)
    book_n = int(theme.loc["Booking / schedule / roster", "reviews"]) if "Booking / schedule / roster" in theme.index else 0
    book_pct = float(theme.loc["Booking / schedule / roster", "share_of_low_reviews"]) if "Booking / schedule / roster" in theme.index else 0.0
    action_card(doc, "Week 1", "Make booking state impossible to misread", f"{book_n} primary\ntags ({book_pct:.1%})", "Show confirmed, waitlisted and cancelled as explicit states. Fix contradictory 'trip not booked' pushes; explain cancellation/no-show consequences before confirmation and add a dispute route.", "Product + Design + Backend", "Booking success/failure, contradictory notifications, waitlist disputes and no-show appeals.", accent=GOLD)
    action_card(doc, "Week 1", "Validate ETA and live tracking", f"{int(mention.loc['ETA / tracking / location', 'reviews_with_mention'])} mentions", "Join predicted pickup ETAs to actual arrival timestamps for a representative sample of routes, shifts and vendors. Report median and P90 error; check tracking availability and map freshness separately.", "Routing + Transport Operations", "Median/P90 ETA error, share of trips with live tracking available, late-pickup rate.", accent=TEAL)

    # PAGE 6: next sprint and metrics.
    page_heading(doc, "07", "The next sprint and how to measure it", "For the next sprint, focus on the steps employees depend on most: booking a ride, finding the pickup, and boarding on time.")
    action_card(doc, "Next sprint", "Reduce repeat late-cab and route failures", f"{int(mention.loc['Transport operations / driver / route', 'reviews_with_mention'])} mentions", "Group complaints by route, shift, vendor, site and pickup window. Compare planned vs actual pickup, journey time and route detours; review the largest recurring clusters with the transport desk and vendor, then assign corrective actions.", "Transport Operations + Vendor Management + Routing", "Late-pickup rate, P90 delay, excess journey time, and repeat complaints per route/vendor.", accent=TEAL)
    action_card(doc, "Next sprint", "Give employees a visible issue path", f"{int(mention.loc['Support / escalation', 'reviews_with_mention'])} mentions", "Add 'Report an issue' on the trip screen with issue type, ticket reference, current status and routing to the employee's transport desk. Keep driver/no-show complaints distinct from app bugs.", "Product + Support + Operations", "Issue-submission completion, first-response time, resolution rate and reopened cases.", accent=NAVY2)
    action_card(doc, "Next release", "Remove forced-rating friction", f"{int(mention.loc['Rating prompts / notifications', 'reviews_with_mention'])} mentions", "Make post-ride rating optional and skippable. Never gate booking, OTP access or viewing trip details behind a rating. Keep rating requests separate from safety or issue reporting.", "Product + Android", "Task completion and rating-prompt dismissal; forced-rating complaints should trend toward zero.", accent=NAVY2)
    action_card(doc, "Every release", "Use staged rollout and release notes", "Guardrail", "Roll out gradually. At a defined checkpoint, inspect crash/ANR telemetry and recent review signals. A version with at least 30 reviews and mean below 3.50 is an investigation trigger, not an automatic rollback rule.", "Engineering + Release", "Crash/ANR changes, version sample size, release timing and validated defects.", accent=GOLD)

    heading = doc.add_paragraph()
    heading.paragraph_format.space_before = Pt(3)
    heading.paragraph_format.space_after = Pt(4)
    r = heading.add_run("30-day scorecard")
    format_run(r, 11.5, True, NAVY, DISPLAY)
    scorecard = [
        ["Response loop", "1.4% reply coverage in latest 30 days", "Target ≥80% of 1–2 star reviews receive a useful public reply within 48h; verify timing in the team's response workflow."],
        ["Login / OTP", f"{int(mention.loc['OTP / login / session', 'reviews_with_mention'])} of {low_n} low-rated reviews contain a keyword match", "Capture a baseline by provider/device first, then set a delivery/verification SLO."],
        ["Booking state", f"{int(theme.loc['Booking / schedule / roster', 'reviews'])} primary labels", "Track booking success, waitlist clarity and disputes in product telemetry."],
        ["ETA / tracking", f"{int(mention.loc['ETA / tracking / location', 'reviews_with_mention'])} keyword matches", "Baseline median/P90 ETA error and tracking freshness from actual trips."],
        ["Support resolution", f"{int(mention.loc['Support / escalation', 'reviews_with_mention'])} keyword matches", "Track first response, time to resolution and repeat complaints; public replies alone are insufficient."],
        ["Transport ops", f"{int(mention.loc['Transport operations / driver / route', 'reviews_with_mention'])} keyword matches", "Track late pickups and P90 delay by route/vendor; review recurring detours and repeat complaints."],
    ]
    styled_table(doc, ["Workstream", "Public-review baseline", "30-day measure"], scorecard,
                 [1.18, 2.10, 3.87], font_size=7.6, header_size=7.5)

    # PAGE 7: method, limitations and sources.
    page_heading(doc, "08", "Method, limits and reproducibility", "The recommendations are only useful if the team can see what the evidence supports and what still needs checking.")
    heading = doc.add_paragraph()
    heading.paragraph_format.space_after = Pt(2)
    r = heading.add_run("Scope and source")
    format_run(r, 11.1, True, NAVY, DISPLAY)
    add_para(doc, f"This analysis uses a saved snapshot of {len(df):,} public, English-language written reviews from the India Play Store listing for {metadata['package_id']}, dated {metadata['review_collection_window_start']} to {metadata['latest_review_timestamp']}. On {metadata['store_listing_snapshot_date']}, the live listing showed {metadata['store_score_display']} and {metadata['store_reviews_count_display']}. The displayed count is rounded, and rerunning the analysis on the saved CSV does not refresh the live listing data.", size=8.7)
    add_source_line(doc, metadata)
    heading = doc.add_paragraph()
    heading.paragraph_format.space_before = Pt(7)
    heading.paragraph_format.space_after = Pt(2)
    r = heading.add_run("Analysis method")
    format_run(r, 11.1, True, NAVY, DISPLAY)
    add_bullet(doc, "Python and pandas validate timestamps and star scores; compute 30-, 90- and 365-day windows anchored to the latest review timestamp; calculate monthly trends, response rates, and recent-version summaries.", size=8.5)
    add_bullet(doc, "The classifier uses ordered regular-expression rules with word boundaries for risky terms. It reports (1) one primary theme per review for mutually exclusive shares and (2) multi-label keyword matches so secondary issues are visible. Overlapping mention percentages must not be added.", size=8.5)
    validation = json.loads((OUT / "classifier_validation_metrics.json").read_text(encoding="utf-8")) if (OUT / "classifier_validation_metrics.json").exists() else {}
    semantic_triage = json.loads((OUT / "semantic_triage_summary.json").read_text(encoding="utf-8")) if (OUT / "semantic_triage_summary.json").exists() else {}
    agreement = float(validation.get("exact_primary_theme_agreement", float("nan")))
    interval = validation.get("wilson_95pct_interval", [float("nan"), float("nan")])
    add_bullet(doc, f"The primary classifier did not assign a theme to {other_n} ({other_pct:.1%}) reviews; {short_unmatched} of these are three words or fewer. An AI-assisted semantic review examined {int(semantic_triage.get('pre_refinement_long_unmatched_review_count', 55))} longer comments from the original unmatched set. It helped turn {int(semantic_triage.get('explicit_signals_captured_by_refined_rules', 8))} specific signals into repeatable rules and regression tests. Another {int(semantic_triage.get('remaining_vague_or_underspecified_long_comments', 47))} comments remain unmatched because the wording is too vague to classify safely. In a separate fixed, prediction-blind 100-review model-assisted adjudication sample, the rule-based primary label agreed on {agreement:.0%} of reviews (Wilson 95% interval {interval[0]:.0%}-{interval[1]:.0%}; macro-F1 {float(validation.get('macro_f1', float('nan'))):.2f}). The sample was single-pass and not independently double-coded, so this is a directional quality check rather than a certified benchmark.", size=8.5)
    add_bullet(doc, "The suite includes 32 classifier regression tests, 8 snapshot/integrity/metric/privacy/replay/score-bridge checks, and 3 alert tests (43 automated tests in total).", size=8.5)
    heading = doc.add_paragraph()
    heading.paragraph_format.space_before = Pt(6)
    heading.paragraph_format.space_after = Pt(2)
    r = heading.add_run("What this analysis cannot tell us")
    format_run(r, 11.1, True, NAVY, DISPLAY)
    add_bullet(doc, "Reviews are self-selected; they do not represent every employee, commute, device or region, and theme counts are not incident rates. The dataset was collected with lang=en for the India listing. Hindi and other regional-language reviews were not separately scraped or counted, so their patterns may differ.", size=8.4)
    add_bullet(doc, "The India Google Play listing displayed 4.3 stars and 1.15L reviews on 13 Oct 2026; the rounded public count is not an exact rating denominator. The India iOS listing displayed 4.7/5 from 60k ratings on the same date. This is directional context only: platform populations, app versions and rating systems differ, so it is not a controlled comparison.", size=8.4)
    add_bullet(doc, f"The 100-review model-assisted validation sample had {agreement:.0%} exact agreement (95% Wilson interval {interval[0]:.0%}-{interval[1]:.0%}); it was single-pass, not independently double-coded, and per-theme precision/recall varies. The complete per-theme 4-star/5-star sensitivity table is in Appendix B and output/theme_impact_scenarios.csv. These are counterfactual arithmetic, not forecasts.", size=8.4)
    add_bullet(doc, "Public reviews cannot prove root cause or establish that version 12.19.0 caused lower ratings. The 12.19.0 review label is consistent with the Android release series (a third-party tracker showed 12.20.0 available on 12 Oct); 10.50.0 is the iOS App Store version, a separate numbering sequence. Validate exact Android production build and rollout timing in Play Console before interpreting a spike. Validate launch issues against Android vitals, login against authentication logs, booking against booking outcomes, ETA against actual pickup timestamps, and route issues against vendor and operations data.", size=8.4)
    add_bullet(doc, "Developer reply presence is not the same as support response time or case resolution. The submitted review dataset retains only a reply-present flag, not reviewer profile data or raw developer-response text.", size=8.4)
    heading = doc.add_paragraph()
    heading.paragraph_format.space_before = Pt(6)
    heading.paragraph_format.space_after = Pt(2)
    r = heading.add_run("Reproduce the snapshot analysis")
    format_run(r, 11.1, True, NAVY, DISPLAY)
    for command in ("python -m pip install -r requirements.txt", "python moveinsync_ratings_monitor.py --csv reviews.csv --output-dir output", "python build_report.py", "python -m unittest -v"):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.18)
        p.paragraph_format.space_after = Pt(1.5)
        r = p.add_run(command)
        format_run(r, 8, True, NAVY2, "Consolas")
    add_para(doc, "Collecting new reviews requires internet access, and new results may differ from this saved snapshot. The repository includes a weekly GitHub Actions workflow (Monday at 08:00 India time) and a manual run option. Once the repository is published, its owner must enable Actions and grant `contents: write` permission so the workflow can update the aggregate history file. The owner still needs to verify the first live run, scraper access and GitHub permissions. Alerts should trigger an investigation, not an automatic rollback.", size=8.5, color=GRAY, after=1)

    # APPENDIX: next-day tickets based on actual, dated, anonymised public excerpts.
    page_heading(doc, "A", "Tickets a team could pick up tomorrow", "These tickets turn public review comments into work the team can investigate. Use internal telemetry to reproduce each issue before treating the suspected cause as confirmed.")
    ticket_rows = [
        ["P0 · OTP/login reliability", "“app is not sending otp” (6 Oct 2026)\n“Unable to login ... Mobile Otp and Email OTP options are not working” (9 Sep 2026)", "Reproduce sign-in via SMS and email across a small device/carrier matrix; record send, delivery, verification and expiry events. Suspected: auth backend/provider integration/session handling.", "Owner: Auth backend + Android. Acceptance: end-to-end tests for both channels; instrument success and latency; >=98% successful verification within 60s over a 7-day pilot or documented baseline/target agreed with engineering; visible recovery path for failures."],
        ["P0 · App won't open after update", "“whenever i update this app, i am not able to open the app again, I need to uninstall and reinstall again” (9 Oct 2026)\n“installed and uninstalled... still not working... open and close automatically” (29 Sep 2026)", "Update from the prior production version without clearing data on affected supported devices/OS versions; inspect launch/crash logs and the install-source verification result. Suspected: update migration, installer integrity or startup crash.", "Owner: Android engineering. Acceptance: update-path regression test; no false 'not installed from Play Store' response in supported Play-installed builds; launch success and crash-free sessions tracked by version/device; proposed >=99.5% crash-free-session guardrail."],
        ["P0 · Booking state and waitlist clarity", "“it just books you without informing if he's on waitlist or not” (8 Oct 2026)\n“schedules that I booked did not show up... when I try to book again it's already showing duplicate schedule” (18 May 2026)", "Submit a booking with capacity constrained, reload the schedule and inspect notifications; tap/retry after a slow response. Suspected: state propagation, booking idempotency and push-copy mismatch.", "Owner: Product + Backend. Acceptance: every booking displays Confirmed / Waitlisted / Cancelled consistently; waitlist is disclosed before leaving flow; retry cannot duplicate booking; contradictory 'trip not booked' push is covered by automated tests."],
        ["P1 · ETA and live tracking accuracy", "“The GPS tracking system is very slow, and the pickup and drop timings are frequently incorrect.” (1 Jul 2026)\n“google maps always shows 3x the time shown in moveinsync app” (8 Oct 2026)", "For representative shifts/routes, capture predicted pickup ETA at fixed intervals and compare with actual vehicle arrival; log location freshness. Suspected: map-feed freshness, ETA model inputs or routing latency.", "Owner: Routing + Platform + Operations. Acceptance: median and P90 absolute ETA error dashboard; stale-location indicator and data freshness logging; agree target after a one-week baseline; regression alert when P90 error materially worsens."],
        ["P1 · Late cab / poor routing escalation", "“cab is never assigned on time...always late” (25 Mar 2026)\n“Daily showing wrong routes and High travel time.” (4 Jun 2026)", "Join planned route, pickup and actual arrival logs by shift, site and vendor; review recurring late pickups and detours with the transport desk. Suspected: route/pooling constraints, allocation policy or vendor execution.", "Owner: Transport Ops + Vendor Management + Routing. Acceptance: weekly lateness and P90 delay by route/vendor; owner assigned for the worst repeat clusters; ticket or corrective action and due date recorded; exclude app-only fixes where operations caused the delay."],
    ]
    styled_table(doc, ["Proposed ticket", "Evidence (public review excerpts)", "Reproduction / suspected area", "Owner / acceptance criteria"], ticket_rows,
                 [1.20, 1.78, 2.02, 1.68], font_size=6.6, header_size=6.7)
    add_para(doc, "Quotes are shortened only where an ellipsis appears, and dates come from the saved review snapshot. These are proposed tickets, not confirmed incidents. Treat the acceptance criteria as starting targets and adjust them after measuring a telemetry baseline.", size=7.0, color=GRAY, after=1)

    # APPENDIX B: complete, source-of-truth sensitivity ranking for all primary themes.
    doc.add_page_break()
    page_heading(doc, "B", "Full counterfactual uplift by primary theme", "The table below includes every primary-theme group. The ranking assumes that all 1–3-star reviews in a group became 4 stars; the 5-star column shows a separate, more extreme scenario.")
    impact = pd.read_csv(OUT / "theme_impact_scenarios.csv")
    impact = impact.sort_values(["actionable_theme", "sample_mean_uplift_if_to_4"], ascending=[False, False]).reset_index(drop=True)
    impact_rows = []
    action_rank = 0
    for r in impact.itertuples():
        if bool(r.actionable_theme):
            action_rank += 1
            rank_label = str(action_rank)
        else:
            rank_label = "—"
        impact_rows.append([rank_label, r.primary_theme, int(r.low_reviews), f"+{r.sample_mean_uplift_if_to_4:.3f}", f"{r.sample_mean_if_to_4:.2f}", f"+{r.sample_mean_uplift_if_to_5:.3f}"])
    styled_table(doc, ["Rank¹", "Primary theme", "n low", "Δ if →4★", "Mean if →4★", "Δ if →5★"], impact_rows,
                 [0.47, 2.47, 0.55, 0.75, 0.85, 0.75], font_size=7.1, header_size=7.0)
    add_para(doc, "¹ Rank excludes ‘No specific detail / other’, because it is a residual bucket rather than a fixable product theme. All figures use the same 2,848-review 365-day written-review denominator. For each row, existing 1–3-star scores in that one primary theme are replaced with 4 or 5; all other scores are held constant. This is arithmetic sensitivity, not an expected lift, causal estimate or prediction of the public Play Store rating. Theme definitions and counts are generated from the same classifier output to avoid brief/report drift.", size=8.0, color=GRAY, after=2)
    add_para(doc, "Use this ranking as one input to prioritisation, not as the decision by itself. A safety issue, a blocked employee journey, stronger evidence, lower implementation cost or clearer operational ownership may deserve attention before a theme with a larger calculated uplift. The 100-review classifier check and the unmatched queue also show where uncertainty remains.", size=8.0, after=1)

    path = ROOT / "MoveInSync_Play_Store_Ratings_Report.docx"
    doc.save(path)
    return path


def create_decision_brief(metadata, df, windows, themes, mentions, replies, versions):
    doc = Document()
    setup_doc(doc, compact=True, footer_note="DECISION BRIEF  |  PUBLIC REVIEW SNAPSHOT")
    low_n = int(len(df[(df["at"] > df["at"].max() - pd.Timedelta(days=365)) & (df["score"] <= 3)]))
    mention = mentions.set_index("theme")
    m30 = windows.loc[windows.window_days.eq(30)].iloc[0]
    m365 = windows.loc[windows.window_days.eq(365)].iloc[0]
    r2023 = replies.loc[replies.year.eq(2023)].iloc[0]
    r2026 = replies.loc[replies.year.eq(2026)].iloc[0]

    kicker(doc, "MoveInSync | FDE Candidate Assignment")
    title = doc.add_paragraph(style="Title")
    title.paragraph_format.space_after = Pt(3)
    r = title.add_run("What should MoveInSync fix first?")
    format_run(r, 24, True, NAVY, DISPLAY)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("A decision brief based on 24,315 public written reviews  •  Snapshot collected 13 Oct 2026")
    format_run(r, 8.4, False, GRAY)
    bridge = pd.read_csv(OUT / "store_score_bridge.csv").set_index("scenario")
    otp_scenario = pd.read_csv(OUT / "theme_impact_scenarios.csv").set_index("primary_theme").loc["OTP / login / session"]
    top_line = doc.add_paragraph()
    top_line.paragraph_format.space_after = Pt(4)
    top_line.paragraph_format.space_before = Pt(2)
    r = top_line.add_run(f"DO FIRST: reply to negative reviews today; investigate OTP/login first. If all {int(otp_scenario.low_reviews)} OTP-primary low-rated reviews became 4 stars, the 365-day written mean would rise +{otp_scenario.sample_mean_uplift_if_to_4:.3f}; a crude equal-weight whole-listing bridge is only about +{float(bridge.loc['OTP/login primary theme only', 'naive_equal_weight_whole_listing_score_points']):.3f} points (not a forecast).")
    format_run(r, 8.7, True, CORAL)
    metric_tiles(doc, [
        (f"{m30.mean_score:.2f}/5", "LAST 30 DAYS", f"n={int(m30.reviews)} written reviews"),
        (f"{m30.one_star_share:.1%}", "ONE STAR", "Share in last 30 days"),
        (f"{m30.low_1_2_star_reply_rate:.1%}", "PUBLIC REPLIES", f"{int(m30.low_1_2_star_replies)}/{int(m30.low_1_2_star_reviews)} recent 1–2 star reviews"),
        (f"{r2026.reply_rate:.1%}", "2026 YTD REPLIES", f"vs {r2023.reply_rate:.1%} in 2023"),
    ], small=True)
    callout(doc, "The recommendation", "Do not run a campaign to solicit better stars. Treat the reviews as a signal that employees need a more dependable commute journey: access the app, sign in, know whether a trip is confirmed, trust the pickup ETA, and reach a human when something fails.", fill=MINT, accent=TEAL, body_size=8.9)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run("Act in this order")
    format_run(r, 11.5, True, NAVY, DISPLAY)
    moves = [
        ["TODAY", "Restore public response coverage", f"Only {int(m30.low_1_2_star_replies)} of {int(m30.low_1_2_star_reviews)} recent 1–2 star reviews received a developer reply. Assign a daily owner, offer a real support route, and escalate safety reports the same day."],
        ["DAYS 1–2", "Audit login and app access", f"{int(mention.loc['OTP / login / session', 'reviews_with_mention'])} low-rated reviews contain login/OTP terms. Reproduce OTP/session and post-update launch/install issues; validate against authentication logs and Android vitals."],
        ["WEEK 1", "Clarify booking and ETA", f"{int(mention.loc['Booking / schedule / roster', 'reviews_with_mention'])} reviews mention booking/scheduling and {int(mention.loc['ETA / tracking / location', 'reviews_with_mention'])} mention ETA/tracking/location. Make confirmed/waitlisted/cancelled states explicit and validate ETA against actual pickups."],
        ["WEEK 1", "Triage route and pickup failures", f"{int(mention.loc['Transport operations / driver / route', 'reviews_with_mention'])} reviews contain transport/driver/route signals. Group by route, shift and vendor; compare planned vs actual pickup and P90 delays; assign follow-up to operations and vendors."],
        ["NEXT RELEASE", "Remove forced-rating friction", "Make post-ride feedback skippable and never block booking or trip details behind a rating. It is less frequent than login problems, but a relatively small fix for a directly reported blocker."],
    ]
    styled_table(doc, ["WHEN", "MOVE", "NEXT ACTION"], moves, [0.83, 1.65, 4.72], font_size=7.7, header_size=7.5)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("Why the headline rating is not the whole story")
    format_run(r, 10.3, True, NAVY, DISPLAY)
    all_time_written_mean = float(df["score"].mean())
    add_para(doc, f"On {metadata['store_listing_snapshot_date']}, the India Play listing showed {metadata['store_score_display']} and {metadata['store_reviews_count_display']}. The written-review sample averages {m365.mean_score:.2f}/5 over the latest 365 days and {all_time_written_mean:.2f}/5 across all collected years. These figures measure different things: Google weights the Play rating toward recent ratings, while this self-selected, English-language text sample includes older reviews. The 30-day written mean ({m30.mean_score:.2f}) is below the 90-day and 365-day means, although monthly results vary. iOS shows {metadata['ios_store_score_display']} from {metadata['ios_ratings_count_display'].split(' (')[0]}, compared with Android at {metadata['store_score_display']}. The 0.4-star gap is worth investigating, but it does not prove that the platform caused the difference.", size=7.7, after=2)
    platform_line = doc.add_paragraph()
    platform_line.paragraph_format.space_before = Pt(0)
    platform_line.paragraph_format.space_after = Pt(1)
    r = platform_line.add_run("PLATFORM CLUE: Android 4.3 vs iOS 4.7 (0.4★ gap). Investigate Android OTP/install/launch friction; this comparison is directional, not causal.")
    format_run(r, 7.2, True, TEAL)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("Potential impact if low-rated primary-theme reviews improved to 4 stars")
    format_run(r, 9.2, True, NAVY, DISPLAY)
    impact = pd.read_csv(OUT / "theme_impact_scenarios.csv")
    chart_path = make_brief_impact_chart(impact)
    chart_in_doc(doc, chart_path, width=6.55, caption="Extreme arithmetic sensitivity on the 365-day written-review mean; not a promised result.")
    otp_bridge = float(bridge.loc["OTP/login primary theme only", "naive_equal_weight_whole_listing_score_points"])
    both_bridge = float(bridge.loc["OTP/login + booking primary themes", "naive_equal_weight_whole_listing_score_points"])
    add_para(doc, f"Rough store-score bridge (equal-weight arithmetic, not a forecast): if those exact 123 OTP reviews alone gained the missing star points to reach 4, the whole-listing mean would move about +{otp_bridge:.3f}; OTP + booking together, about +{both_bridge:.3f}, using ~115,000 as a rounded denominator. The true Play display is recency-weighted and the public count is rounded; at one-decimal display precision it would likely still show 4.3.", size=7.25, color=GRAY, after=1)
    add_para(doc, "Method: Python/pandas and word-boundary rules; 43 tests passed. The 82% agreement is model-assisted, not independent human validation. A fresh scrape and remote Actions run remain pending. Reviews point to issues to check, not proven causes.", size=7.0, color=GRAY, after=0)
    path = ROOT / "MoveInSync_Decision_Brief.docx"
    doc.save(path)
    return path


def main():
    metadata, df, result, windows, monthly, themes, mentions, replies, versions = get_data()
    main_doc = create_main_report(metadata, df, windows, monthly, themes, mentions, replies, versions)
    brief_doc = create_decision_brief(metadata, df, windows, themes, mentions, replies, versions)
    print(f"Built: {main_doc}")
    print(f"Built: {brief_doc}")
    print(f"Charts: {CHARTS}")
    print("Source snapshot:", metadata["store_listing_snapshot_date"], "| Reviews:", len(df))


if __name__ == "__main__":
    main()
