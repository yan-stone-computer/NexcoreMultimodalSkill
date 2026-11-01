#!/usr/bin/env python3
"""Inspect and install the local ComfyUI + Qwen-Image-2.1 runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))

from comfyui_local import resolve_cli as resolve_plugin_cli  # noqa: E402
from engines.common import dotenv_values  # noqa: E402


COMFYUI_REPO = "https://github.com/Comfy-Org/ComfyUI.git"
GGUF_NODE_REPO = "https://github.com/leejet/ComfyUI-GGUF.git"


def _setting(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or dotenv_values().get(name, "").strip() or default


DEFAULT_COMFYUI_REF = _setting("COMFYUI_REF", "v0.42.0")
DEFAULT_TORCH_INDEX = _setting(
    "COMFYUI_TORCH_INDEX_URL",
    "https://download.pytorch.org/whl/cu128",
).rstrip("/")

MODELS = [
    {
        "target": "models/diffusion_models/qwen_image_2.1-Q4_K.gguf",
        "url": "https://modelscope.cn/models/Abiray/Qwen-Image-2.1-GGUF/resolve/master/"
        "qwen_image_2.1_Q4_K_M.gguf",
        "size": 4_197_494_816,
        "sha256": "29f9c83c249ff0292fb2943fceddfa2319b446601866c82a4f8be062abea72c2",
    },
    {
        "target": "models/text_encoders/qwen3vl_8b_w4a8.safetensors",
        "url": "https://modelscope.cn/models/Comfy-Org/Qwen-Image-2.1/resolve/master/"
        "text_encoders/qwen3vl_8b_w4a8.safetensors",
        "size": 6_312_105_364,
        "sha256": "7754425e55e7bea2bfde4dde59a4cc236cb44e5ee9c215ea66ef8d47012824eb",
    },
    {
        "target": "models/vae/qwen_image_2.1_vae_bf16.safetensors",
        "url": "https://modelscope.cn/models/Comfy-Org/Qwen-Image-2.1/resolve/master/"
        "vae/qwen_image_2.1_vae_bf16.safetensors",
        "size": 675_509_688,
        "sha256": "bb21f7473051e1ac368515dd3f2e15cd44d7a11748ee8823e1ddca3e4876b7c9",
    },
]


def default_root() -> Path:
    override = _setting("COMFYUI_ROOT")
    if override:
        return Path(override).expanduser()
    if os.name == "nt" and Path("D:/").exists():
        return Path("D:/ComfyUI")
    return Path.home() / "ComfyUI"


def python_path(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def inspect_install(root: Path) -> dict:
    try:
        plugin_cli = str(resolve_plugin_cli())
    except FileNotFoundError:
        plugin_cli = None
    models = {
        model["target"]: (
            (root / model["target"]).is_file()
            and (root / model["target"]).stat().st_size == model["size"]
        )
        for model in MODELS
    }
    comfyui = (root / "main.py").is_file()
    venv = python_path(root).is_file()
    gguf_node = (root / "custom_nodes" / "ComfyUI-GGUF").is_dir()
    return {
        "root": str(root),
        "comfyui": comfyui,
        "venv": venv,
        "gguf_node": gguf_node,
        "plugin_cli": plugin_cli,
        "models": models,
        "ready": bool(plugin_cli) and comfyui and venv and gguf_node and all(models.values()),
    }


def build_plan(root: Path) -> list[str]:
    total_gib = sum(model["size"] for model in MODELS) / (1024**3)
    return [
        f"Install root: {root}",
        f"1. Clone ComfyUI {DEFAULT_COMFYUI_REF} from {COMFYUI_REPO}",
        f"2. Create the isolated environment at {python_path(root)}",
        f"3. Install PyTorch with index {DEFAULT_TORCH_INDEX}",
        "4. Install ComfyUI requirements",
        f"5. Clone ComfyUI-GGUF from {GGUF_NODE_REPO}",
        f"6. Download {len(MODELS)} verified model files ({total_gib:.2f} GiB)",
        *[f"   - {model['url']}" for model in MODELS],
        "7. Download each file to a temporary path, verify SHA-256, then rename atomically",
        "8. Install/enable the comfyui-qwen-image Codex skill used by the local bridge",
        "9. Start ComfyUI with --lowvram and verify /system_stats",
        "Recommended hardware: NVIDIA GPU with 8 GiB+ VRAM, 16 GiB+ RAM, 25 GiB+ free disk.",
        "Existing valid files are reused. Bad models are not overwritten unless explicitly requested.",
    ]


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_model(root: Path, model: dict, replace_bad: bool) -> None:
    target = root / model["target"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size == model["size"]:
        print(f"Checking existing {target.name}...", flush=True)
        if sha256(target) == model["sha256"]:
            print(f"OK: {target}", flush=True)
            return
        if not replace_bad:
            raise RuntimeError(
                f"Checksum mismatch for {target}. Re-run with --replace-bad-models "
                "after confirming the target file is safe to replace."
            )

    partial = target.with_suffix(target.suffix + ".part")
    if partial.exists():
        partial.unlink()
    request = Request(model["url"], headers={"User-Agent": "nexcore-comfyui-setup"})
    digest = hashlib.sha256()
    downloaded = 0
    with urlopen(request, timeout=120) as response, partial.open("wb") as output:
        while chunk := response.read(8 * 1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
            downloaded += len(chunk)
            if downloaded % (512 * 1024 * 1024) < len(chunk):
                print(f"  {target.name}: {downloaded / 1024**3:.2f} GiB", flush=True)

    if partial.stat().st_size != model["size"]:
        raise RuntimeError(f"Size mismatch for {target.name}")
    if digest.hexdigest() != model["sha256"]:
        raise RuntimeError(f"SHA-256 mismatch for {target.name}; partial file retained")
    os.replace(partial, target)
    print(f"OK: {target}", flush=True)


def install(
    root: Path,
    *,
    yes: bool,
    skip_deps: bool,
    skip_models: bool,
    replace_bad: bool,
    comfyui_ref: str,
) -> int:
    if not yes:
        print(
            "ERROR: Explicit user consent is required. Show `plan` to the user, "
            "ask whether to install, then re-run with --yes only after approval.",
            file=sys.stderr,
        )
        return 2

    if root.exists() and any(root.iterdir()) and not (root / "main.py").is_file():
        raise RuntimeError(f"{root} is not empty and does not look like a ComfyUI checkout")

    if not (root / "main.py").is_file():
        run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                comfyui_ref,
                COMFYUI_REPO,
                str(root),
            ]
        )
    else:
        print(f"Using existing ComfyUI checkout: {root}")

    if not skip_deps:
        python = python_path(root)
        if not python.is_file():
            run([sys.executable, "-m", "venv", str(root / ".venv")])
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "torch",
                "torchvision",
                "torchaudio",
                "--index-url",
                DEFAULT_TORCH_INDEX,
            ]
        )
        run([str(python), "-m", "pip", "install", "-r", str(root / "requirements.txt")])

    gguf_node = root / "custom_nodes" / "ComfyUI-GGUF"
    if not gguf_node.is_dir():
        run(["git", "clone", "--depth", "1", GGUF_NODE_REPO, str(gguf_node)])
    node_requirements = gguf_node / "requirements.txt"
    if node_requirements.is_file():
        run([str(python_path(root)), "-m", "pip", "install", "-r", str(node_requirements)])

    if not skip_models:
        for model in MODELS:
            download_model(root, model, replace_bad)

    status = inspect_install(root)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if not status["ready"]:
        print(
            "Backend files are installed, but the comfyui-qwen-image skill may still "
            "need to be enabled before generation can run.",
            file=sys.stderr,
        )
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="comfyui_setup.py",
        description="Inspect and install local ComfyUI + Qwen-Image-2.1.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("check", "plan", "verify"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--root", type=Path, default=default_root())

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--root", type=Path, default=default_root())
    install_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm that the user explicitly approved installation.",
    )
    install_parser.add_argument("--skip-deps", action="store_true")
    install_parser.add_argument("--skip-models", action="store_true")
    install_parser.add_argument("--replace-bad-models", action="store_true")
    install_parser.add_argument("--comfyui-ref", default=DEFAULT_COMFYUI_REF)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.expanduser().resolve()

    if args.command == "plan":
        print("\n".join(build_plan(root)))
        return 0
    if args.command == "check":
        status = inspect_install(root)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["ready"] else 1
    if args.command == "verify":
        failed = False
        for model in MODELS:
            path = root / model["target"]
            if not path.is_file() or path.stat().st_size != model["size"]:
                print(f"MISSING_OR_WRONG_SIZE: {path}")
                failed = True
            elif sha256(path) != model["sha256"]:
                print(f"SHA256_MISMATCH: {path}")
                failed = True
            else:
                print(f"OK: {path}")
        return 1 if failed else 0
    return install(
        root,
        yes=args.yes,
        skip_deps=args.skip_deps,
        skip_models=args.skip_models,
        replace_bad=args.replace_bad_models,
        comfyui_ref=args.comfyui_ref,
    )


if __name__ == "__main__":
    raise SystemExit(main())
