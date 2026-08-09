#!/usr/bin/env python3
"""Vision-reader engine registry."""

from __future__ import annotations

from pathlib import Path

from . import gemini, glm, local, mineru, qwen, siliconflow

# Default priority (first available engine wins). Override with
# VISION_ENGINE_PRIORITY="gemini,glm,mineru,local" etc.
ENGINES = {
    "glm": glm,
    "qwen": qwen,
    "siliconflow": siliconflow,
    "gemini": gemini,
    "mineru": mineru,
    "local": local,
}

DEFAULT_PRIORITY = ["glm", "qwen", "siliconflow", "gemini", "mineru", "local"]


def priority_list() -> list[str]:
    override = __import__("os").environ.get("VISION_ENGINE_PRIORITY", "").strip()
    if override:
        names = [n.strip().lower() for n in override.split(",") if n.strip()]
        if names:
            return names
    return DEFAULT_PRIORITY


def resolve(names: list[str]) -> list:
    resolved = []
    for name in names:
        engine = ENGINES.get(name)
        if engine:
            resolved.append(engine)
    return resolved


def available() -> list:
    """Engines that can run right now, in priority order."""
    return [engine for engine in resolve(priority_list()) if engine.is_available()]


def pick(engine_name: str, is_document_input: bool) -> list:
    """Select engines for the requested mode.

    - explicit engine: that engine only
    - auto: document inputs prefer mineru first; otherwise VLM engines in
      priority order, with local OCR as offline fallback.
    """
    if engine_name and engine_name != "auto":
        engine = ENGINES.get(engine_name.lower())
        if not engine:
            raise ValueError(
                f"Unknown engine '{engine_name}'. Choose from: {', '.join(ENGINES)} or 'auto'"
            )
        return [engine]

    names = priority_list()
    if is_document_input:
        names = ["mineru"] + [n for n in names if n != "mineru"]
    return resolve(names)
