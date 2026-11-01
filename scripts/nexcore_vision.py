#!/usr/bin/env python3
"""Run the bundled NexcoreVision evidence pipeline through Node.js."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engines.common import dotenv_values  # noqa: E402


SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_ROOT = SKILL_ROOT / "integrations" / "nexcorevision"


def _setting(name: str) -> str:
    return os.environ.get(name, "").strip() or dotenv_values().get(name, "").strip()


def resolve_root(explicit: str | None = None) -> Path:
    raw = (explicit or _setting("NEXCORE_VISION_ROOT")).strip()
    candidates = [Path(raw).expanduser().resolve()] if raw else [
        BUNDLED_ROOT,
        Path(sys.prefix) / "share" / "nexcore-multimodal-skill" / "integrations" / "nexcorevision",
    ]
    for root in candidates:
        if (root / "package.json").is_file() and (root / "src" / "cli.ts").is_file():
            return root.resolve()
    raise FileNotFoundError(
        "NexcoreVision pipeline not found; expected package.json and src/cli.ts "
        "in the bundled integration or NEXCORE_VISION_ROOT."
    )


def resolve_node() -> tuple[str, str, int, int]:
    node = shutil.which("node")
    if not node:
        raise FileNotFoundError("Node.js was not found on PATH (NexcoreVision requires Node.js 22.13+).")
    completed = subprocess.run(
        [node, "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    version = completed.stdout.strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.\d+", version)
    if not match:
        raise RuntimeError(f"Unexpected Node.js version output: {version!r}")
    major, minor = int(match.group(1)), int(match.group(2))
    if (major, minor) < (22, 13):
        raise RuntimeError(f"NexcoreVision requires Node.js 22.13+, found {version}")
    return node, version, major, minor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexcore_vision.py",
        description="Run the NexcoreVision OCR + deep vision + VLM evidence pipeline.",
    )
    parser.add_argument(
        "--root",
        help="NexcoreVision checkout; defaults to NEXCORE_VISION_ROOT or the bundled pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health", help="Check Node.js and the bundled pipeline.")
    analyze = subparsers.add_parser("analyze", help="Forward arguments to the NexcoreVision CLI.")
    analyze.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = resolve_root(args.root)
        node, version, _, _ = resolve_node()
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.command == "health":
        print(
            json.dumps(
                {
                    "root": str(root),
                    "node": node,
                    "node_version": version,
                    "cli": str(root / "src" / "cli.ts"),
                    "ready": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    child_env = os.environ.copy()
    for name, value in dotenv_values().items():
        child_env.setdefault(name, value)
    completed = subprocess.run(
        [
            node,
            "--experimental-strip-types",
            str(root / "src" / "cli.ts"),
            *args.args,
        ],
        cwd=root,
        env=child_env,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
