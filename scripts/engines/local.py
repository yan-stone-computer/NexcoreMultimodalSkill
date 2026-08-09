#!/usr/bin/env python3
"""Local offline OCR engine (RapidOCR, fully free, no network).

Optional dependency: `pip install rapidocr-onnxruntime` (or the newer
`rapidocr` package). Only images are supported; PDFs must go through MinerU.
"""

from __future__ import annotations

from pathlib import Path

from .common import VisionError, is_image

NAME = "local"

_ocr = None


def _load_ocr():
    global _ocr
    if _ocr is not None:
        return _ocr
    try:
        from rapidocr_onnxruntime import RapidOCR

        _ocr = RapidOCR()
    except ImportError:
        try:
            from rapidocr import RapidOCR

            _ocr = RapidOCR()
        except ImportError:
            raise VisionError(
                "[local] RapidOCR is not installed. Install it with:\n"
                "  pip install rapidocr-onnxruntime"
            ) from None
    return _ocr


def is_available() -> bool:
    try:
        _load_ocr()
        return True
    except VisionError:
        return False


def analyze(images: list[Path], prompt: str, timeout: int = 120) -> str:
    ocr = _load_ocr()
    sections: list[str] = []
    for image in images:
        if not is_image(image):
            raise VisionError(f"[local] unsupported file for local OCR: {image.name}")
        result, _elapse = ocr(str(image))
        lines = []
        for item in result or []:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                text = str(item[1])
                confidence = ""
                if len(item) >= 3:
                    try:
                        confidence = f" ({float(item[2]):.2f})"
                    except (TypeError, ValueError):
                        pass
                if text.strip():
                    lines.append(text.strip() + confidence)
        if lines:
            sections.append(f"## `{image.name}`\n\n" + "\n".join(lines))
    if not sections:
        return "> No text detected by local OCR."
    return "> Local OCR (RapidOCR, offline)\n\n" + "\n\n".join(sections)
