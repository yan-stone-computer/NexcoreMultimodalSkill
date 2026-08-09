#!/usr/bin/env python3
"""MinerU document-parsing engine (OCR / PDF / tables / formulas).

Two modes:

1. Lightweight API (default, NO token required, IP rate-limited):
   - file <= 10MB and <= 20 pages
   - endpoints: https://mineru.net/api/v1/agent/parse/url | /parse/file | /parse/{task_id}

2. Precision API (token from https://mineru.net/apiManage/token, ~1000 pages/day):
   - file <= 200MB and <= 200 pages
   - automatically used when MINERU_TOKEN is set and the input exceeds the
     lightweight limits, or when MINERU_MODE=precision is forced.

Output is the extracted Markdown document.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from .common import (
    VisionError,
    get_api_key,
    http_get_json,
    http_post_json,
    http_request,
    is_document,
    is_url,
    raw_put,
)

NAME = "mineru"

LIGHT_BASE = "https://mineru.net/api/v1/agent"
PRECISION_BASE = "https://mineru.net/api/v4"
LIGHT_MAX_BYTES = 10 * 1024 * 1024
LIGHT_MAX_PAGES = 20
POLL_INTERVAL = 2.0


def _default_language() -> str:
    # PaddleOCR language code; "auto" is not accepted by the parse backend.
    return os.environ.get("MINERU_LANGUAGE", "ch")


def _parse_options(prompt: str) -> dict:
    """Build common parse params; enable OCR by default since this is the OCR engine."""
    return {
        "language": _default_language(),
        "enable_table": True,
        "is_ocr": True,
        "enable_formula": True,
    }


def is_available() -> bool:
    # The lightweight API needs no key at all, so MinerU is always usable.
    return True


def _extract_markdown(data: dict) -> str | None:
    """Best-effort extraction of Markdown from an unknown-shaped response."""
    if not isinstance(data, dict):
        return None
    for key, value in data.items():
        low = str(key).lower()
        if isinstance(value, str) and value.strip():
            if low in {"markdown", "md", "md_content", "markdown_content", "content", "result"}:
                if value.startswith("http://") or value.startswith("https://"):
                    try:
                        _, body = http_request("GET", value, timeout=120)
                        return body.decode("utf-8", errors="replace")
                    except VisionError:
                        continue
                return value
            if low == "markdown_url" and value.startswith("http"):
                try:
                    _, body = http_request("GET", value, timeout=120)
                    return body.decode("utf-8", errors="replace")
                except VisionError:
                    continue
        if isinstance(value, dict):
            found = _extract_markdown(value)
            if found:
                return found
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found = _extract_markdown(item)
                    if found:
                        return found
    return None


# --------------------------------------------------------------------------
# Lightweight mode (free, no token)
# --------------------------------------------------------------------------

def _submit_light_url(url: str, timeout: int) -> str:
    payload = {"url": url, **_parse_options("")}
    response = http_post_json(f"{LIGHT_BASE}/parse/url", payload, timeout=timeout)
    if response.get("code", 0) != 0:
        raise VisionError(f"[mineru] submit failed: {response.get('msg')}")
    return response["data"]["task_id"]


def _submit_light_file(path: Path, timeout: int) -> str:
    payload = {"file_name": path.name, **_parse_options("")}
    response = http_post_json(f"{LIGHT_BASE}/parse/file", payload, timeout=timeout)
    if response.get("code", 0) != 0:
        raise VisionError(f"[mineru] submit failed: {response.get('msg')}")
    data = response["data"]
    upload_url = data.get("file_url")
    if not upload_url:
        raise VisionError(f"[mineru] no upload URL in response: {json.dumps(data, ensure_ascii=False)[:1000]}")
    raw_put(upload_url, path.read_bytes(), timeout=timeout)
    return data["task_id"]


def _poll_light(task_id: str, timeout: int) -> str:
    deadline = time.time() + timeout
    url = f"{LIGHT_BASE}/parse/{task_id}"
    while time.time() < deadline:
        response = http_get_json(url, timeout=timeout)
        if response.get("code", 0) != 0:
            raise VisionError(f"[mineru] poll error: {response.get('msg')}")
        data = response.get("data") or {}
        state = str(data.get("state") or data.get("status") or "").lower()
        if state in {"failed", "error"}:
            raise VisionError(f"[mineru] task failed: {json.dumps(data, ensure_ascii=False)[:1000]}")
        markdown = _extract_markdown(data)
        if markdown:
            return markdown
        if state in {"done", "success", "completed"}:
            raise VisionError(f"[mineru] task finished without markdown: {json.dumps(data, ensure_ascii=False)[:2000]}")
        time.sleep(POLL_INTERVAL)
    raise VisionError(f"[mineru] poll timeout after {timeout}s")


# --------------------------------------------------------------------------
# Precision mode (token)
# --------------------------------------------------------------------------

def _submit_precision_file(path: Path, timeout: int, model_version: str) -> str:
    response = http_post_json(
        f"{PRECISION_BASE}/file-urls/batch",
        {"files": [{"name": path.name}], "model_version": model_version},
        headers={"Authorization": f"Bearer {get_api_key('MINERU_TOKEN')}"},
        timeout=timeout,
    )
    if response.get("code", 0) != 0:
        raise VisionError(f"[mineru] submit failed: {response.get('msg')}")
    data = response["data"]
    upload_urls = data.get("file_urls") or []
    if not upload_urls:
        raise VisionError(f"[mineru] no upload URL: {json.dumps(data, ensure_ascii=False)[:1000]}")
    raw_put(upload_urls[0], path.read_bytes(), timeout=timeout)
    return data["batch_id"]


def _submit_precision_url(url: str, timeout: int, model_version: str) -> str:
    response = http_post_json(
        f"{PRECISION_BASE}/extract/task/batch",
        {"files": [{"url": url, "data_id": "vision-reader"}], "model_version": model_version},
        headers={"Authorization": f"Bearer {get_api_key('MINERU_TOKEN')}"},
        timeout=timeout,
    )
    if response.get("code", 0) != 0:
        raise VisionError(f"[mineru] submit failed: {response.get('msg')}")
    return response["data"]["batch_id"]


def _download_zip_and_extract_md(zip_url: str, timeout: int) -> str:
    _, body = http_request("GET", zip_url, timeout=timeout)
    fd, tmp_zip = tempfile.mkstemp(suffix=".zip", prefix="mineru_")
    os.close(fd)
    Path(tmp_zip).write_bytes(body)
    try:
        with zipfile.ZipFile(tmp_zip) as archive:
            md_names = [n for n in archive.namelist() if n.lower().endswith(".md")]
            if not md_names:
                raise VisionError("[mineru] no markdown in result zip")
            # Prefer full.md, then the longest-named md file.
            md_names.sort(key=lambda n: (n.lower() != "full.md", -len(n)))
            return archive.read(md_names[0]).decode("utf-8", errors="replace")
    finally:
        try:
            Path(tmp_zip).unlink(missing_ok=True)
        except OSError:
            pass


def _poll_precision(batch_id: str, timeout: int) -> str:
    deadline = time.time() + timeout
    url = f"{PRECISION_BASE}/extract-results/batch/{batch_id}"
    while time.time() < deadline:
        response = http_get_json(
            url,
            headers={"Authorization": f"Bearer {get_api_key('MINERU_TOKEN')}"},
            timeout=timeout,
        )
        if response.get("code", 0) != 0:
            raise VisionError(f"[mineru] poll error: {response.get('msg')}")
        data = response.get("data") or {}
        state = str(data.get("state") or "").lower()
        if state in {"failed", "error"}:
            raise VisionError(f"[mineru] task failed: {json.dumps(data, ensure_ascii=False)[:1000]}")
        if state in {"done", "success", "completed"}:
            results = data.get("extract_result") or data.get("results") or []
            for item in results:
                if not isinstance(item, dict):
                    continue
                markdown = _extract_markdown(item)
                if markdown and markdown.startswith("#") and len(markdown) > 20:
                    return markdown
                for key, value in item.items():
                    low = str(key).lower()
                    if isinstance(value, str) and ("zip" in low or "url" in low) and value.startswith("http"):
                        if "markdown" in low or "zip" in low or "result" in low:
                            try:
                                return _download_zip_and_extract_md(value, timeout)
                            except VisionError:
                                continue
        time.sleep(POLL_INTERVAL)
    raise VisionError(f"[mineru] poll timeout after {timeout}s")


def analyze(images: list[Path], prompt: str, timeout: int = 120) -> str:
    """Parse one document/image and return extracted Markdown."""
    if len(images) != 1:
        raise VisionError("[mineru] MinerU processes one file per call")
    source = images[0]
    if not source.exists():
        raise VisionError(f"[mineru] file not found: {source}")
    size = source.stat().st_size
    token = get_api_key("MINERU_TOKEN")
    mode = os.environ.get("MINERU_MODE", "auto").lower()

    model_version = os.environ.get("MINERU_MODEL_VERSION", "vlm")

    if mode == "precision" or (mode == "auto" and token and size > LIGHT_MAX_BYTES):
        if not token:
            raise VisionError("[mineru] precision mode requires MINERU_TOKEN")
        try:
            batch_id = _submit_precision_file(source, timeout, model_version)
            markdown = _poll_precision(batch_id, timeout)
        except VisionError as exc:
            raise VisionError(f"[mineru:precision] {exc}") from exc
        return _wrap(markdown, f"mineru (precision, {model_version})")

    # Lightweight mode
    if size > LIGHT_MAX_BYTES:
        raise VisionError(
            "[mineru] file exceeds the free lightweight limit of 10MB; "
            "set MINERU_TOKEN for the precision API (up to 200MB)"
        )
    try:
        task_id = _submit_light_file(source, timeout)
        markdown = _poll_light(task_id, timeout)
    except VisionError as exc:
        raise VisionError(f"[mineru:light] {exc}") from exc
    return _wrap(markdown, "mineru (lightweight, free)")


def _wrap(markdown: str, source_note: str) -> str:
    header = f"> Document extracted via **{source_note}**\n\n"
    if markdown.startswith("#"):
        return header + markdown
    return header + "```markdown\n" + markdown.strip() + "\n```"
