"""Label export formats (Fix Plan Section 3.2): csv (real), pdf_sheet, zpl."""
from __future__ import annotations
import csv
import io
import tempfile
import os

from fpdf import FPDF

from app.core.qr import make_qr_png

EXPORT_FORMATS = ("csv", "pdf_sheet", "zpl")


def verify_url_for(public_web_url: str, unit_id: str) -> str:
    return f"{public_web_url.rstrip('/')}/v/{unit_id}"


def export_csv(unit_ids: list[str], public_web_url: str) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["unit_id", "verify_url"])
    for uid_ in unit_ids:
        writer.writerow([uid_, verify_url_for(public_web_url, uid_)])
    return buf.getvalue().encode()


def export_pdf_sheet(
    unit_ids: list[str],
    public_web_url: str,
    size_mm: float = 30.0,
    cols: int = 5,
    rows: int = 10,
) -> bytes:
    """Ready-to-print grid of QR labels on A4."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    margin, gap = 10.0, 4.0
    tmpdir = tempfile.mkdtemp(prefix="labels_")
    try:
        paths: list[str] = []
        for uid_ in unit_ids:
            png = make_qr_png(verify_url_for(public_web_url, uid_), size_mm=size_mm)
            path = os.path.join(tmpdir, f"{uid_}.png")
            with open(path, "wb") as fh:
                fh.write(png)
            paths.append(path)
        per_page = cols * rows
        for idx, (uid_, path) in enumerate(zip(unit_ids, paths)):
            slot = idx % per_page
            if idx and slot == 0:
                pdf.add_page()
            col, row = slot % cols, (slot // cols) % rows
            x = margin + col * (size_mm + gap)
            y = margin + row * (size_mm + 8 + gap)
            pdf.image(path, x=x, y=y, w=size_mm, h=size_mm)
            pdf.set_xy(x, y + size_mm + 1)
            pdf.set_font("Helvetica", size=7)
            pdf.cell(size_mm, 4, uid_, align="C")
    finally:
        for name in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, name))
        os.rmdir(tmpdir)
    return bytes(pdf.output())


def export_zpl(unit_ids: list[str], public_web_url: str, size_mm: float = 30.0) -> bytes:
    """Raw Zebra (ZPL) output — one ^XA label per unit, QR via ^BQN."""
    dots_per_mm = 8  # 203 dpi
    mag = max(2, min(10, int(size_mm / 25.4 * dots_per_mm / 25)))
    out: list[str] = []
    for uid_ in unit_ids:
        url = verify_url_for(public_web_url, uid_)
        out.append(
            "^XA\n"
            f"^FO50,50^BQN,2,{mag}^FDQA,{url}^FS\n"
            f"^FO50,300^ADN,18,10^FD{uid_}^FS\n"
            "^XZ\n"
        )
    return "".join(out).encode()
