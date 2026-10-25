"""Self-hosted Docling (IBM) Hybrid Parser: provides deep Document Layout Analysis (DLA),
table reconstruction (TableFormer), and multi-column reading order recovery
for complex or disordered CVs. Runs 100% locally on VPS.
"""

from __future__ import annotations

import contextlib
import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("cv_screening.docling")

_docling_converter = None


def get_docling_converter():
    """Lazy loader for DocumentConverter to optimize worker startup memory."""
    global _docling_converter
    if _docling_converter is None:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            pipeline_options.do_table_structure = True

            logger.info("Initializing local self-hosted Docling DocumentConverter (CPU-optimized, OCR disabled for digital text)...")
            _docling_converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
            )
            logger.info("Docling DocumentConverter initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Docling converter: {e}")
            return None
    return _docling_converter


def parse_with_docling(content: bytes, filename: str) -> dict[str, Any] | None:
    """Converts a complex PDF document into structured Markdown and semantic sections using Docling."""
    converter = get_docling_converter()
    if converter is None:
        return None

    # Write temporarily to /dev/shm (RAM disk) for zero-disk latency
    tmp_path = Path("/dev/shm") if Path("/dev/shm").exists() else Path(tempfile.gettempdir())
    tmp_file = tmp_path / f"docling_{str(abs(hash(content)))[:12]}_{filename}"

    try:
        tmp_file.write_bytes(content)
        res = converter.convert(str(tmp_file))
        doc = res.document
        markdown_text = doc.export_to_markdown()

        # Parse sections from markdown headers
        sections = []
        current_heading = "HEADER"
        current_lines: list[str] = []

        for line in markdown_text.splitlines():
            line_str = line.strip()
            if line_str.startswith("#"):
                if current_lines:
                    sections.append({
                        "heading": current_heading,
                        "text": "\n".join(current_lines).strip(),
                    })
                    current_lines = []
                current_heading = line_str.lstrip("#").strip()
            else:
                if line_str:
                    current_lines.append(line_str)

        if current_lines:
            sections.append({
                "heading": current_heading,
                "text": "\n".join(current_lines).strip(),
            })

        return {
            "status": "SUCCESS",
            "markdown": markdown_text,
            "sections": sections,
            "engine": "docling_ibm",
        }
    except Exception as e:
        logger.warning(f"Docling parsing failed for {filename}: {e}")
        return None
    finally:
        if tmp_file.exists():
            with contextlib.suppress(Exception):
                tmp_file.unlink()
