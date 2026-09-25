"""Server-side QR image generation (Fix Plan Section 3.1).

Error-correction level Q (~25% damage tolerance) — printed labels get scuffed.
"""
from __future__ import annotations
import io

import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_Q

_EC = {"L": ERROR_CORRECT_L, "Q": ERROR_CORRECT_Q}


def make_qr_png(payload: str, size_mm: float = 30.0, dpi: int = 300, ec: str = "Q") -> bytes:
    qr = qrcode.QRCode(
        error_correction=_EC.get(ec.upper(), ERROR_CORRECT_Q),
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    px = max(64, int(size_mm / 25.4 * dpi))
    img = img.resize((px, px))
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(dpi, dpi))
    return buf.getvalue()
