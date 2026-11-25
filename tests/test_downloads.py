"""Every download type builds a valid file, including awkward content. Run: python tests/test_downloads.py"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from docx import Document
from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader

import exporter

NASTY = '=HYPERLINK("x") <b>&\x07 ' + "verylongword" * 20


def sample(rows=3, cols=3):
    df = pd.DataFrame({f"Col {c}": [NASTY if r == 0 else f"{r}.{c}" for r in range(rows)] for c in range(cols)})
    return exporter.make_doc("Report Card", subtitle="Finals 🎓", info=[("Name", "=cmd"), ("Roll", None)],
                             tables=[("Subjects", df), ("Empty", pd.DataFrame())])


def build(doc, name):
    return exporter.FORMATS[name][0](doc)


def test_every_format_builds():
    assert len(exporter.available()) == len(exporter.FORMATS) == 9
    for name in exporter.FORMATS:
        assert len(build(sample(), name)) > 100, name


def test_files_open_and_hold_the_content():
    doc = sample()
    assert Image.open(io.BytesIO(build(doc, "Picture (PNG)"))).format == "PNG"
    assert Image.open(io.BytesIO(build(doc, "Picture (JPG)"))).format == "JPEG"
    assert len(PdfReader(io.BytesIO(build(doc, "PDF document"))).pages) == 1
    ws = load_workbook(io.BytesIO(build(doc, "Excel spreadsheet"))).active
    assert not any(c.data_type == "f" for row in ws.iter_rows() for c in row)  # no live formulas
    assert any(c.value == "1.0" for row in ws.iter_rows() for c in row)
    assert Document(io.BytesIO(build(doc, "Word document"))).tables[0].rows[2].cells[0].text == "1.0"
    assert "'=cmd" in build(doc, "CSV (spreadsheet text)").decode("utf-8-sig")
    assert "<b>" not in build(doc, "Web page (HTML)").decode()
    assert json.loads(build(doc, "JSON data"))["details"]["Name"] == "=cmd"


def test_big_tables_flow_onto_more_pages():
    assert len(PdfReader(io.BytesIO(build(sample(rows=150), "PDF document"))).pages) > 2
    wide = Image.open(io.BytesIO(build(sample(cols=25), "Picture (PNG)")))
    assert wide.width > 3000


def test_file_names_are_safe():
    assert exporter.filename("report_card_../../Sam Lee", "PDF document") == "report_card_.._.._Sam_Lee.pdf"
    assert exporter.filename("///", "Plain text") == "report.txt"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
