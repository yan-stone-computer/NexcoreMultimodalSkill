#!/usr/bin/env python3
"""Google Gemini vision engine (free via AI Studio API keys, ~1500 req/day).

Uses the native generateContent endpoint; images are inlined as base64.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from .common import (
    VisionError,
    get_api_key,
    http_post_json,
    mime_for,
    maybe_preprocess,
    read_bytes,
)

NAME = "gemini"
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"


def model() -> str:
    return os.environ.get("GEMINI_VISION_MODEL", DEFAULT_MODEL)


def is_available() -> bool:
    return bool(get_api_key("GEMINI_API_KEY", "GOOGLE_API_KEY"))


def analyze(images: list[Path], prompt: str, timeout: int = 120) -> str:
    api_key = get_api_key("GEMINI_API_KEY", "GOOGLE_API_KEY")
    if not api_key:
        raise VisionError("GEMINI_API_KEY is not set")
    parts: list[dict] = []
    for image in images:
        preprocessed = maybe_preprocess(image)
        parts.append(
            {
                "inline_data": {
                    "mime_type": mime_for(preprocessed),
                    "data": base64.b64encode(read_bytes(preprocessed)).decode("ascii"),
                }
            }
        )
        if preprocessed != image:
            try:
                preprocessed.unlink(missing_ok=True)
            except OSError:
                pass
    parts.append({"text": prompt})
    url = f"{DEFAULT_ENDPOINT}/{model()}:generateContent?key={api_key}"
    try:
        response = http_post_json(url, {"contents": [{"parts": parts}]}, timeout=timeout)
    except VisionError as exc:
        raise VisionError(f"[gemini:{model()}] {exc}") from exc
    if response.get("error"):
        raise VisionError(f"[gemini:{model()}] API error: {response['error']}")
    try:
        candidates = response["candidates"]
        texts = []
        for part in candidates[0]["content"]["parts"]:
            if "text" in part:
                texts.append(part["text"])
        text = "\n".join(texts).strip()
        if not text:
            raise VisionError("[gemini] empty response")
        return text
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionError(
            f"[gemini:{model()}] unexpected response: {json.dumps(response, ensure_ascii=False)[:2000]}"
        ) from exc
