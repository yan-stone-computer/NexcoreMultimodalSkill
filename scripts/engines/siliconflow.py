#!/usr/bin/env python3
"""SiliconFlow open-source vision models (OpenAI-compatible, free-tier credits).

Default model Qwen/Qwen2.5-VL-7B-Instruct is on the free list. You can pick any
other available VLM with SILICONFLOW_VISION_MODEL.
"""

from __future__ import annotations

import os
from pathlib import Path

from .common import VisionError, get_api_key, openai_chat

NAME = "siliconflow"
DEFAULT_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
DEFAULT_ENDPOINT = "https://api.siliconflow.cn/v1/chat/completions"


def model() -> str:
    return os.environ.get("SILICONFLOW_VISION_MODEL", DEFAULT_MODEL)


def endpoint() -> str:
    return os.environ.get("SILICONFLOW_BASE_URL", DEFAULT_ENDPOINT)


def is_available() -> bool:
    return bool(get_api_key("SILICONFLOW_API_KEY"))


def analyze(images: list[Path], prompt: str, timeout: int = 120) -> str:
    api_key = get_api_key("SILICONFLOW_API_KEY")
    if not api_key:
        raise VisionError("SILICONFLOW_API_KEY is not set")
    try:
        return openai_chat(endpoint(), api_key, model(), images, prompt, timeout=timeout)
    except VisionError as exc:
        raise VisionError(f"[siliconflow:{model()}] {exc}") from exc
