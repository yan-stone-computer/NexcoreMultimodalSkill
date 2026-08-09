#!/usr/bin/env python3
"""GLM-4.6V-Flash vision engine (Zhipu AI, permanently free tier)."""

from __future__ import annotations

import os
from pathlib import Path

from .common import VisionError, get_api_key, openai_chat

NAME = "glm"
DEFAULT_MODEL = "glm-4.6v-flash"
DEFAULT_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def model() -> str:
    return os.environ.get("GLM_VISION_MODEL", DEFAULT_MODEL)


def endpoint() -> str:
    return os.environ.get("GLM_VISION_BASE_URL", DEFAULT_ENDPOINT)


def is_available() -> bool:
    return bool(get_api_key("ZHIPUAI_API_KEY"))


def analyze(images: list[Path], prompt: str, timeout: int = 120) -> str:
    api_key = get_api_key("ZHIPUAI_API_KEY")
    if not api_key:
        raise VisionError("ZHIPUAI_API_KEY is not set")
    try:
        return openai_chat(endpoint(), api_key, model(), images, prompt, timeout=timeout)
    except VisionError as exc:
        raise VisionError(f"[glm:{model()}] {exc}") from exc
