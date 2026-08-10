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

## API keys — stored in the skill config (recommended)

When the user tells you an API key (or asks you to save one), **persist it with
`set_key.py`** instead of printing it back:

```bash
python <skill-dir>/scripts/set_key.py glm sk-xxxx          # GLM / Zhipu (free forever)
python <skill-dir>/scripts/set_key.py qwen sk-xxxx         # Qwen / DashScope
python <skill-dir>/scripts/set_key.py siliconflow sk-xxxx  # SiliconFlow
python <skill-dir>/scripts/set_key.py gemini sk-xxxx       # Gemini
python <skill-dir>/scripts/set_key.py mineru your-token    # MinerU (optional)
```

- Keys are saved to `~/.vision-reader/config.json` (override with `VISION_CONFIG`)
  and loaded automatically by `vision.py` on every run — the user never has to
  re-enter them. Provider aliases: `glm`→`ZHIPUAI_API_KEY`, `qwen`→`DASHSCOPE_API_KEY`,
  `siliconflow`→`SILICONFLOW_API_KEY`, `gemini`→`GEMINI_API_KEY`, `mineru`→`MINERU_TOKEN`
  (raw env-var names like `ZHIPUAI_API_KEY` also work).
- Manage: `set_key.py --list` (masked), `set_key.py --delete glm`, `set_key.py --path`.
- Precedence: **real environment variables > config file**. If an env var is already
  set it wins; the config file only fills in what is missing.
- Never echo the full key back to the user — confirm with a masked value
  (e.g. `sk-12…34ab`) or the saved env-var name.
- The config file is plain text; never commit it to git, and never paste it into
  prompts, code, or chat messages.

## Environment variables

Set once at the Windows user level (PowerShell), or simply let the model save
keys with `set_key.py` (see "API keys" above — env vars take precedence over the
config file):

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

## Workarounds — when the client UI blocks image uploads

Some clients (WorkBuddy, Codex, …) detect that the active model is text-only
(DeepSeek, MiMo, GLM-4.5, …) and **disable image attachments at the UI layer** —
the upload control simply rejects images. This skill still works; you just have
to give the model the image as a text-addressable reference instead of an
attachment:

1. **Image URL (recommended).** Ask the user to upload the picture to any image
   host (or reuse an existing link) and paste the URL into the chat. `vision.py`
   auto-downloads HTTP(S) URLs:

        python <skill-dir>/scripts/vision.py https://example.com/photo.png --prompt "<question>"

2. **Local path.** If the image is already on the machine (saved screenshot,
   exported file, …), ask for its absolute path — no upload step at all:

        python <skill-dir>/scripts/vision.py "C:/Users/me/Pictures/shot.png" --prompt "<question>"

3. **Clipboard image.** If the image only exists in the clipboard, ask the user to
   save it to a file first (e.g. `Win+Shift+S` → paste into Paint → Save as PNG),
   then use the local path from step 2.

Never ask the user to paste the image as Base64 text — text-only models cannot
handle it and it explodes the context window. Prefer URL, then local path, in
that order.

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
