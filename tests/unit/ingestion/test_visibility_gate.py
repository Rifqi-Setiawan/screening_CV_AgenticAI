"""Unit tests for Visibility Gate (C2 N0b).

Tests detection of:
- Font size < 4.0pt (hidden)
- Pure white color (hidden)
- Outside mediabox coordinates (hidden)
- Normal visible text (visible)
- Borderline / suspect cases (suspect)
- filter_visible_spans with both span lists and PyMuPDF Documents
"""

from __future__ import annotations

import fitz

from src.worker.visibility import (
    SpanVisibility,
    filter_visible_spans,
    inspect_span_visibility,
)


def test_normal_text_is_visible():
    page_rect = (0.0, 0.0, 595.0, 842.0)
    span = {
        "text": "Software Engineer with 5 years experience",
        "size": 11.0,
        "color": 0,  # Black
        "bbox": (50.0, 100.0, 300.0, 120.0),
    }
    status = inspect_span_visibility(span, page_rect)
    assert status == SpanVisibility.VISIBLE
    assert status == "VISIBLE"


def test_micro_font_below_4pt_is_hidden():
    page_rect = (0.0, 0.0, 595.0, 842.0)
    for sz in [0.5, 1.0, 2.0, 3.5, 3.99]:
        span = {
            "text": "keyword_stuffing_python_django_fastapi",
            "size": sz,
            "color": 0,
            "bbox": (50.0, 100.0, 200.0, 104.0),
        }
        assert inspect_span_visibility(span, page_rect) == SpanVisibility.HIDDEN


def test_white_text_is_hidden():
    page_rect = (0.0, 0.0, 595.0, 842.0)
    # Integer hex 0xFFFFFF (16777215)
    span_hex = {
        "text": "hidden keywords in white font",
        "size": 10.0,
        "color": 0xFFFFFF,
        "bbox": (50.0, 100.0, 300.0, 120.0),
    }
    assert inspect_span_visibility(span_hex, page_rect) == SpanVisibility.HIDDEN

    # RGB tuple (255, 255, 255)
    span_rgb = {
        "text": "hidden keywords in white font rgb",
        "size": 10.0,
        "color": (255, 255, 255),
        "bbox": (50.0, 100.0, 300.0, 120.0),
    }
    assert inspect_span_visibility(span_rgb, page_rect) == SpanVisibility.HIDDEN

    # Float RGB tuple (1.0, 1.0, 1.0)
    span_float_rgb = {
        "text": "hidden keywords in float rgb",
        "size": 10.0,
        "color": (1.0, 1.0, 1.0),
        "bbox": (50.0, 100.0, 300.0, 120.0),
    }
    assert inspect_span_visibility(span_float_rgb, page_rect) == SpanVisibility.HIDDEN


def test_outside_mediabox_coordinates_is_hidden():
    page_rect = (0.0, 0.0, 595.0, 842.0)

    # Completely off to the left
    span_left = {
        "text": "Offscreen text left",
        "size": 10.0,
        "color": 0,
        "bbox": (-200.0, 100.0, -10.0, 120.0),
    }
    assert inspect_span_visibility(span_left, page_rect) == SpanVisibility.HIDDEN

    # Completely off the bottom
    span_bottom = {
        "text": "Offscreen text bottom",
        "size": 10.0,
        "color": 0,
        "bbox": (50.0, 900.0, 200.0, 920.0),
    }
    assert inspect_span_visibility(span_bottom, page_rect) == SpanVisibility.HIDDEN


def test_render_mode_invisible_is_hidden():
    page_rect = (0.0, 0.0, 595.0, 842.0)
    span = {
        "text": "Invisible OCR overlay",
        "size": 10.0,
        "color": 0,
        "bbox": (50.0, 100.0, 200.0, 120.0),
        "render_mode": 3,
    }
    assert inspect_span_visibility(span, page_rect) == SpanVisibility.HIDDEN


def test_suspect_borderline_font_size():
    page_rect = (0.0, 0.0, 595.0, 842.0)
    span = {
        "text": "Borderline font 4.5pt",
        "size": 4.5,
        "color": 0,
        "bbox": (50.0, 100.0, 200.0, 105.0),
    }
    assert inspect_span_visibility(span, page_rect) == SpanVisibility.SUSPECT


def test_suspect_near_white_color():
    page_rect = (0.0, 0.0, 595.0, 842.0)
    # Color #F8F8F8 is 16316664
    span = {
        "text": "Near white low contrast text",
        "size": 10.0,
        "color": (248, 248, 248),
        "bbox": (50.0, 100.0, 200.0, 120.0),
    }
    assert inspect_span_visibility(span, page_rect) == SpanVisibility.SUSPECT


def test_suspect_partially_clipped_coordinates():
    page_rect = (0.0, 0.0, 595.0, 842.0)
    # Span starts inside but extends past right page edge
    span = {
        "text": "Partially clipped text across page boundary",
        "size": 10.0,
        "color": 0,
        "bbox": (500.0, 100.0, 650.0, 120.0),
    }
    assert inspect_span_visibility(span, page_rect) == SpanVisibility.SUSPECT


def test_filter_visible_spans_with_list():
    page_rect = (0.0, 0.0, 595.0, 842.0)
    spans = [
        {"text": "Visible Experience", "size": 11.0, "color": 0, "bbox": (50, 50, 200, 70), "page_rect": page_rect},
        {"text": "Hidden stuffing 1", "size": 2.0, "color": 0, "bbox": (50, 80, 200, 85), "page_rect": page_rect},
        {
            "text": "Hidden stuffing 2",
            "size": 10.0,
            "color": 0xFFFFFF,
            "bbox": (50, 90, 200, 105),
            "page_rect": page_rect,
        },
        {"text": "Visible Skills", "size": 10.0, "color": 0, "bbox": (50, 120, 200, 140), "page_rect": page_rect},
    ]

    res = filter_visible_spans(spans)
    assert res.has_hidden_text is True
    assert "HIDDEN_TEXT" in res.flags
    assert len(res.visible_spans) == 2
    assert [s["text"] for s in res.visible_spans] == ["Visible Experience", "Visible Skills"]
    assert len(res.hidden_spans) == 2

    # Verify tuple unpacking support
    vis, flags = filter_visible_spans(spans)
    assert len(vis) == 2
    assert "HIDDEN_TEXT" in flags


def test_filter_visible_spans_with_pymupdf_doc():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # 1. Normal text
    page.insert_text(fitz.Point(50, 100), "Senior Backend Engineer", fontsize=12, color=(0, 0, 0))

    # 2. Hidden micro-font (< 4pt)
    page.insert_text(fitz.Point(50, 200), "hidden_cheat_keyword", fontsize=2, color=(0, 0, 0))

    # 3. Hidden white text
    page.insert_text(fitz.Point(50, 300), "invisible_white_keyword", fontsize=10, color=(1, 1, 1))

    res = filter_visible_spans(doc)
    doc.close()

    assert res.has_hidden_text is True
    assert "HIDDEN_TEXT" in res.flags
    visible_texts = [s["text"] for s in res.visible_spans]
    assert any("Senior Backend Engineer" in t for t in visible_texts)
    # Hidden keywords must be excluded
    assert not any("hidden_cheat_keyword" in t for t in visible_texts)
    assert not any("invisible_white_keyword" in t for t in visible_texts)
