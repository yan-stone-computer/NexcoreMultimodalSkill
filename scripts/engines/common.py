#!/usr/bin/env python3
"""Shared helpers for the vision-reader engines.

Only the Python standard library is required. Pillow is optional: when it is
installed, oversized images are downscaled before upload so free-tier APIs
with strict size limits do not reject them.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CACHE_TTL_DEFAULT = 7 * 24 * 3600  # 7 days


class VisionError(Exception):
    """Raised when an engine cannot produce a result (safe to fall back)."""


def ensure_utf8_stdout() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def get_api_key(*env_names: str) -> str | None:
    """Return the first non-empty API key found in the given env vars."""
    for name in env_names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


# --------------------------------------------------------------------------
# Persisted API-key config (~/.vision-reader/config.json)
#
# Keys stored here are injected into os.environ by ensure_config_loaded()
# before engine selection, so every engine keeps reading env vars unchanged.
# Real environment variables always win over the config file.
# --------------------------------------------------------------------------

def config_path() -> Path:
    """Path of the persisted key config (override with VISION_CONFIG)."""
    override = os.environ.get("VISION_CONFIG", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".vision-reader" / "config.json"


def load_config() -> dict:
    """Load the whole config file; return {} when missing/corrupt."""
    try:
        data = json.loads(config_path().read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(data: dict) -> Path:
    """Persist the config file (creates parent dirs as needed)."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    return path


def stored_keys() -> dict:
    """Return {ENV_VAR: key} currently persisted in the config file."""
    keys = load_config().get("keys", {})
    return keys if isinstance(keys, dict) else {}


def set_stored_key(env_name: str, value: str) -> Path:
    """Persist one API key under the given env-var name. Returns the config path."""
    env_name = env_name.strip().upper()
    value = value.strip()
    if not env_name or not value:
        raise VisionError("set_stored_key requires a non-empty env name and value")
    if any(char in env_name for char in " \t\n\r\"'\\"):
        raise VisionError(f"Invalid env var name: {env_name!r}")
    data = load_config()
    keys = data.get("keys")
    if not isinstance(keys, dict):
        keys = {}
    keys[env_name] = value
    data["keys"] = keys
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return save_config(data)


def delete_stored_key(env_name: str) -> bool:
    """Remove a persisted key. Returns True when it existed and was removed."""
    env_name = env_name.strip().upper()
    data = load_config()
    keys = data.get("keys")
    if not isinstance(keys, dict) or env_name not in keys:
        return False
    del keys[env_name]
    data["keys"] = keys
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_config(data)
    return True


def ensure_config_loaded() -> dict:
    """Inject persisted keys into os.environ (never overriding real env vars).

    Call once at startup, before engine selection. Returns the injected
    {env_var: key} map (empty when nothing was injected).
    """
    injected: dict = {}
    for env_name, value in stored_keys().items():
        if value and not os.environ.get(env_name):
            os.environ[env_name] = value
            injected[env_name] = value
    return injected


def http_request(
    method: str,
    url: str,
    headers: dict | None = None,
    data: bytes | None = None,
    timeout: int = 120,
) -> tuple[int, bytes]:
    """Perform an HTTP request and return (status_code, body_bytes)."""
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise VisionError(f"HTTP {error.code} from {url}: {body[:2000]}") from error
    except urllib.error.URLError as error:
        raise VisionError(f"Request to {url} failed: {error.reason}") from error
    except OSError as error:
        raise VisionError(f"Request to {url} failed: {error}") from error


def http_get_json(url: str, headers: dict | None = None, timeout: int = 120) -> dict:
    status, body = http_request("GET", url, headers=headers, timeout=timeout)
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise VisionError(f"Invalid JSON from {url} (HTTP {status})") from exc


def raw_put(url: str, data: bytes, timeout: int = 120) -> int:
    """PUT raw bytes without any extra headers (for OSS presigned upload URLs).

    urllib adds a default Content-Type which breaks OSS presigned signatures,
    so the request is built manually via http.client.
    """
    import http.client

    parsed = urllib.parse.urlparse(url)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.netloc, timeout=timeout)
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    try:
        conn.putrequest("PUT", path)
        conn.putheader("Content-Length", str(len(data)))
        conn.endheaders()
        conn.send(data)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status >= 400:
            raise VisionError(f"Upload failed (HTTP {resp.status}): {body[:500]}")
        return resp.status
    finally:
        conn.close()


def http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 120) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    merged = {"Content-Type": "application/json"}
    if headers:
        merged.update(headers)
    status, body = http_request("POST", url, headers=merged, data=data, timeout=timeout)
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise VisionError(f"Invalid JSON from {url} (HTTP {status}): {body[:2000]}") from exc


def mime_for(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    suffix = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(suffix, "application/octet-stream")


def read_bytes(path: Path) -> bytes:
    if not path.exists():
        raise VisionError(f"File not found: {path}")
    if not path.is_file():
        raise VisionError(f"Not a file: {path}")
    return path.read_bytes()


def to_data_url(path: Path) -> str:
    encoded = base64.b64encode(read_bytes(path)).decode("ascii")
    return f"data:{mime_for(path)};base64,{encoded}"


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
DOCUMENT_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".html", ".htm", ".txt", ".md"}


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def is_document(path: Path) -> bool:
    return path.suffix.lower() in DOCUMENT_SUFFIXES


def kind_of(path: Path) -> str:
    if is_image(path):
        return "image"
    if is_document(path):
        return "document"
    return "unknown"


def download_to_temp(url: str, timeout: int = 120) -> Path:
    """Download a URL to a temp file, keeping the original extension."""
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in IMAGE_SUFFIXES | DOCUMENT_SUFFIXES:
        suffix = ".bin"
    status, body = http_request("GET", url, timeout=timeout)
    fd, tmp = tempfile.mkstemp(suffix=suffix, prefix="vision_")
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
    return Path(tmp)


def maybe_preprocess(path: Path, max_side: int = 4096, max_bytes: int = 4 * 1024 * 1024) -> Path:
    """Downscale/compress an image in place of the caller when Pillow is available.

    Returns the (possibly new) path. Images that are already small are returned
    untouched. Non-images and non-downloaded files are always returned untouched.
    """
    if not is_image(path):
        return path
    size = path.stat().st_size
    if size <= max_bytes:
        try:
            from PIL import Image
        except ImportError:
            return path
        try:
            with Image.open(path) as img:
                if max(img.size) <= max_side:
                    return path
        except Exception:
            return path
        try:
            with Image.open(path) as img:
                img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
                img.thumbnail((max_side, max_side))
                fd, tmp = tempfile.mkstemp(suffix=".jpg", prefix="vision_")
                os.close(fd)
                img.save(tmp, "JPEG", quality=88)
                return Path(tmp)
        except Exception:
            return path
    # File is large: always try to shrink it when Pillow is available.
    try:
        from PIL import Image
    except ImportError:
        return path
    try:
        with Image.open(path) as img:
            img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
            if max(img.size) > max_side:
                img.thumbnail((max_side, max_side))
            fd, tmp = tempfile.mkstemp(suffix=".jpg", prefix="vision_")
            os.close(fd)
            img.save(tmp, "JPEG", quality=88)
            return Path(tmp)
    except Exception:
        return path


# --------------------------------------------------------------------------
# Cache: SHA256(images + prompt + engine + model) -> JSON, TTL 7 days by default
# --------------------------------------------------------------------------

def cache_dir() -> Path:
    override = os.environ.get("VISION_CACHE_DIR", "").strip()
    if override:
        path = Path(override).expanduser()
    else:
        path = Path.home() / ".cache" / "vision-reader"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_key(images: list[Path], prompt: str, engine: str, model: str) -> str:
    hasher = hashlib.sha256()
    for image in images:
        try:
            hasher.update(image.read_bytes())
        except OSError:
            pass
    hasher.update(("\0" + prompt + "\0" + engine + "\0" + model).encode("utf-8"))
    return hasher.hexdigest()


def cache_get(key: str, ttl: int = CACHE_TTL_DEFAULT) -> str | None:
    path = cache_dir() / f"{key}.json"
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text("utf-8"))
        if time.time() - record.get("ts", 0) > ttl:
            return None
        return record.get("text")
    except (ValueError, OSError):
        return None


def cache_put(key: str, text: str) -> None:
    path = cache_dir() / f"{key}.json"
    try:
        path.write_text(json.dumps({"ts": time.time(), "text": text}, ensure_ascii=False), "utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------
# OpenAI-compatible chat completion helper (used by glm / qwen / siliconflow)
# --------------------------------------------------------------------------

def openai_chat(
    endpoint: str,
    api_key: str,
    model: str,
    images: list[Path],
    prompt: str,
    timeout: int = 120,
    extra_body: dict | None = None,
    max_image_size: int = 8 * 1024 * 1024,
) -> str:
    """Call an OpenAI-compatible /chat/completions endpoint with image parts."""
    content: list[dict] = []
    for image in images:
        preprocessed = maybe_preprocess(image, max_bytes=max_image_size)
        content.append({"type": "image_url", "image_url": {"url": to_data_url(preprocessed)}})
        if preprocessed != image:
            try:
                preprocessed.unlink(missing_ok=True)
            except OSError:
                pass
    content.append({"type": "text", "text": prompt})
    body: dict = {"model": model, "messages": [{"role": "user", "content": content}]}
    if extra_body:
        body.update(extra_body)
    response = http_post_json(
        endpoint,
        body,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    return extract_openai_text(response)


def extract_openai_text(response: dict) -> str:
    """Extract text from an OpenAI-compatible chat completion response."""
    if response.get("error"):
        raise VisionError(f"API error: {response['error']}")
    choices = response.get("choices")
    if not choices:
        raise VisionError(f"Unexpected response (no choices): {json.dumps(response, ensure_ascii=False)[:2000]}")
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


def cleanup_temp(paths: list[Path]) -> None:
    for path in paths:
        try:
            if path and str(path).startswith(tempfile.gettempdir()):
                path.unlink(missing_ok=True)
        except OSError:
            pass
