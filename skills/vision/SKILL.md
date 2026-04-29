---
name: vision
description: >
  Analyzes images using vision-capable models. Use whenever the conversation
  contains an image (local file path, URL, or data URI) and the current model
  cannot see images. The agent should read Pi's enabled models, check if any
  support vision, prefer free models, and ask the user before using paid ones.
---

# Vision Skill

Enables Pi to "see" images. `vision.py` handles the API call + auto-detects
the API key from Pi's config — **the agent decides which model to use**.

## How to Use

When the user shares an image (file path, URL, or data URI):

### 1. Figure out which models Pi has enabled

Read `~/.pi/agent/settings.json` → `enabledModels`.

Reference: free vision models on OpenRouter (all may or may not work depending
on region/availability):
- `nvidia/nemotron-nano-12b-v2-vl:free`
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- `google/gemma-4-26b-a4b-it:free`
- `google/gemma-4-31b-it:free`
- `google/gemma-3-27b-it:free`
- `baidu/qianfan-ocr-fast:free`

To check a model is **free**: model ID ends with `:free`.
To check if a model supports vision, you can:
- Look at the model ID: if it contains `vision`, `vl`, `omni`, etc., it likely does
- Or call vision.py with it — if it returns None/empty, it doesn't
- Or check OpenRouter's model list:
  ```bash
  curl -s "https://openrouter.ai/api/v1/models" | python3 -c "
  import json,sys
  d = json.load(sys.stdin)
  for m in d['data']:
      if 'image' in m.get('architecture',{}).get('modality','') and ':free' in m['id']:
          print(m['id'])
  "
  ```

### 2. Decide which model to use

1. **Check Pi's enabled models** — if any support vision and are free, use them
2. **If none enabled**, use the recommended free models from the list above
3. **If only paid models** (no `:free` suffix), ask the user before proceeding:
   > "这个模型需要付费（xxx），要用吗？"

### 3. Run the analysis

```bash
python3 <SKILL_DIR>/vision.py --model <SELECTED_MODEL> <IMAGE_PATH_OR_URL>
```

- Use the user's language for the prompt (optional `--prompt "..."`)
- If the user asked a specific question, pass it as `--prompt`

### 4. Handle failure

- If the model returns None/empty → **not a vision model**, try another
- If HTTP 429 (rate limited) → try another model
- If HTTP 400 with "location" → skip all models from that provider
- If timed out → bash may need a longer timeout (try `timeout 120`)

## Usage Examples

```bash
# Default prompt, auto-detected API key
python3 <SKILL_DIR>/vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  /tmp/screenshot.png

# Custom prompt
python3 <SKILL_DIR>/vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  --prompt "这段代码有什么bug？" \
  /tmp/code.png

# Image from URL
python3 <SKILL_DIR>/vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  https://example.com/diagram.png
```

## API Key

vision.py auto-detects the API key in this order:
1. `--api-key` CLI argument (override)
2. `VISION_API_KEY` or `OPENROUTER_API_KEY` environment variable
3. Pi's `~/.pi/agent/auth.json` (any of: openrouter, deepseek, kimi-coding)

No need to extract the key yourself — just call the script.
