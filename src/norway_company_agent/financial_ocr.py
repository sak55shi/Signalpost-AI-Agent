from __future__ import annotations

import hashlib
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .http import FetchResult


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def download_official_pdf(
    url: str,
    *,
    timeout: float = 30.0,
) -> FetchResult:
    """Download an official annual-account PDF and preserve its provenance."""
    started = time.monotonic()
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "builderr-signalpost-poc/0.1 (+https://builderr.ai)",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            elapsed = int((time.monotonic() - started) * 1000)
            content_type = response.headers.get("Content-Type", "").lower()

            if not raw.startswith(b"%PDF-") or "pdf" not in content_type:
                return FetchResult(
                    url, response.status, elapsed, len(raw),
                    error="Response is not a valid PDF",
                    content_sha256=hashlib.sha256(raw).hexdigest(),
                    retrieved_at=_utc_now(),
                )

            return FetchResult(
                url,
                response.status,
                elapsed,
                len(raw),
                body=raw,
                content_sha256=hashlib.sha256(raw).hexdigest(),
                retrieved_at=_utc_now(),
            )

    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return FetchResult(
            url,
            exc.code,
            int((time.monotonic() - started) * 1000),
            len(raw),
            error=f"HTTP {exc.code}",
            content_sha256=hashlib.sha256(raw).hexdigest(),
            retrieved_at=_utc_now(),
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return FetchResult(
            url, 0, int((time.monotonic() - started) * 1000), 0,
            error=type(exc).__name__,
            retrieved_at=_utc_now(),
        )


def ocr_pdf_bytes(
    pdf_bytes: bytes,
    *,
    page_numbers: list[int] | None = None,
    dpi: int = 180,
) -> dict[str, Any]:
    """Render selected zero-based PDF pages and extract their text with Tesseract."""
    try:
        import pymupdf
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "OCR requires PyMuPDF, pytesseract and Pillow."
        ) from exc

    if not isinstance(pdf_bytes, (bytes, bytearray)):
        raise ValueError("No PDF bytes received; check the download result first.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Input does not contain valid PDF bytes.")

    configured_tesseract = os.environ.get("TESSERACT_CMD")
    default_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    if configured_tesseract:
        pytesseract.pytesseract.tesseract_cmd = configured_tesseract
    elif os.path.isfile(default_tesseract):
        pytesseract.pytesseract.tesseract_cmd = default_tesseract

    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    try:
        total_pages = len(document)
        selected_pages = (
            list(range(total_pages))
            if page_numbers is None
            else sorted(set(page_numbers))
        )

        if any(page < 0 or page >= total_pages for page in selected_pages):
            raise ValueError("A requested PDF page number is out of range.")

        if dpi < 100 or dpi > 300:
            raise ValueError("OCR rendering DPI must be between 100 and 300.")

        extracted = []

        for page_number in selected_pages:
            page = document[page_number]
            pixmap = page.get_pixmap(
                dpi=dpi,
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            image = Image.frombytes(
                "RGB",
                (pixmap.width, pixmap.height),
                pixmap.samples,
            )
            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6",
            )
            extracted.append(
                f"--- PDF PAGE {page_number + 1} ---\n{text.strip()}"
            )

        return {
            "text": "\n\n".join(extracted),
            "total_pages": total_pages,
            "processed_pages": [page + 1 for page in selected_pages],
            "dpi": dpi,
            "ocr_engine": "Tesseract",
        }
    finally:
        document.close()


def parse_insurance_financials(text: str, year: str) -> dict[str, Any]:
    import re

    """Extract labelled insurer-specific NOK figures from OCR text."""
    normalized = text.casefold()
    normalized = re.sub(
        r"resultat av teknisk\s+regnskap",
        "resultat av teknisk regnskap",
        normalized,
    )

    labels = {
        "earned_gross_premiums": (
            "opptjente bruttopremier",
            "sum premieinntekter for egen regning",
            "premieinntekter for egen regning",
        ),
        "other_insurance_income": ("andre forsikringsrelaterte inntekter",),
        "gross_claims_expenses": ("brutto erstatningskostnader",),
        "technical_result": (
            "resultat av teknisk regnskap",
            "teknisk resultat",
        ),
        "profit_before_tax": (
            "resultat f?r skattekostnad",
            "resultat for skattekostnad",
            "resultat fer skattekostnad",
            "resultat f?r skatt",
            "resultat for skatt",
        ),
        "total_comprehensive_result": ("totalresultat",),
        "assets": ("sum eiendeler", "sum elendeler"),
        "equity": ("sum egenkapital",),
    }

    def amounts_after_label(line: str, label: str) -> list[int]:
        remainder = line[line.find(label) + len(label):]
        # Remove accounting note references such as 1,2,3 before reading amounts.
        remainder = re.sub(r"(?<!\w)\d+(?:,\d+)+(?!\w)", " ", remainder)
        chunks = re.findall(r"(?<!\w)-?\d+", remainder)
        values = []
        i = 0

        while i < len(chunks):
            first = chunks[i]
            sign = -1 if first.startswith("-") else 1
            digits = first.lstrip("-")

            if len(digits) > 3:
                values.append(int(first))
                i += 1
                continue

            parts = [digits]
            i += 1
            while (
                i < len(chunks)
                and len(chunks[i].lstrip("-")) == 3
                and len(parts) < 3
            ):
                parts.append(chunks[i].lstrip("-"))
                i += 1

            values.append(sign * int("".join(parts)))

        return values

    result: dict[str, Any] = {
        "year": str(year),
        "currency": "NOK",
        "line_items": {},
    }

    for line in normalized.splitlines():
        for field, names in labels.items():
            label = next((name for name in names if name in line), None)
            if label and field not in result["line_items"]:
                values = amounts_after_label(line, label)
                if values:
                    result["line_items"][field] = {
                        "label": label,
                        "current_year": values[0],
                        "comparative_year": values[1] if len(values) > 1 else None,
                        "year": str(year),
                        "comparative_year_label": str(int(year) - 1),
                    }
                break

    return result

