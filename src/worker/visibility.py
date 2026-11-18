"""Extract PDF text that is visible on the rendered page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pymupdf

from src.domain.text_hygiene import scan_injection

MAX_RASTER_SIDE = 1400
MIN_LIGHT_LUMINANCE = 160
MIN_BACKGROUND_FRACTION = 0.55
MIN_INK_FRACTION = 0.02


@dataclass(frozen=True)
class PdfLine:
    x: float
    y: float
    text: str


def _is_printed_span(span: dict[str, Any], bounds: pymupdf.Rect) -> bool:
    if span["size"] < 4 or span.get("alpha", 255) == 0 or span.get("render_mode") == 3:
        return False
    span_box = pymupdf.Rect(span["bbox"])
    return not span_box.is_empty and span_box.intersects(bounds)


def _luminance(color: int) -> int:
    red = (color >> 16) & 255
    green = (color >> 8) & 255
    blue = color & 255
    return (299 * red + 587 * green + 114 * blue) // 1000


@dataclass(frozen=True)
class PageRaster:
    pixels: bytes
    width: int
    height: int
    stride: int
    matrix: pymupdf.Matrix

    @classmethod
    def render(cls, page: pymupdf.Page) -> PageRaster | None:
        # A single bounded grayscale raster serves every light span on this page.
        scale = min(1.5, MAX_RASTER_SIDE / max(page.rect.width, page.rect.height, 1))
        matrix = pymupdf.Matrix(scale, scale)
        try:
            pixmap = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csGRAY, alpha=False, annots=False)
        except RuntimeError:
            return None
        return cls(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, page.rotation_matrix * matrix)

    def light_text_has_contrast(self, bbox: Any, foreground: int) -> bool:
        # Background should dominate the bounds of a light span. A few dark
        # pixels from nearby body text do not make white-on-white text visible.
        box = (pymupdf.Rect(bbox) * self.matrix).irect
        left, top = max(0, box.x0), max(0, box.y0)
        right, bottom = min(self.width, box.x1), min(self.height, box.y1)
        if left >= right or top >= bottom:
            return False

        ink = background = samples = 0
        # Limit probes even for a pathological text box spanning the page.
        step = max(1, max(right - left, bottom - top) // 120)
        for y in range(top, bottom, step):
            offset = y * self.stride
            for x in range(left, right, step):
                value = self.pixels[offset + x]
                contrast = abs(value - foreground)
                samples += 1
                ink += contrast <= 24
                background += contrast >= 36
        return ink >= max(3, samples * MIN_INK_FRACTION) and background >= samples * MIN_BACKGROUND_FRACTION


def visible_pdf_lines(page: pymupdf.Page) -> list[PdfLine]:
    bounds = page.rect * page.derotation_matrix
    blocks = page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT, sort=True)["blocks"]
    raster = None
    rendered = False
    result = []
    for block in blocks:
        for line in block.get("lines", []):
            spans = []
            for span in line["spans"]:
                if not _is_printed_span(span, bounds) or scan_injection(span["text"]):
                    continue
                foreground = _luminance(span["color"])
                if foreground >= MIN_LIGHT_LUMINANCE:
                    if not rendered:
                        raster = PageRaster.render(page)
                        rendered = True
                    if not raster or not raster.light_text_has_contrast(span["bbox"], foreground):
                        continue
                spans.append(span)
            text = "".join(span["text"] for span in spans).strip()
            if text and not scan_injection(text):
                result.append(PdfLine(min(span["bbox"][0] for span in spans), line["bbox"][1], text))
    return result
