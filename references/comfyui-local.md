# Local ComfyUI Qwen-Image route

Use this route for local/private image generation and editing with
Qwen-Image-2.1. It delegates to an installed `comfyui-qwen-image` skill instead
of bundling ComfyUI, model weights, or workflow graphs in this repository.

## Prerequisites

- ComfyUI and the verified Qwen-Image-2.1 weights are already installed.
- The `comfyui-qwen-image` Agent Skill is installed and enabled.
- The local service normally listens on `http://127.0.0.1:8188`.

If the runtime is missing, use the consent-gated process in
`references/comfyui-install.md`.

The bridge auto-discovers the current Codex plugin cache. If discovery fails,
set `COMFYUI_QWEN_CLI` to the absolute path of `scripts/comfyui_qwen.py`.

```text
COMFYUI_QWEN_CLI=C:\path\to\comfyui_qwen.py
COMFYUI_ROOT=D:\ComfyUI
COMFYUI_URL=http://127.0.0.1:8188
```

Do not reinstall ComfyUI, download model weights, or edit ComfyUI core files
for an ordinary image request.

## Commands

```bash
python scripts/comfyui_local.py health
python scripts/comfyui_local.py start
python scripts/comfyui_local.py generate "<prompt>" --preset standard
python scripts/comfyui_local.py edit "<instruction>" --image target.png --preset standard
python scripts/comfyui_local.py stop
```

Presets:

- `preview`: fast check, 8 steps.
- `standard`: normal work, 20 steps.
- `quality`: extra detail, 25 steps.

Preserve a user-specified seed, width, height, steps, negative prompt, and output
directory. Otherwise let the plugin choose its defaults.

## Editing

- Pass images in order with repeated `--image`.
- The first image is the edit target; later images are references.
- State what must remain unchanged and what should change.
- Start with one reference image on lower-memory machines.
- Keep the original canvas unless the user requests a new size.

## Routing

- Local/private image generation or editing, local Qwen, or availability of the
  installed plugin: use `comfyui_local.py`.
- Agnes-specific models, image generation through its API, video generation, or
  an explicit API choice: use `agnes_api.py`.
- Do not silently upload a private image when a local edit can satisfy the task.

## Memory and failures

The plugin starts ComfyUI with `--lowvram`. If generation fails from memory
pressure, lower the preset or dimensions and suggest closing other GPU/RAM
consumers. Do not silently remove models or modify their installation.

## Output

Return the saved absolute path, seed, resolution, steps, and elapsed time. Show
the resulting local PNG when the interface supports it.

Qwen-Image-2.1 weights use the Qwen Research License Agreement. Do not claim
commercial rights on the user's behalf.
