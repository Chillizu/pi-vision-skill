---
name: vision
description: >
  Analyzes images using vision-capable models. Use whenever the conversation
  contains an image (local file path, URL, or data URI) and the current model
  cannot see images.
---

# Vision Skill

Enables Pi to "see" images. `vision.mjs` handles the API call + auto-detects
the API key from Pi's config — **the agent decides which model to use**.

## How to Use

When the user shares an image (file path, URL, or data URI):

### 1. Check Pi's enabled models for vision support

Read `~/.pi/agent/settings.json` → `enabledModels`.

Look for model IDs containing **vision-related keywords** (in order of reliability):
- `vl` — most common indicator (e.g. `nemotron-nano-12b-v2-vl`)
- `vision` — explicit (e.g. `gemini-pro-vision`)
- `omni` — multimodal (e.g. `nemotron-3-nano-omni`)
- `ocr` — text extraction (e.g. `qianfan-ocr-fast`)

If any of Pi's enabled models match these keywords → use that model directly.

**⚠️ Important:** Pi's settings.json stores model IDs with a `provider/` prefix (e.g.
`"openrouter/nvidia/nemotron-nano-12b-v2-vl:free"`). **Strip the `openrouter/` prefix**
before passing to vision.mjs — the script already sends requests to OpenRouter's API.

Correct:
```bash
node vision.mjs --model nvidia/nemotron-nano-12b-v2-vl:free image.png
```
Wrong (causes HTTP 400):
```bash
node vision.mjs --model openrouter/nvidia/nemotron-nano-12b-v2-vl:free image.png
```

### 2. Fallback: use the recommended list (priority order)

If none of Pi's enabled models support vision, try these in **this exact order**.
Earlier models are more likely to work:

| Priority | Model ID | Why |
|----------|----------|-----|
| 🥇 1st | `nvidia/nemotron-nano-12b-v2-vl:free` | Has `vl`, tested reliable |
| 🥇 2nd | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | Has `omni` (multimodal) |
| 3rd | `baidu/qianfan-ocr-fast:free` | Has `ocr` (image input) |
| 4th | `google/gemma-4-26b-a4b-it:free` | May support images |
| 5th | `google/gemma-4-31b-it:free` | May support images |
| 6th | `google/gemma-3-27b-it:free` | May support images |

**Do not deviate from this order.** Skip models that don't have vision keywords
(`vl`, `vision`, `omni`, `ocr`). They will waste a call and return null.

### 3. Paid model guard

If all free models failed and you want to try a paid one (no `:free` suffix),
ask the user first:
> "免费模型都失败了，试试付费模型 xxx 吗？"

### 4. Run the analysis

```bash
node <SKILL_DIR>/vision.mjs --model <MODEL_ID> <IMAGE>
```

- Use the user's language for `--prompt` (optional, defaults to English)
- If the user asked a specific question, pass it as `--prompt "..."`

### 5. Handle failure

| Error | Meaning | Action |
|-------|---------|--------|
| null / empty / "none" | **Not a vision model** | Skip, try next |
| HTTP 429 | Rate limited | Skip, try next |
| HTTP 400 + "location" | Provider rejects model | Skip all from that provider |
| Timeout | Slow response | Set longer timeout with `timeout 180` |

Try next model in the priority list. Usually the 1st or 2nd model works.

## One-liner: find all free vision models on OpenRouter

```bash
curl -s "https://openrouter.ai/api/v1/models" | python3 -c "
import json,sys
for m in json.load(sys.stdin)['data']:
    mid = m['id']
    if ':free' in mid:
        arch = m.get('architecture',{}).get('modality','')
        keywords = ['vl','vision','omni','ocr','image']
        if any(k in mid.lower() or k in arch.lower() for k in keywords):
            print(mid)
"
```

## Usage Examples

```bash
# Recommended: use top priority model
node <SKILL_DIR>/vision.mjs \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  /tmp/screenshot.png

# Custom prompt in user's language
node <SKILL_DIR>/vision.mjs \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  --prompt "这段代码有什么bug？" \
  /tmp/code.png

# Image from URL
node <SKILL_DIR>/vision.mjs \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  https://example.com/diagram.png
```

## API Key

Script auto-detects the API key (no need to extract it yourself):
1. `--api-key` CLI argument (override)
2. `VISION_API_KEY` or `OPENROUTER_API_KEY` env var
3. Pi's `~/.pi/agent/auth.json` (openrouter → deepseek → kimi-coding)
