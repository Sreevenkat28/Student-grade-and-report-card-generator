"""Turn a report into a downloadable file: PDF, picture, Excel, Word, CSV, web page, text or JSON.

A report is described once with make_doc() and every format is built from that description.
"""
import html
import importlib.util
import io
import json
import os
import re

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


def make_doc(title, tables, subtitle="", info=(), raw=None):
    """tables: [(heading, DataFrame)], info: [(label, value)], raw: what the JSON format should contain."""
    return {"title": title, "subtitle": subtitle, "info": [(k, _text(v)) for k, v in info],
            "tables": [(h, df) for h, df in tables], "raw": raw}


def _text(v):
    if v is None or (isinstance(v, float) and v != v):
        return ""
    if isinstance(v, float):
        return f"{v:g}"
    # control characters would break the Excel and Word files
    return re.sub(r"[\x00-\x08\x0b-\x1f\ud800-\udfff￾￿]", "", str(v))


def _rows(df):
    return [_text(c) for c in df.columns], [[_text(v) for v in row] for row in df.astype(object).values.tolist()]


def _no_formula(v):
    """Stop spreadsheet apps from running a name like '=HYPERLINK(...)' as a formula."""
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


# ---------------------------------------------------------------- text formats
def to_csv(doc):
    plain = not doc["info"] and len(doc["tables"]) == 1
    out = io.StringIO()

    def line(cells):
        pd.DataFrame([[_no_formula(c) for c in cells]]).to_csv(out, index=False, header=False)

    if not plain:
        line([doc["title"]])
        for k, v in doc["info"]:
            line([k, v])
    for heading, df in doc["tables"]:
        head, rows = _rows(df)
        if not plain:
            out.write("\n")
            if heading:
                line([heading])
        if head:
            line(head)
        for row in rows:
            line(row)
    return out.getvalue().encode("utf-8-sig")  # the BOM makes Excel read accents correctly


def to_txt(doc):
    parts = [doc["title"], "=" * len(doc["title"])]
    if doc["subtitle"]:
        parts.append(doc["subtitle"])
    parts.append("")
    parts += [f"{k}: {v}" for k, v in doc["info"]]
    for heading, df in doc["tables"]:
        head, rows = _rows(df)
        parts.append("")
        if heading:
            parts += [heading, "-" * len(heading)]
        if not rows:
            parts.append("(nothing yet)")
            continue
        grid = [head] + rows
        widths = [max(len(r[i]) for r in grid) for i in range(len(head))]
        for r in grid:
            parts.append("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
    return ("\n".join(parts) + "\n").encode("utf-8")


def to_html(doc):
    e = html.escape
    out = ["<!doctype html><html lang='en'><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>", f"<title>{e(doc['title'])}</title>",
           "<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:32px auto;padding:0 16px;color:#1d1d1f}"
           "table{border-collapse:collapse;width:100%;margin:8px 0 24px}th,td{border:1px solid #d2d2d7;padding:8px 10px;text-align:left}"
           "th{background:#f5f5f7}dt{color:#6e6e73;font-size:13px}dd{margin:0 0 8px;font-weight:600}h1{margin-bottom:4px}</style>",
           f"<h1>{e(doc['title'])}</h1>"]
    if doc["subtitle"]:
        out.append(f"<p>{e(doc['subtitle'])}</p>")
    if doc["info"]:
        out.append("<dl>" + "".join(f"<dt>{e(k)}</dt><dd>{e(v) or '—'}</dd>" for k, v in doc["info"]) + "</dl>")
    for heading, df in doc["tables"]:
        head, rows = _rows(df)
        if heading:
            out.append(f"<h2>{e(heading)}</h2>")
        if not rows:
            out.append("<p>Nothing yet.</p>")
            continue
        out.append("<table><tr>" + "".join(f"<th>{e(c)}</th>" for c in head) + "</tr>")
        out += ["<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows]
        out.append("</table>")
    return "".join(out).encode("utf-8")


def to_json(doc):
    data = doc["raw"]
    if data is None:
        data = {"title": doc["title"], "subtitle": doc["subtitle"], "details": dict(doc["info"]),
                "tables": [{"heading": h, "rows": [dict(zip(*[_rows(df)[0], r])) for r in _rows(df)[1]]}
                           for h, df in doc["tables"]]}
    return json.dumps(data, indent=2, ensure_ascii=False, default=str).encode("utf-8")


# ---------------------------------------------------------------- office formats
def to_xlsx(doc):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    widths = {}

    def add(cells, bold=False, fill=False, size=11):
        ws.append([_no_formula(c) for c in cells])
        for i, c in enumerate(cells, 1):
            cell = ws.cell(ws.max_row, i)
            cell.font = Font(bold=bold, size=size)
            cell.alignment = Alignment(vertical="top", wrap_text=len(c) > 50)
            if fill:
                cell.fill = PatternFill("solid", fgColor="E8E8ED")
            if size == 11:
                widths[i] = max(widths.get(i, 10), min(len(c) + 3, 50))

    add([doc["title"]], bold=True, size=16)
    if doc["subtitle"]:
        ws.append([_no_formula(doc["subtitle"])])
    for k, v in doc["info"]:
        add([k, v])
    for heading, df in doc["tables"]:
        head, rows = _rows(df)
        ws.append([])
        if heading:
            add([heading], bold=True)
        if head:
            add(head, bold=True, fill=True)
        for row in rows:
            add(row)
    for i, w in widths.items():
        ws.column_dimensions[get_column_letter(i)].width = w
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def to_docx(doc):
    from docx import Document

    d = Document()
    d.add_heading(doc["title"], 0)
    if doc["subtitle"]:
        d.add_paragraph(doc["subtitle"])
    for k, v in doc["info"]:
        p = d.add_paragraph()
        p.add_run(f"{k}: ").bold = True
        p.add_run(v or "—")
    for heading, df in doc["tables"]:
        head, rows = _rows(df)
        if heading:
            d.add_heading(heading, 1)
        if not rows or not head:
            d.add_paragraph("Nothing yet.")
            continue
        t = d.add_table(rows=len(rows) + 1, cols=len(head))
        t.style = "Light Grid Accent 1"
        cells = t._cells  # looking cells up one by one is very slow on big tables
        for i, value in enumerate(v for r in [head] + rows for v in r):
            cells[i].text = value
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


# ---------------------------------------------------------------- pictures and PDF
_FONT_FILES = {
    False: ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf"],
    True: ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
}


def _font(size, bold=False):
    for path in _FONT_FILES[bold] + _FONT_FILES[False]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)  # built into Pillow


def _wrap(text, font, width):
    lines = []
    for para in re.sub(r"[\U00010000-\U0010ffff]", "", text).split("\n"):  # the fonts have no emoji
        cur = ""
        for word in para.split():
            trial = f"{cur} {word}".strip()
            if font.getlength(trial) <= width:
                cur = trial
                continue
            if cur:
                lines.append(cur)
            while font.getlength(word) > width and len(word) > 1:  # one very long word
                cut = len(word) - 1
                while cut > 1 and font.getlength(word[:cut]) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            cur = word
        lines.append(cur)
    return lines or [""]


def _render(doc, page_height=None):
    """Draw the report. Returns a list of page images: one tall image when page_height is None."""
    margin, pad, line_h, min_col = 70, 12, 32, 130
    body, bold, h2, h1 = _font(22), _font(22, True), _font(28, True), _font(44, True)
    columns = max([len(df.columns) for _h, df in doc["tables"]] or [1])
    width = max(1240, 2 * margin + columns * min_col)
    content = width - 2 * margin

    blocks = []  # (height, draw(canvas, y), header_to_repeat_on_a_new_page)

    def text_block(text, font, color="#1d1d1f", gap=6, step=line_h):
        for ln in _wrap(text, font, content):
            blocks.append((step, lambda d, y, ln=ln, font=font, color=color: d.text((margin, y), ln, font=font, fill=color), None))
        blocks.append((gap, lambda d, y: None, None))

    def row_block(cells, widths, font, fill, header):
        wrapped = [_wrap(c, font, w - 2 * pad)[:30] for c, w in zip(cells, widths)]
        height = max(len(w) for w in wrapped) * line_h + pad

        def draw(d, y):
            x = margin
            for lines, w in zip(wrapped, widths):
                d.rectangle([x, y, x + w, y + height], fill=fill, outline="#d2d2d7")
                for i, ln in enumerate(lines):
                    d.text((x + pad, y + pad // 2 + i * line_h), ln, font=font, fill="#1d1d1f")
                x += w

        return (height, draw, header)

    text_block(doc["title"], h1, step=58)
    if doc["subtitle"]:
        text_block(doc["subtitle"], body, color="#6e6e73")
    if doc["info"]:
        blocks.append((12, lambda d, y: None, None))
        for k, v in doc["info"]:
            text_block(f"{k}:  {v or '—'}", body, gap=2)
    for heading, df in doc["tables"]:
        head, rows = _rows(df)
        blocks.append((24, lambda d, y: None, None))
        if heading:
            text_block(heading, h2, step=40)
        if not rows or not head:
            text_block("Nothing yet.", body, color="#6e6e73")
            continue
        # columns get the room their text needs; if that is too much, wide ones are narrowed and wrap
        want = [min(max(bold.getlength(head[i]), max(body.getlength(r[i]) for r in rows)) + 2 * pad + 4, 560)
                for i in range(len(head))]
        spare = content - len(head) * min_col
        extra = [max(w - min_col, 0) for w in want]
        if sum(want) <= content:
            widths = [int(w * content / sum(want)) for w in want]
        else:
            widths = [int(min(w, min_col) + spare * e / (sum(extra) or 1)) for w, e in zip(want, extra)]
        header = row_block(head, widths, bold, "#e8e8ed", None)
        blocks.append(header)
        for r in rows:
            blocks.append(row_block(r, widths, body, "#ffffff", header))

    if page_height is None:
        total = min(2 * margin + sum(b[0] for b in blocks), 30000)
        page_h = total
    else:
        page_h = max(page_height, int(width * 1.414)) if width > 1240 else page_height

    pages, draw, y = [], None, 0
    for height, paint, header in blocks:
        if draw is None or (page_height is not None and y + height > page_h - margin):
            pages.append(Image.new("RGB", (width, page_h), "white"))
            draw, y = ImageDraw.Draw(pages[-1]), margin
            if header is not None:
                header[1](draw, y)
                y += header[0]
        paint(draw, y)
        y += height
    return pages


def to_png(doc):
    out = io.BytesIO()
    _render(doc)[0].save(out, "PNG", optimize=True)
    return out.getvalue()


def to_jpg(doc):
    out = io.BytesIO()
    _render(doc)[0].save(out, "JPEG", quality=92)
    return out.getvalue()


def to_pdf(doc):
    pages = _render(doc, page_height=1754)  # A4 at 150 dpi
    out = io.BytesIO()
    pages[0].save(out, "PDF", resolution=150, save_all=True, append_images=pages[1:])
    return out.getvalue()


# label -> (builder, file extension, MIME type, extra package it needs)
FORMATS = {
    "PDF document": (to_pdf, "pdf", "application/pdf", None),
    "Picture (PNG)": (to_png, "png", "image/png", None),
    "Picture (JPG)": (to_jpg, "jpg", "image/jpeg", None),
    "Excel spreadsheet": (to_xlsx, "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "openpyxl"),
    "Word document": (to_docx, "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "CSV (spreadsheet text)": (to_csv, "csv", "text/csv", None),
    "Web page (HTML)": (to_html, "html", "text/html", None),
    "Plain text": (to_txt, "txt", "text/plain", None),
    "JSON data": (to_json, "json", "application/json", None),
}


def available():
    return [name for name, (_b, _e, _m, need) in FORMATS.items() if need is None or importlib.util.find_spec(need)]


def filename(base, fmt):
    clean = re.sub(r"[^\w.-]+", "_", base).strip("._") or "report"
    return f"{clean[:80]}.{FORMATS[fmt][1]}"


def download_ui(st, doc, base, key):
    """A format picker with a download button next to it."""
    left, right = st.columns([2, 1], vertical_alignment="bottom")
    fmt = left.selectbox("Download as", available(), key=f"fmt_{key}",
                         help="Pick the kind of file you want, then press Download. PDF and pictures are best for printing "
                              "or sharing; Excel and CSV for spreadsheets.")
    builder, _ext, mime, _need = FORMATS[fmt]
    right.download_button("⬇ Download", builder(doc), file_name=filename(base, fmt), mime=mime, type="primary",
                          width="stretch", on_click="ignore", key=f"dl_{key}")
