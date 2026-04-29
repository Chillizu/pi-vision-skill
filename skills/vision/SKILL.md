---
name: vision
description: >
  Analyzes images using free vision-capable models via OpenRouter. Use whenever
  the conversation contains an image (local file path, URL, or data URI) and
  the current model cannot see images. Reads Pi config for API key. Agent must
  pass --model explicitly. Priority: (1) Pi-enabled vision models,
  (2) nvidia/nemotron-nano-12b-v2-vl:free, (3) other free models.
  All models used are FREE (zero cost).
---

# Vision Skill

Enables Pi to "see" images by sending them to a free vision model.
`vision.py` is a **thin API client** — it needs `--model` and `--api-key`.
Model selection logic is in this file (the agent decides).

## How to Use

When the user shares an image (file path, URL, or data URI):

### Step 1: Get API key

Read Pi's auth config:
```bash
python3 -c "
import json
auth = json.load(open('$HOME/.pi/agent/auth.json'))
print(auth.get('openrouter', {}).get('key', ''))
"
```

If the above returns empty, try `deepseek` or `kimi-coding` providers.

### Step 2: Pick a model

**Priority order** (try in this sequence):

| Priority | Model | Notes |
|----------|-------|-------|
| 1st | Pi's enabled models that support vision | Check `~/.pi/agent/settings.json` → `enabledModels` |
| 2nd | `nvidia/nemotron-nano-12b-v2-vl:free` | ✅ Most reliable free vision model |
| 3rd | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | ❓ Sometimes returns None |
| 4th | `openrouter/free` | Routes to available free model |
| 5th | `google/gemma-4-26b-a4b-it:free` | ❗ May be rate-limited or region-blocked |

> **Important**: If a model returns "None", empty, or an error → skip it and try the next one.

### Step 3: Run the analysis

```bash
python3 <SKILL_DIR>/vision.py \
  --model <SELECTED_MODEL> \
  --api-key <API_KEY> \
  --prompt "请描述这张图片的详细内容" \
  <IMAGE_PATH_OR_URL>
```

Use the prompt in the user's language. If the user asks a specific question,
pass it as `--prompt`.

## Usage Examples

### Basic description
```bash
API_KEY=$(python3 -c "import json; print(json.load(open('$HOME/.pi/agent/auth.json'))['openrouter']['key'])")

python3 <SKILL_DIR>/vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  --api-key "$API_KEY" \
  /tmp/screenshot.png
```

### With a specific question
```bash
python3 <SKILL_DIR>/vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  --api-key "$API_KEY" \
  --prompt "What programming language? Explain the code." \
  /tmp/screenshot.png
```

### Image from URL
```bash
python3 <SKILL_DIR>/vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  --api-key "$API_KEY" \
  https://example.com/diagram.png
```

## Error Handling

| Symptom | Likely cause | What to do |
|---------|-------------|------------|
| HTTP 429 | Rate limited | Skip this model, try next in priority |
| HTTP 400 "location" | Region blocked | Skip all models from same provider |
| "null"/"None" returned | Model doesn't support vision | Skip, try next model |
| Connection error | Network issue | Retry once, or report to user |

## Notes

- All models used are **free** on OpenRouter
- The script only needs Python stdlib — no pip install
- Image is sent as base64 (not uploaded)
- For large images, consider checking file size first (< 10MB)
