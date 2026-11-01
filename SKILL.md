---
name: nexcore-multimodal-skill
description: Give text-only LLMs multimodal input and output. Analyze images, screenshots, UI captures, diagrams, charts, and documents through browser or API vision engines with fallback and caching; generate images, edit images, generate videos, query video tasks, and perform optional Agnes vision analysis. Use when the user references visual content, asks what an image/document says, requests image or video generation, asks to edit a picture, or wants a text-only model to gain multimodal capabilities. Use vision.py for inspection and agnes_api.py for media generation. Do not invoke media generation for a purely text-only task.
---

# NexcoreMultimodalSkill 👁️ + 🎨

Give text-only models two missing senses: **see existing material** and **create visual media**.

| Direction | Tool | Use when |
|---|---|---|
| Image/document → text | `scripts/vision.py` | Read screenshots, charts, photos, PDFs, Office files; extract text, diagnose UI, compare images |
| Image generation and editing | `scripts/agnes_api.py image` or `image-edit` | Text-to-image, image-to-image, or multi-image composition |
| Text/image → video | `scripts/agnes_api.py video` | Text-to-video, image-to-video, or keyframe animation |

Provider availability, free quotas, and model names can change upstream. Check the provider response instead of promising a fixed quota.

## Engines (all free tiers)

| Engine | Default model | Env var | Free tier | Best for |
|---|---|---|---|---|
| `web` 🧭 | Doubao → Kimi → Tongyi → ChatGLM → Yuanbao → Xunfei → ERNIE | none | Free, no key | **Images by default** (browser-driven) |
| `glm` | GLM-4.6V-Flash | `ZHIPUAI_API_KEY` | Free forever | General vision (API default) |
| `qwen` | qwen-vl-plus | `DASHSCOPE_API_KEY` | New-user quota | Chinese / OCR |
| `siliconflow` | Qwen2.5-VL-7B-Instruct | `SILICONFLOW_API_KEY` | Sign-up credits | Any open model |
| `gemini` | gemini-2.5-flash | `GEMINI_API_KEY` | ~1500 req/day | Best free visual reasoning |
| `mineru` | MinerU document parser | `MINERU_TOKEN` (optional) | Tokenless / 1000 pages/day | PDF / tables / formulas |
| `local` | RapidOCR (offline) | none | Fully free | Offline fallback |

## Usage

### Inspect an image or document

```bash
python <skill-dir>/scripts/vision.py <image-or-url> [--prompt "<question>"]
```

- Multiple inputs supported (multi-image compare): `vision.py a.png b.png --prompt "Compare them"`
- Local paths and HTTP(S) URLs; URLs are auto-downloaded
- Document inputs (PDF/DOCX/PPTX/XLSX/HTML) automatically route to `mineru` and return full Markdown (tables/formulas/layout preserved)
- Image inputs default to the `web` engine (browser guidance, zero keys); the API chain `glm → qwen → siliconflow → gemini → mineru → local` takes over when no browser is available or all web sites are exhausted; failures auto-fall back to the next engine

### Generate, edit, or animate media

```bash
# Text → image
python <skill-dir>/scripts/agnes_api.py image --prompt "<description>" --download

# Image → image
python <skill-dir>/scripts/agnes_api.py image-edit --prompt "<edit>" --image <path-or-url> --download

# Text/image → video
python <skill-dir>/scripts/agnes_api.py video --prompt "<motion>" --mode text --seconds 5 --wait --download
python <skill-dir>/scripts/agnes_api.py video --prompt "<motion>" --mode text --images <public-url> --wait --download

# Two-frame animation
python <skill-dir>/scripts/agnes_api.py video --prompt "<transition>" --mode keyframe --first-frame <url> --last-frame <url> --wait --download
```

Agnes media generation requires `AGNES_API_KEY`. Image-to-video and keyframe inputs that are sent to the remote service must be public URLs. Local files are accepted by image analysis and image editing; check the CLI output for the exact accepted form.

### Key flags

| Flag | Description |
|---|---|
| `--engine auto\|web\|glm\|qwen\|siliconflow\|gemini\|mineru\|local` | Force an engine (default `auto`; images → `web` browser guidance first) |
| `--prompt "..."` | The user's question, passed through verbatim |
| `--json` | Structured output (engine/model/cache_hit/elapsed/text) |
| `--no-cache` | Skip the SHA256 disk cache (default TTL 7 days) |
| `--timeout N` | Per-request timeout in seconds (default 120) |
| `--fallback` | Keep falling back even for an explicit engine |
| `--debug` | Print engine-selection diagnostics |

## Engine selection & fallback

- **Images default to `web` first** (browser-driven, zero keys): the agent opens
  a free web model, uploads the image, reads back the reply — no API key needed.
  Logged out → rotate to the next site when the daily quota is used up; logged in
  → keep using the same site. Only when no browser is available or **all** web
  sites are exhausted does the API chain take over.
- `auto`: documents → `mineru`; images → `web` (browser) first, then the first
  configured VLM key with auto-fallback on failure, `local` OCR as offline last
  resort. `--engine web` forces the browser path explicitly.
- Explicit engine (e.g. `--engine gemini`): only that engine, unless `--fallback`.
  `--engine web` emits browser guidance instead of calling an API.
- Reorder priority via env var: `VISION_ENGINE_PRIORITY="gemini,glm,mineru,local"`
  (drop `web` to make API engines first); web sites rotate via
  `VISION_WEB_ORDER` (e.g. `kimi,doubao,tongyi`).

## API keys — `.env` file or skill config

The skill ships with a `.env` file at the skill root (copy from `.env.example`).
Fill it in with your keys — `vision.py` loads it automatically on every run:

```
# <skill-dir>/.env
ZHIPUAI_API_KEY=sk-xxxx
DASHSCOPE_API_KEY=sk-xxxx
SILICONFLOW_API_KEY=sk-xxxx
GEMINI_API_KEY=sk-xxxx
MINERU_TOKEN=your-token          # optional
AGNES_API_KEY=sk-xxxx            # image / image-edit / video
```

- Lookup order for the `.env` file: `VISION_ENV_FILE` env var → skill root
  `.env` → current working directory `.env`.
- Supports `KEY=VALUE` lines, optional `export ` prefix, inline `#` comments,
  and quoted values. Empty values are ignored.
- Alternative: persist keys with `set_key.py` (they go to
  `~/.vision-reader/config.json`):

```bash
python <skill-dir>/scripts/set_key.py glm sk-xxxx          # GLM / Zhipu (free forever)
python <skill-dir>/scripts/set_key.py qwen sk-xxxx         # Qwen / DashScope
python <skill-dir>/scripts/set_key.py siliconflow sk-xxxx  # SiliconFlow
python <skill-dir>/scripts/set_key.py gemini sk-xxxx       # Gemini
python <skill-dir>/scripts/set_key.py mineru your-token    # MinerU (optional)
python <skill-dir>/scripts/set_key.py agnes sk-xxxx        # Agnes media
```

- `set_key.py` keys are saved to `~/.vision-reader/config.json` (override with
  `VISION_CONFIG`). Provider aliases: `glm`→`ZHIPUAI_API_KEY`,
  `qwen`→`DASHSCOPE_API_KEY`, `siliconflow`→`SILICONFLOW_API_KEY`,
  `gemini`→`GEMINI_API_KEY`, `mineru`→`MINERU_TOKEN`,
  `agnes`→`AGNES_API_KEY`
  (raw env-var names like `ZHIPUAI_API_KEY` also work).
- Manage: `set_key.py --list` (masked), `set_key.py --delete glm`, `set_key.py --path`.
- Precedence: **real environment variables > `.env` file > config file**. If an
  env var is already set it wins; the `.env` only fills in what is missing, and
  the config file only fills in what is still missing.
- Never echo the full key back to the user — confirm with a masked value
  (e.g. `sk-12…34ab`) or the saved env-var name.
- Key files are plain text; never commit them to git, and never paste them into
  prompts, code, or chat messages.

## Environment variables

Set once at the Windows user level (PowerShell), or simply fill in the skill's
`.env` file / let the model save keys with `set_key.py` (see "API keys" above —
real env vars take precedence over `.env`, which takes precedence over the
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

## Web engines — browser-driven, preferred for images

**Images default to the web engines first** — no API key, no registration
needed. The agent drives a free web-based multimodal model in a browser: open
the site, upload the image, send the prompt, read the reply. API engines are
the fallback when no browser is available or every web site is exhausted.

- Supported sites (rotation order): Doubao `doubao.com` → Kimi `kimi.com` →
  Tongyi `tongyi.com` → ChatGLM `chatglm.cn` → Yuanbao `yuanbao.tencent.com` →
  Xunfei Xinghuo `xinghuo.xfyun.cn` → ERNIE `yiyan.baidu.com`.
- **Logged in → keep using**: if the browser session is logged in to a site, use it
  for every request, no quota limit.
- **Logged out → rotate**: each site has a small daily free quota (Doubao ≈ 15–20
  free turns/day, others vary — always trust the on-page quota notice). When the
  page reports "今日次数已用完 / 已达上限 / 请登录后继续", close that site and move
  to the next one in the list. Once all sites are exhausted, fall back to the API
  engines, or report that the daily web quota is used up and suggest logging in
  or providing an API key.
- `vision.py` returns the browser guidance payload when the web engine is
  selected (default for images, or `--engine web`); the agent executes it.
- Full SOP (login-state detection, upload steps, quota-detection wording, error
  handling): see `references/web-engines.md`.

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
