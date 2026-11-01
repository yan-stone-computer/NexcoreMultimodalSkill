#!/usr/bin/env python3
"""Forward local Qwen-Image jobs to the installed ComfyUI skill CLI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engines.common import dotenv_values  # noqa: E402


COMMANDS = ("health", "start", "stop", "generate", "edit")


def _setting(name: str) -> str:
    return os.environ.get(name, "").strip() or dotenv_values().get(name, "").strip()


def _plugin_candidates() -> list[Path]:
    plugin_root = (
        Path.home()
        / ".codex"
        / "plugins"
        / "cache"
        / "comfyui-qwen-local"
        / "comfyui-qwen-image"
    )
    return sorted(
        plugin_root.glob("*/skills/comfyui-qwen-image/scripts/comfyui_qwen.py"),
        reverse=True,
    )


def resolve_cli(explicit: str | None = None) -> Path:
    """Find the installed comfyui_qwen.py without downloading or installing it."""
    raw = explicit or _setting("COMFYUI_QWEN_CLI")
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw).expanduser())
    else:
        command = shutil.which("comfyui_qwen.py")
        if command:
            candidates.append(Path(command))
        candidates.extend(_plugin_candidates())

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved

    raise FileNotFoundError(
        "ComfyUI Qwen CLI not found. Install/enable the comfyui-qwen-image "
        "skill, or run `python scripts/comfyui_setup.py check` and ask the user "
        "before installing the backend. You can also set COMFYUI_QWEN_CLI to "
        "the plugin's scripts/comfyui_qwen.py path."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="comfyui_local.py",
        description="Run Qwen-Image-2.1 through the installed local ComfyUI skill.",
    )
    parser.add_argument(
        "--cli",
        help="Path to comfyui_qwen.py; defaults to COMFYUI_QWEN_CLI or auto-discovery.",
    )
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cli = resolve_cli(args.cli)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    child_env = os.environ.copy()
    for name, value in dotenv_values().items():
        child_env.setdefault(name, value)
    completed = subprocess.run(
        [sys.executable, str(cli), args.command, *args.args],
        check=False,
        env=child_env,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
