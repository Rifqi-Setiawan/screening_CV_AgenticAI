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

            for b in blocks:
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        span_copy = dict(span)
                        span_copy["page"] = page_num
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
