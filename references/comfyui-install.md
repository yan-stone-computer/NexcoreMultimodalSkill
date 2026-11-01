# ComfyUI + Qwen-Image-2.1 installation

This is a consent-gated local installation flow. A request to generate an image
is not permission to install software or download more than 10 GiB of models.

## 1. Inspect without changing the machine

```bash
python scripts/comfyui_setup.py check
python scripts/comfyui_setup.py plan
```

The check covers the ComfyUI checkout, isolated Python environment,
ComfyUI-GGUF custom node, model size, and `comfyui-qwen-image` bridge.

## 2. Ask for explicit approval

Before installation, tell the user:

- installation target: `D:\ComfyUI` by default on Windows when the `D:` drive
  exists, otherwise `~/ComfyUI`;
- expected hardware: NVIDIA GPU with 8 GiB+ VRAM and 16 GiB+ RAM;
- free disk target: at least 25 GiB including Python packages and downloads;
- model download: about 10.4 GiB;
- Qwen-Image-2.1 uses the Qwen Research License, not an unrestricted
  commercial license;
- an existing non-ComfyUI directory will not be overwritten.

Wait for a clear yes. Then run:

```bash
python scripts/comfyui_setup.py install --yes
```

Use `--root D:\path\to\ComfyUI` to choose another location. Use `--skip-deps`
or `--skip-models` for staged installation. `--comfyui-ref` selects another
ComfyUI tag when `v0.42.0` is unsuitable.

## 3. What the installer does

1. Clones [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) at the
   tested `v0.42.0` tag.
2. Creates an isolated `.venv`.
3. Installs PyTorch and ComfyUI requirements.
4. Clones [leejet/ComfyUI-GGUF](https://github.com/leejet/ComfyUI-GGUF).
5. Downloads Qwen-Image-2.1 files from ModelScope.
6. Verifies each file's byte size and SHA-256.
7. Moves a verified temporary download atomically into `ComfyUI/models`.

The torch index defaults to `https://download.pytorch.org/whl/cu128`. Override
it with `COMFYUI_TORCH_INDEX_URL` before running the installer when the target GPU
needs a different official PyTorch build.

## 4. Verified model files

| Target | Source | Size |
|---|---|---:|
| `models/diffusion_models/qwen_image_2.1-Q4_K.gguf` | [Abiray/Qwen-Image-2.1-GGUF](https://www.modelscope.cn/models/Abiray/Qwen-Image-2.1-GGUF) | 4.20 GB |
| `models/text_encoders/qwen3vl_8b_w4a8.safetensors` | [Comfy-Org/Qwen-Image-2.1](https://modelscope.cn/models/Comfy-Org/Qwen-Image-2.1) | 6.31 GB |
| `models/vae/qwen_image_2.1_vae_bf16.safetensors` | [Comfy-Org/Qwen-Image-2.1](https://modelscope.cn/models/Comfy-Org/Qwen-Image-2.1) | 0.68 GB |

The installer manifest stores the exact URL, byte count, and SHA-256. A size or
hash mismatch fails the installation. Existing valid files are reused. Bad model
files are never overwritten unless the user explicitly approves
`--replace-bad-models`.

Model and software availability can change upstream. Review the license and
model pages before redistribution or commercial use.

## 5. Verify and start

```bash
python scripts/comfyui_setup.py verify
python scripts/comfyui_local.py start
python scripts/comfyui_local.py health
```

Stop the service when finished:

```bash
python scripts/comfyui_local.py stop
```

## Troubleshooting

- `git` missing: install Git before running the installer.
- No compatible NVIDIA PyTorch build: set `COMFYUI_TORCH_INDEX_URL` to the
  official PyTorch index for the machine.
- Download interrupted: inspect the `.part` file and rerun. The installer
  restarts that model download rather than trusting an incomplete file.
- Hash mismatch: do not delete a working installation; report the target path,
  expected size/hash, and actual result. Use `--replace-bad-models` only after
  the user explicitly approves replacing that file.
- Out of memory: use `preview`, reduce resolution or reference count, close other
  GPU/RAM consumers, and keep `--lowvram`. Do not silently change model files.
