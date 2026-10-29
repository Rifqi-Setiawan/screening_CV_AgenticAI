"""Visibility Gate for CV text spans.

Detects hidden text, white-on-white text, micro-font keyword stuffing (<4pt),
and spans placed outside page mediabox boundaries to ensure grounding by construction.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SpanVisibility(str, Enum):
    VISIBLE = "VISIBLE"
    HIDDEN = "HIDDEN"
    SUSPECT = "SUSPECT"


def _extract_rgb(color: Any) -> tuple[int, int, int] | None:
    """Normalizes color into an (R, G, B) integer tuple in 0..255."""
    if color is None:
        return 0, 0, 0
    if isinstance(color, int):
        # 24-bit sRGB integer: 0xRRGGBB
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        return r, g, b
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        # Check if float components 0.0 .. 1.0
        if all(isinstance(c, float) for c in color[:3]) and any(c <= 1.0 for c in color[:3]):
            return int(round(color[0] * 255)), int(round(color[1] * 255)), int(round(color[2] * 255))
        return int(color[0]), int(color[1]), int(color[2])
    return None


def inspect_span_visibility(
    span: dict[str, Any] | Any,
    page_rect: tuple[float, float, float, float] | Any = None,
) -> SpanVisibility:
    """Inspects a PyMuPDF text span for visibility status.

    Returns:
        - SpanVisibility.HIDDEN: font size < 4.0pt, white text (0xFFFFFF),
          completely outside page_rect mediabox, or invisible render mode.
        - SpanVisibility.SUSPECT: borderline font (4.0 <= size < 5.0),
          near-white low contrast, or partially clipped coordinates.
        - SpanVisibility.VISIBLE: normal visible text.
    """
    # Extract span properties (supports dict or object)
    if isinstance(span, dict):
        size = float(span.get("size", 10.0))
        color_val = span.get("color", 0)
        bbox = span.get("bbox")
        render_mode = span.get("render_mode")
        invisible = span.get("invisible", False)
    else:
        size = float(getattr(span, "size", 10.0))
        color_val = getattr(span, "color", 0)
        bbox = getattr(span, "bbox", None)
        render_mode = getattr(span, "render_mode", None)
        invisible = getattr(span, "invisible", False)

    # 1. Render mode 3 (invisible text in PDF specification)
    if render_mode == 3 or invisible:
        return SpanVisibility.HIDDEN

    # 2. Font size check (< 4.0pt is strictly hidden)
    if size < 4.0:
        return SpanVisibility.HIDDEN

    # 3. Color check (white or near-white)
    rgb = _extract_rgb(color_val)
    if rgb is not None:
        r, g, b = rgb
        if r == 255 and g == 255 and b == 255:
            return SpanVisibility.HIDDEN
        # Low contrast check: very close to pure white background (e.g. #FAFAFA, #F5F5F5)
        if r >= 240 and g >= 240 and b >= 240:
            return SpanVisibility.SUSPECT

    # 4. Mediabox / page_rect coordinates check
    if page_rect is not None and bbox is not None and len(bbox) >= 4:
        try:
            px0, py0, px1, py1 = float(page_rect[0]), float(page_rect[1]), float(page_rect[2]), float(page_rect[3])
            sx0, sy0, sx1, sy1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])

            # Inverted / degenerate bbox
            if sx1 < sx0 or sy1 < sy0:
                return SpanVisibility.HIDDEN

            # Completely outside mediabox
            if sx1 <= px0 or sx0 >= px1 or sy1 <= py0 or sy0 >= py1:
                return SpanVisibility.HIDDEN

            # Partially outside mediabox (clipped text)
            if sx0 < px0 or sx1 > px1 or sy0 < py0 or sy1 > py1:
                return SpanVisibility.SUSPECT
        except (ValueError, TypeError, IndexError):
            pass

    # 5. Borderline font size (4.0pt <= size < 5.0pt)
    if 4.0 <= size < 5.0:
        return SpanVisibility.SUSPECT

    return SpanVisibility.VISIBLE


# --- Render check: does the span actually put ink on the page? -------------------------------------
# Text can sit in the text layer yet be invisible: colour equal to the background (not only pure white),
# covered by a shape drawn later, or clipped. Rendering the page once and measuring the luminance range
# under each span catches all of these without OCR.
RENDER_SCALE = 2.0  # 144 dpi
MIN_INK_RANGE = 16  # luminance (0..255) spread below which a span region is considered blank
MIN_REGION_PIXELS = 6


def _render_page_gray(page: Any, scale: float = RENDER_SCALE) -> Any | None:
    """Renders a page to an 8-bit grayscale pixmap, or None when rendering is unavailable."""
    try:
        import fitz

        return page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
    except Exception:
        return None


def span_has_ink(pix: Any, bbox: Any, scale: float = RENDER_SCALE) -> bool:
    """True if the pixels under `bbox` show enough contrast to contain rendered text.

    Unknown / degenerate regions return True (never flag what could not be measured).
    """
    if pix is None or bbox is None or len(bbox) < 4:
        return True
    try:
        x0 = max(0, int(float(bbox[0]) * scale))
        y0 = max(0, int(float(bbox[1]) * scale))
        x1 = min(pix.width, int(float(bbox[2]) * scale) + 1)
        y1 = min(pix.height, int(float(bbox[3]) * scale) + 1)
        if x1 <= x0 or y1 <= y0 or (x1 - x0) * (y1 - y0) < MIN_REGION_PIXELS:
            return True
        samples = pix.samples
        stride = pix.stride
        lo, hi = 255, 0
        for y in range(y0, y1):
            row = samples[y * stride + x0 : y * stride + x1]
            if row:
                lo = min(lo, min(row))
                hi = max(hi, max(row))
        return (hi - lo) >= MIN_INK_RANGE
    except Exception:
        return True


@dataclass
class VisibilityFilterResult:
    visible_spans: list[dict[str, Any]]
    flags: list[str] = field(default_factory=list)
    has_hidden_text: bool = False
    hidden_spans: list[dict[str, Any]] = field(default_factory=list)
    suspect_spans: list[dict[str, Any]] = field(default_factory=list)

    def __iter__(self):
        """Allows unpacking: visible_spans, flags = filter_visible_spans(...)"""
        return iter((self.visible_spans, self.flags))

    def __getitem__(self, index):
        return (self.visible_spans, self.flags)[index]

    def __len__(self):
        return len(self.visible_spans)


def filter_visible_spans(
    doc_or_spans: Any,
    include_suspect: bool = True,
    render_check: bool = True,
) -> VisibilityFilterResult:
    """Filters visible spans from a PyMuPDF document or a list of spans.

    Marks flag 'HIDDEN_TEXT' if any hidden span is detected.
    """
    visible_spans: list[dict[str, Any]] = []
    hidden_spans: list[dict[str, Any]] = []
    suspect_spans: list[dict[str, Any]] = []
    has_hidden_text = False

    # Check if doc_or_spans is a PyMuPDF Document
    if hasattr(doc_or_spans, "page_count") or hasattr(doc_or_spans, "load_page"):
        for page_idx, page in enumerate(doc_or_spans):
            page_rect = getattr(page, "rect", None)
            page_num = getattr(page, "number", page_idx) + 1
            try:
                text_dict = page.get_text("dict")
                blocks = text_dict.get("blocks", [])
            except Exception:
                blocks = []
            pix = _render_page_gray(page) if render_check else None

            for b in blocks:
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        span_copy = dict(span)
                        span_copy["page"] = page_num
                        vis = inspect_span_visibility(span_copy, page_rect)
                        if pix is not None and str(span_copy.get("text", "")).strip():
                            has_ink = span_has_ink(pix, span_copy.get("bbox"))
                            if vis != SpanVisibility.HIDDEN and not has_ink:
                                vis = SpanVisibility.HIDDEN
                                span_copy["hidden_reason"] = "NO_RENDERED_INK"
                            elif vis != SpanVisibility.VISIBLE and has_ink:
                                # White / near-white text on a dark background renders ink: judge it without colour.
                                neutral = inspect_span_visibility({**span_copy, "color": 0}, page_rect)
                                if neutral == SpanVisibility.VISIBLE:
                                    vis = SpanVisibility.VISIBLE
                        span_copy["visibility"] = vis.value

                        if vis == SpanVisibility.VISIBLE:
                            visible_spans.append(span_copy)
                        elif vis == SpanVisibility.HIDDEN:
                            has_hidden_text = True
                            hidden_spans.append(span_copy)
                        elif vis == SpanVisibility.SUSPECT:
                            suspect_spans.append(span_copy)
                            if include_suspect:
                                visible_spans.append(span_copy)
    elif isinstance(doc_or_spans, Iterable) and not isinstance(doc_or_spans, (str, bytes)):
        for item in doc_or_spans:
            if isinstance(item, dict):
                span_copy = dict(item)
                page_rect = span_copy.get("page_rect")
            else:
                span_copy = {"text": str(item)}
                page_rect = getattr(item, "page_rect", None)

            vis = inspect_span_visibility(span_copy, page_rect)
            span_copy["visibility"] = vis.value

            if vis == SpanVisibility.VISIBLE:
                visible_spans.append(span_copy)
            elif vis == SpanVisibility.HIDDEN:
                has_hidden_text = True
                hidden_spans.append(span_copy)
            elif vis == SpanVisibility.SUSPECT:
                suspect_spans.append(span_copy)
                if include_suspect:
                    visible_spans.append(span_copy)

    flags: list[str] = []
    if has_hidden_text:
        flags.append("HIDDEN_TEXT")

    return VisibilityFilterResult(
        visible_spans=visible_spans,
        flags=flags,
        has_hidden_text=has_hidden_text,
        hidden_spans=hidden_spans,
        suspect_spans=suspect_spans,
    )
