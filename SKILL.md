---
name: model-vision-skill
description: Give text-only LLMs (DeepSeek, Xiaomi MiMo, GLM-4.5, MiniMax, Llama 3.x, etc.) eyes by analyzing images, screenshots, UI captures, diagrams, charts, and OCR documents through free multi-modal APIs with automatic engine fallback and caching. Use automatically when the user attaches or references an image and asks to read, describe, inspect, extract text, debug a screenshot, identify UI details, understand a chart/table/scanned document, or answer questions grounded in image content. Do not use for image generation or purely text-only tasks.
---

# ModelVisionSkill 👁️

Give every non-multimodal model (DeepSeek, Xiaomi MiMo, GLM-4.5, MiniMax, Llama 3.x…) eyes: bridge free vision APIs with automatic engine fallback, disk caching, and document-grade parsing. All free tiers.

## Engines (all free tiers)

| Engine | Default model | Env var | Free tier | Best for |
|---|---|---|---|---|
| `glm` | GLM-4.6V-Flash | `ZHIPUAI_API_KEY` | Free forever | General vision (default) |
| `qwen` | qwen-vl-plus | `DASHSCOPE_API_KEY` | New-user quota | Chinese / OCR |
| `siliconflow` | Qwen2.5-VL-7B-Instruct | `SILICONFLOW_API_KEY` | Sign-up credits | Any open model |
| `gemini` | gemini-2.5-flash | `GEMINI_API_KEY` | ~1500 req/day | Best free visual reasoning |
| `mineru` | MinerU document parser | `MINERU_TOKEN` (optional) | Tokenless / 1000 pages/day | PDF / tables / formulas |
| `local` | RapidOCR (offline) | none | Fully free | Offline fallback |

## Usage

```bash
python <skill-dir>/scripts/vision.py <image-or-url> [--prompt "<question>"]
```

- Multiple inputs supported (multi-image compare): `vision.py a.png b.png --prompt "Compare them"`
- Local paths and HTTP(S) URLs; URLs are auto-downloaded
- Document inputs (PDF/DOCX/PPTX/XLSX/HTML) automatically route to `mineru` and return full Markdown (tables/formulas/layout preserved)
- Image inputs pick the first available engine by `glm → qwen → siliconflow → gemini → mineru → local` priority; failures auto-fall back to the next engine

### Key flags

| Flag | Description |
|---|---|
| `--engine auto\|glm\|qwen\|siliconflow\|gemini\|mineru\|local` | Force an engine (default `auto`) |
| `--prompt "..."` | The user's question, passed through verbatim |
| `--json` | Structured output (engine/model/cache_hit/elapsed/text) |
| `--no-cache` | Skip the SHA256 disk cache (default TTL 7 days) |
| `--timeout N` | Per-request timeout in seconds (default 120) |
| `--fallback` | Keep falling back even for an explicit engine |
| `--debug` | Print engine-selection diagnostics |

## Engine selection & fallback

- `auto`: documents → `mineru`; images → first configured VLM key, auto-fallback on failure, `local` as offline last resort
- Explicit engine (e.g. `--engine gemini`): only that engine, unless `--fallback`
- Reorder priority via env var: `VISION_ENGINE_PRIORITY="gemini,glm,mineru,local"`

## Environment variables

Set once at the Windows user level (PowerShell):

```powershell
[Environment]::SetEnvironmentVariable('ZHIPUAI_API_KEY',    'your-key', 'User')
[Environment]::SetEnvironmentVariable('DASHSCOPE_API_KEY',  'your-key', 'User')
[Environment]::SetEnvironmentVariable('SILICONFLOW_API_KEY','your-key', 'User')
[Environment]::SetEnvironmentVariable('GEMINI_API_KEY',     'your-key', 'User')
[Environment]::SetEnvironmentVariable('MINERU_TOKEN',       'your-token', 'User')  # optional
```

Restart after setting so new tasks inherit them. **At least one key is enough; MinerU tokenless tier and local OCR need no key at all.**

Overridable:

- `GLM_VISION_MODEL` / `GLM_VISION_BASE_URL` / `GLM_VISION_TIMEOUT`
- `QWEN_VISION_MODEL` / `QWEN_VISION_BASE_URL`
- `SILICONFLOW_VISION_MODEL` / `SILICONFLOW_BASE_URL`
- `GEMINI_VISION_MODEL`
- `MINERU_MODE` (auto/precision)、`MINERU_MODEL_VERSION` (vlm/pipeline)、`MINERU_LANGUAGE` (default ch)
- `VISION_ENGINE_PRIORITY` (comma-separated engine names)
- `VISION_CACHE_DIR` (default `~/.cache/vision-reader`)

## Getting keys

- Zhipu (GLM): https://open.bigmodel.cn — register, GLM-4.6V-Flash is free forever
- Alibaba Bailian (Qwen): https://dashscope.aliyun.com — new-user free quota
- SiliconFlow: https://siliconflow.cn — sign-up credits; pick a free VLM in the model plaza
- Google AI Studio (Gemini): https://aistudio.google.com/apikey — ~1500 free req/day
- MinerU token (optional, 1000 pages/day): https://mineru.net/apiManage/token

## Prompting guidelines

- Pass the user's actual question through in `--prompt`
- OCR: ask for verbatim text, layout, and uncertain characters
- Charts/tables: ask for visible labels, values, trends, and any uncertainty
- UI screenshots: ask for visible state, controls, errors, selected items; only speculate on causes when visually supported
- Documents/PDFs: hand off to `mineru` for full text extraction; no prompt needed

## Output rules

- Never claim certainty beyond the vision model's result; note when the model reports uncertainty or image quality is poor
- Never expose API keys, request headers, or raw Base64 image data
- When multiple engines fail, report a summary of each engine's error
