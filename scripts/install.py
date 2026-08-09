#!/usr/bin/env python3
"""ModelVisionSkill installer — install the vision skill into mainstream agent platforms.

Usage:
  python scripts/install.py --all                # install everywhere it is detected
  python scripts/install.py --target claude      # Claude Code only
  python scripts/install.py --target trae        # project-level .trae/skills
  python scripts/install.py --target trae --global  # global ~/.trae/skills
  python scripts/install.py --dest <dir>         # copy into a custom directory

Platforms: claude | codex | opencode | trae | workbuddy | cursor
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

SKILL_NAME = "model-vision-skill"
SKILL_DIR = Path(__file__).resolve().parent.parent  # repo root (contains SKILL.md)

# Directories/files we never copy into a skill install.
EXCLUDE = {".git", ".workbuddy", "__pycache__", ".idea", ".vscode", "tests", "assets", "config.json"}


def home() -> Path:
    return Path.home()


def platform_paths(global_install: bool = False) -> dict[str, list[Path]]:
    h = home()
    return {
        "claude": [h / ".claude" / "skills" / SKILL_NAME],
        "workbuddy": [h / ".workbuddy" / "skills" / SKILL_NAME],
        "trae": (
            [h / ".trae" / "skills" / SKILL_NAME]
            if global_install
            else [Path(".trae") / "skills" / SKILL_NAME]
        ),
        "codex": [h / ".codex" / "agents" / "model-vision-skill.yaml"],
        "opencode": [h / ".config" / "opencode" / "agent" / "model-vision-skill.md"],
        "cursor": [Path(".cursor") / "rules" / "model-vision-skill.mdc"],
    }


def copy_skill(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)

    def ignore(dirname: str, names: list[str]) -> set[str]:
        return {n for n in names if n in EXCLUDE or n.endswith((".pyc", ".pyo"))}

    shutil.copytree(SKILL_DIR, dest, dirs_exist_ok=True, ignore=ignore)
    # Never keep install.py inside the installed copy.
    (dest / "scripts" / "install.py").unlink(missing_ok=True)


def render_codex_agent() -> str:
    src = SKILL_DIR / "agents" / "openai.yaml"
    return src.read_text("utf-8") if src.exists() else "# see agents/openai.yaml in the repo\n"


def render_opencode_agent() -> str:
    return (
        "---\n"
        "description: ModelVisionSkill — give text-only LLMs (DeepSeek etc.) eyes. Analyze "
        "images/screenshots/PDFs via free vision APIs with auto fallback. Use when the "
        "user attaches or references an image and asks to read, describe, inspect, extract "
        "text, or debug a screenshot.\n"
        "---\n\n"
        "## ModelVisionSkill\n\n"
        "When you need to understand an image or document, run:\n\n"
        "```bash\n"
        f"python {SKILL_DIR}/scripts/vision.py <image-or-url> --prompt \"<user question>\"\n"
        "```\n\n"
        "- Support multiple inputs: `vision.py a.png b.png --prompt \"compare\"`\n"
        "- PDF/DOCX/PPTX inputs are parsed via MinerU into Markdown automatically\n"
        "- Use `--json` for structured output, `--engine <name>` to force an engine\n"
    )


def render_cursor_rule() -> str:
    return (
        "---\n"
        "description: ModelVisionSkill — analyze images/screenshots/PDFs via free vision APIs.\n"
        "globs: []\n"
        "---\n\n"
        "当需要理解图片 / 截图 / 文档（OCR、看图、调试截图、提取图表信息）时：\n\n"
        "```bash\n"
        f"python {SKILL_DIR}/scripts/vision.py <image-or-url> --prompt \"<问题>\"\n"
        "```\n\n"
        "多图对比、PDF 解析、--json 结构化输出见仓库 README。\n"
    )


def install(target: str, global_install: bool, verbose: bool = False) -> bool:
    paths = platform_paths(global_install).get(target)
    if not paths:
        print(f"[model-vision-skill] unknown target: {target}")
        return False

    installed = False
    for dest in paths:
        try:
            if target == "codex":
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(render_codex_agent(), "utf-8")
            elif target == "opencode":
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(render_opencode_agent(), "utf-8")
            elif target == "cursor":
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(render_cursor_rule(), "utf-8")
            else:
                copy_skill(dest)
            print(f"[model-vision-skill] OK  -> {dest}")
            installed = True
        except OSError as exc:
            print(f"[model-vision-skill] FAIL -> {dest}: {exc}")
    return installed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install ModelVisionSkill into agent platforms.")
    parser.add_argument("--all", action="store_true", help="Install into all supported platforms.")
    parser.add_argument("--target", choices=["claude", "codex", "opencode", "trae", "workbuddy", "cursor"])
    parser.add_argument("--global", dest="global_install", action="store_true", help="Install to the user-global dir (Trae only).")
    parser.add_argument("--dest", help="Copy the whole skill into a custom directory.")
    args = parser.parse_args(argv)

    print(f"[model-vision-skill] source: {SKILL_DIR}")

    if args.dest:
        copy_skill(Path(args.dest).expanduser())
        print(f"[model-vision-skill] OK  -> {args.dest}")
        return 0

    targets = [args.target] if args.target else (list(platform_paths().keys()) if args.all else [])
    if not targets:
        parser.print_help()
        return 2

    ok = 0
    for target in targets:
        ok += 1 if install(target, args.global_install) else 0

    if ok:
        print(
            "\n[model-vision-skill] Next: give the model at least one free API key.\n"
            "The model can persist keys for you anytime with:\n"
            f"  python {SKILL_DIR / 'scripts' / 'set_key.py'} glm sk-xxxx       # GLM (free forever)\n"
            f"  python {SKILL_DIR / 'scripts' / 'set_key.py'} gemini sk-xxxx    # ~1500 req/day\n"
            f"  python {SKILL_DIR / 'scripts' / 'set_key.py'} qwen sk-xxxx      # Qwen-VL\n"
            f"  python {SKILL_DIR / 'scripts' / 'set_key.py'} siliconflow sk-xxxx\n"
            f"  python {SKILL_DIR / 'scripts' / 'set_key.py'} mineru your-token # optional\n"
            "Keys are stored in ~/.vision-reader/config.json and loaded automatically.\n"
            "MinerU free tier and local RapidOCR need no key at all."
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
