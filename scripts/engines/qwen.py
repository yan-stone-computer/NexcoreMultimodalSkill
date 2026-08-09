#!/usr/bin/env python3
"""Qwen-VL vision engine via Alibaba DashScope (OpenAI-compatible endpoint).

Free new-user quota on DashScope; qwen-vl-plus is the recommended default.
"""

from __future__ import annotations

import os
from pathlib import Path

from .common import VisionError, get_api_key, openai_chat

NAME = "qwen"
DEFAULT_MODEL = "qwen-vl-plus"
DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def model() -> str:
    return os.environ.get("QWEN_VISION_MODEL", DEFAULT_MODEL)


def endpoint() -> str:
    return os.environ.get("QWEN_VISION_BASE_URL", DEFAULT_ENDPOINT)


def is_available() -> bool:
    return bool(get_api_key("DASHSCOPE_API_KEY", "QWEN_API_KEY"))


def analyze(images: list[Path], prompt: str, timeout: int = 120) -> str:
    api_key = get_api_key("DASHSCOPE_API_KEY", "QWEN_API_KEY")
    if not api_key:
        raise VisionError("DASHSCOPE_API_KEY is not set")
    try:
        return openai_chat(endpoint(), api_key, model(), images, prompt, timeout=timeout)
    except VisionError as exc:
        raise VisionError(f"[qwen:{model()}] {exc}") from exc
