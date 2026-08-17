#!/usr/bin/env python3
"""ModelVisionSkill — give text-only LLMs (DeepSeek, Xiaomi MiMo, GLM-4.5, etc.) eyes.

Multi-engine CLI that analyzes images / screenshots / documents through free
vision APIs, with automatic fallback and caching. Model-agnostic: works with
any agent platform and any text-only model.

Examples
--------
python vision.py screenshot.png --prompt "What error is shown?"
python vision.py chart.png --engine gemini
python vision.py paper.pdf                          # MinerU, full Markdown
python vision.py a.png b.png --prompt "Compare them" --json
python vision.py photo.png --engine auto --fallback

Engines (all free tiers)
------------------------
web          browser-driven (Doubao/Kimi/Tongyi/...)   none (no key)  images by default
glm          GLM-4.6V-Flash           ZHIPUAI_API_KEY        permanently free
qwen         Qwen-VL (DashScope)      DASHSCOPE_API_KEY      new-user quota
siliconflow  Qwen2.5-VL-7B etc.       SILICONFLOW_API_KEY    sign-up credits
gemini       Gemini 2.5 Flash         GEMINI_API_KEY         ~1500 req/day
mineru       MinerU document parse    MINERU_TOKEN (optional)1000 pages/day, free
                                                             tier w/o token
local        RapidOCR offline         (none)                 fully free

Images default to `web`: vision.py emits browser-guidance (site list, image
paths, prompt) for the agent to execute; API engines take over when no browser
is available or all web sites are exhausted. Documents always use `mineru`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from engines import ENGINES, available, pick, priority_list
from engines import common
from engines.common import (
    VisionError,
    cache_dir,
    cache_get,
    cache_key,
    cache_put,
    cleanup_temp,
    download_to_temp,
    ensure_utf8_stdout,
    is_document,
    is_url,
    kind_of,
)

DEFAULT_PROMPT = "Describe the image and extract any important visible text."
DEFAULT_DOC_PROMPT = "Extract the full document content into Markdown, preserving tables, formulas, and layout."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vision.py",
        description="Analyze images/documents with free vision engines (fallback + cache).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Engines: " + ", ".join(ENGINES) + " | auto",
    )
    parser.add_argument("inputs", nargs="+", help="Local file paths or HTTP(S) image/document URLs.")
    parser.add_argument("--prompt", default=None, help="Question or instruction to answer from the image.")
    parser.add_argument(
        "--engine",
        default="auto",
        help="Engine: auto (default) | " + " | ".join(ENGINES),
    )
    parser.add_argument("--fallback", action="store_true", help="Force fallback to the next engine on failure.")
    parser.add_argument("--no-fallback", action="store_true", help="Disable fallback (auto still retries once).")
    parser.add_argument("--json", action="store_true", help="Emit a JSON object instead of Markdown.")
    parser.add_argument("--no-cache", action="store_true", help="Bypass the on-disk cache.")
    parser.add_argument("--cache-ttl", type=int, default=None, help="Cache TTL in seconds (default 7 days).")
    parser.add_argument("--timeout", type=int, default=120, help="Per-request timeout in seconds.")
    parser.add_argument("--debug", action="store_true", help="Print diagnostics to stderr.")
    return parser


def resolve_inputs(values: list[str]) -> tuple[list[Path], list[Path]]:
    """Return (local_paths, temp_paths_to_cleanup). URLs are downloaded first."""
    local: list[Path] = []
    temp: list[Path] = []
    for value in values:
        if is_url(value):
            try:
                path = download_to_temp(value)
                temp.append(path)
                local.append(path)
            except VisionError as exc:
                raise VisionError(f"Failed to download {value}: {exc}") from exc
        else:
            path = Path(value).expanduser()
            if not path.exists():
                raise VisionError(f"File not found: {path}")
            local.append(path)
    return local, temp


def engine_model(engine) -> str:
    try:
        return engine.model()
    except AttributeError:
        if engine.NAME == "mineru":
            return os.environ.get("MINERU_MODEL_VERSION", "vlm")
        if engine.NAME == "local":
            return "rapidocr"
    return engine.NAME


def analyze_with_engine(engine, images: list[Path], prompt: str, timeout: int, ttl: int | None, use_cache: bool) -> tuple[str, bool]:
    """Run one engine (with caching). Returns (text, cache_hit)."""
    model = engine_model(engine)
    key = cache_key(images, prompt, engine.NAME, model)
    if use_cache and ttl is not None:
        cached = cache_get(key, ttl)
        if cached is not None:
            return cached, True
    # MinerU processes one file per call.
    if engine.NAME == "mineru" and len(images) > 1:
        parts = [engine.analyze([img], prompt, timeout=timeout) for img in images]
        text = "\n\n---\n\n".join(parts)
    else:
        text = engine.analyze(images, prompt, timeout=timeout)
    if use_cache:
        cache_put(key, text)
    return text, False


def web_guide(images: list[Path], prompt: str, request_json: bool) -> str:
    """Emit guidance for the browser-driven web engine (agent executes it).

    The web engine is preferred by default. It is NOT an API module: the agent
    must open a free web model (Doubao/Kimi/Tongyi/...) in a browser, upload the
    image(s), send the prompt and read back the reply. Returns the payload text.
    """
    guide = "\n".join(
        [
            "# Web Engine — browser operation required",
            "",
            "The web engine is preferred and there is no API module for it: the agent must",
            "drive a free web-based multimodal model in a browser to complete the vision task.",
            "",
            "1. Open a site (rotate to the next one when the logged-out daily quota runs out):",
            "   https://www.doubao.com  (Doubao -> Kimi -> Tongyi -> ChatGLM -> Yuanbao -> Xunfei -> ERNIE)",
            f"2. Upload image(s): {', '.join(str(i) for i in images)}",
            f"3. Send prompt verbatim: {prompt!r}",
            "4. Wait for the reply to finish streaming, read the full text, and return it.",
            "",
            "Login rule: if the browser is logged in, keep using the same site (no quota limit).",
            "If logged out, once the page reports quota exhaustion (今日次数已用完 / 已达上限),",
            "close the site and move to the next one.",
            "",
            "Full SOP (login-state detection, quota wording, error handling):",
            "see references/web-engines.md in the skill directory.",
        ]
    )
    if request_json:
        payload = {
            "engine": "web",
            "browser_required": True,
            "images": [str(i) for i in images],
            "prompt": prompt,
            "text": guide,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return guide


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    # Load persisted API keys from ~/.vision-reader/config.json (if any).
    # Real env vars are never overridden; engines keep reading env vars.
    common.ensure_config_loaded()
    args = build_parser().parse_args(argv)

    try:
        images, temp_paths = resolve_inputs(args.inputs)
    except VisionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    document_input = any(is_document(img) for img in images)
    prompt = args.prompt or (DEFAULT_DOC_PROMPT if document_input else DEFAULT_PROMPT)

    ttl = args.cache_ttl if args.cache_ttl is not None else common.CACHE_TTL_DEFAULT
    use_cache = not args.no_cache

    if args.debug:
        print(
            f"[debug] inputs={[str(i) for i in images]} kinds={[kind_of(i) for i in images]} "
            f"document={document_input} prompt={prompt[:80]!r}",
            file=sys.stderr,
        )

    # ----- engine selection -------------------------------------------------
    requested = args.engine or "auto"
    priority = priority_list()

    # Web engine (browser-driven) is the default preferred path for images.
    # It has no API module — emit browser guidance for the agent to execute.
    web_preferred = (
        requested == "web"
        or (
            requested == "auto"
            and not document_input
            and priority
            and priority[0] == "web"
        )
    )
    if web_preferred:
        if args.debug:
            print("[debug] engine=web (browser guidance, preferred)", file=sys.stderr)
        print(web_guide(images, prompt, request_json=args.json))
        cleanup_temp(temp_paths)
        return 0

    try:
        candidates = pick(requested, document_input)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if requested != "auto":
        candidates = [e for e in candidates if e.NAME == requested.lower()]
        if not candidates:
            print(f"ERROR: unknown engine '{requested}'", file=sys.stderr)
            return 2

    fallback = args.fallback or (requested == "auto" and not args.no_fallback)
    # Document inputs can only be served by MinerU (VLM APIs cannot ingest PDFs).
    if document_input:
        candidates = [e for e in candidates if e.NAME == "mineru"]
        fallback = False
        if not candidates:
            print(
                "ERROR: document inputs require the mineru engine, which is unavailable.",
                file=sys.stderr,
            )
            return 2

    if args.debug:
        print(
            f"[debug] engine_order={[e.NAME for e in candidates]} fallback={fallback}",
            file=sys.stderr,
        )

    # ----- run with fallback ------------------------------------------------
    started = time.time()
    errors: list[str] = []
    cache_hit = False
    last_text = ""
    used_engine = None
    for index, engine in enumerate(candidates):
        if engine.NAME != requested and not engine.is_available() and engine.NAME != "mineru":
            # local OCR is_available() probes imports; mineru is always usable.
            if args.debug:
                print(f"[debug] skip {engine.NAME} (not available)", file=sys.stderr)
            continue
        if args.debug:
            print(f"[debug] trying engine={engine.NAME}", file=sys.stderr)
        try:
            last_text, cache_hit = analyze_with_engine(
                engine, images, prompt, args.timeout, ttl, use_cache
            )
            used_engine = engine
            if args.debug:
                print(f"[debug] engine={engine.NAME} OK (cache={cache_hit})", file=sys.stderr)
            break
        except VisionError as exc:
            errors.append(str(exc))
            if args.debug:
                print(f"[debug] engine={engine.NAME} failed: {exc}", file=sys.stderr)
            if index + 1 >= len(candidates) or not fallback:
                break
    else:
        errors.append("no engine produced a result")

    elapsed = time.time() - started
    try:
        cleanup_temp(temp_paths)
    except OSError:
        pass

    if not last_text:
        detail = "\n".join(errors) if errors else "unknown error"
        print(f"ERROR: vision analysis failed.\n{detail}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "engine": used_engine.NAME if used_engine else requested,
            "model": engine_model(used_engine) if used_engine else "",
            "cache_hit": cache_hit,
            "elapsed": round(elapsed, 2),
            "fallbacks": errors,
            "text": last_text,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    engine_name = engine_model(used_engine) if used_engine else "?"
    print(f"# Vision Result\n\nEngine: `{engine_name}`\n")
    if errors:
        print(f"> Note: earlier engines failed and fell back.\n")
    print(last_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def entry() -> None:
    """Console-script entry point (see pyproject.toml)."""
    raise SystemExit(main())
