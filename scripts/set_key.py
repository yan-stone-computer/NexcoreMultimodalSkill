#!/usr/bin/env python3
"""Store / list / delete vision API keys in the skill's persisted config.

Keys are saved to ~/.vision-reader/config.json (override with VISION_CONFIG)
and automatically loaded by vision.py on every run. Real environment
variables still take precedence over this file.

Usage:
  python scripts/set_key.py glm sk-xxxx                # store a key (provider alias ok)
  python scripts/set_key.py ZHIPUAI_API_KEY sk-xxxx    # raw env-var name also works
  python scripts/set_key.py --list                     # show stored keys (masked)
  python scripts/set_key.py --delete glm               # remove a key by provider
  python scripts/set_key.py --path                     # print the config file path

Providers (alias -> env var):
  glm / zhipu / zhipuai            -> ZHIPUAI_API_KEY
  qwen / dashscope / aliyun / bailian -> DASHSCOPE_API_KEY
  siliconflow / silicon            -> SILICONFLOW_API_KEY
  gemini / google                  -> GEMINI_API_KEY
  mineru                           -> MINERU_TOKEN
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/

from engines.common import (  # noqa: E402
    VisionError,
    config_path,
    delete_stored_key,
    ensure_utf8_stdout,
    set_stored_key,
    stored_keys,
)

# Provider alias -> env var name
PROVIDERS = {
    "glm": "ZHIPUAI_API_KEY",
    "zhipu": "ZHIPUAI_API_KEY",
    "zhipuai": "ZHIPUAI_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "aliyun": "DASHSCOPE_API_KEY",
    "bailian": "DASHSCOPE_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
    "silicon": "SILICONFLOW_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
    "mineru": "MINERU_TOKEN",
}


def resolve_env(name: str) -> str:
    """Map a provider alias (or raw env name) to a canonical env var name."""
    lower = name.strip().lower()
    if lower in PROVIDERS:
        return PROVIDERS[lower]
    upper = name.strip().upper()
    if not upper or any(c in upper for c in " \t\n\r\"'\\"):
        raise VisionError(f"Invalid provider/env name: {name!r}")
    return upper


def mask(value: str) -> str:
    """Mask a key so it can be echoed safely."""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}…{value[-4:]}"


def cmd_store(name: str, value: str) -> int:
    env_name = resolve_env(name)
    path = set_stored_key(env_name, value)
    print(f"OK: {env_name} saved -> {path}")
    print(f"    masked: {mask(value)}")
    print("    vision.py will load it automatically on the next run.")
    return 0


def cmd_list() -> int:
    keys = stored_keys()
    if not keys:
        print("No keys stored yet.")
        return 0
    print(f"Stored keys ({config_path()}):")
    for env_name in sorted(keys):
        print(f"  {env_name}: {mask(keys[env_name])}")
    return 0


def cmd_delete(name: str) -> int:
    env_name = resolve_env(name)
    if delete_stored_key(env_name):
        print(f"OK: {env_name} removed.")
        return 0
    print(f"{env_name} was not stored (nothing to delete).")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="set_key.py",
        description="Persist vision API keys for ModelVisionSkill.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Providers: " + ", ".join(sorted(set(PROVIDERS.values()))),
    )
    parser.add_argument("name", nargs="?", help="provider alias or env var name (e.g. glm / ZHIPUAI_API_KEY)")
    parser.add_argument("value", nargs="?", help="the API key to store (omit when using --list/--delete/--path)")
    parser.add_argument("--list", action="store_true", help="show stored keys (masked)")
    parser.add_argument("--delete", metavar="NAME", help="delete a stored key by provider or env var name")
    parser.add_argument("--path", action="store_true", help="print the config file path and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    args = build_parser().parse_args(argv)

    if args.path:
        print(config_path())
        return 0
    if args.list:
        return cmd_list()
    if args.delete:
        return cmd_delete(args.delete)
    if args.name and args.value:
        return cmd_store(args.name, args.value)
    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
