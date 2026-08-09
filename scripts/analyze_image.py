#!/usr/bin/env python3
"""Analyze an image with GLM-4.6V-Flash.

This script intentionally uses only the Python standard library so the skill
works in a fresh Codex install without npm or pip setup.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_MODEL = "glm-4.6v-flash"
DEFAULT_TIMEOUT = 120


def is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def image_to_content_url(image: str) -> str:
    if is_url(image):
        return image

    path = Path(image).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Image path is not a file: {path}")

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type or not mime_type.startswith("image/"):
        suffix = path.suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }.get(suffix)
    if not mime_type:
        raise ValueError(f"Unsupported or unknown image type: {path.suffix or '<none>'}")

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_payload(image: str, prompt: str, model: str) -> dict:
    vision_prompt = (
        "Analyze the image carefully and answer the user's request. "
        "Be factual, call out uncertainty, and preserve visible text exactly when OCR is requested.\n\n"
        f"User request: {prompt}"
    )
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_to_content_url(image)}},
                    {"type": "text", "text": vision_prompt},
                ],
            }
        ],
    }


def request_glm(payload: dict, api_key: str, endpoint: str, timeout: int) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GLM API HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"GLM API request failed: {error.reason}") from error


def extract_text(response: dict) -> str:
    choices = response.get("choices")
    if not choices:
        return json.dumps(response, ensure_ascii=False, indent=2)

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        pieces = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    pieces.append(str(text))
            elif item:
                pieces.append(str(item))
        return "\n".join(pieces).strip()
    return str(content).strip()


def main() -> int:
    # Load persisted keys from ~/.vision-reader/config.json (see scripts/set_key.py).
    try:
        from engines.common import ensure_config_loaded

        ensure_config_loaded()
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Analyze an image with GLM-4.6V-Flash.")
    parser.add_argument("image", help="Local image path or HTTP(S) image URL.")
    parser.add_argument(
        "--prompt",
        default="Describe the image and extract any important visible text.",
        help="Question or instruction to answer from the image.",
    )
    parser.add_argument("--model", default=os.environ.get("GLM_VISION_MODEL", DEFAULT_MODEL))
    parser.add_argument("--endpoint", default=os.environ.get("GLM_VISION_BASE_URL", DEFAULT_ENDPOINT))
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("GLM_VISION_TIMEOUT", str(DEFAULT_TIMEOUT))),
    )
    args = parser.parse_args()

    api_key = os.environ.get("ZHIPUAI_API_KEY")
    if not api_key:
        print(
            "ERROR: ZHIPUAI_API_KEY is not set. Set it once at the Windows user level and restart Codex.",
            file=sys.stderr,
        )
        return 2

    try:
        payload = build_payload(args.image, args.prompt, args.model)
        response = request_glm(payload, api_key, args.endpoint, args.timeout)
        answer = extract_text(response)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"# GLM Vision Result\n\nModel: `{args.model}`\n\n{answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
