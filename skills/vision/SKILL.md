---
name: vision
description: >
  Analyzes images using vision-capable models. Use whenever the conversation
  contains an image (local file path, URL, or data URI) and the current model
  cannot see images.
---

# Vision Skill

Enables Pi to "see" images. `vision.py` handles everything: reads Pi config for
the API key, tries free vision models, and falls back automatically on failure.

## How to Use

When the user shares an image, just run:

```bash
python3 <SKILL_DIR>/vision.py <IMAGE_PATH_OR_URL>
```

That's it. The script will:
1. Auto-detect the API key from Pi's `auth.json`
2. Try the default free vision model
3. If it fails, automatically try the next model
4. Return the description

### Override the model (optional)

If the default models don't work or you want a specific one:

```bash
python3 <SKILL_DIR>/vision.py --model nvidia/nemotron-nano-12b-v2-vl:free <IMAGE>
```

### Custom prompt

If the user asked a specific question about the image, pass it as `--prompt`:

```bash
python3 <SKILL_DIR>/vision.py --prompt "这段代码有什么bug？" /tmp/code.png
```

### HTTP 400 with "location" error

If you see this, it means the provider is rejecting the model. Skip all models
from that provider.

## Usage Examples

```bash
# Default: auto-model, auto-key
python3 <SKILL_DIR>/vision.py ~/screenshot.png

# Specific model + custom prompt
python3 <SKILL_DIR>/vision.py --model google/gemma-3-27b-it:free --prompt "Describe" https://example.com/pic.png

# Image from clipboard (Pi already saves to /tmp)
python3 <SKILL_DIR>/vision.py /tmp/pi-clipboard-*.png
```

## Reference: Free Vision Models on OpenRouter

All with `:free` suffix. Listed in the order the script tries them:

- `nvidia/nemotron-nano-12b-v2-vl:free`
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- `google/gemma-3-27b-it:free`
- `google/gemma-4-26b-a4b-it:free`
- `google/gemma-4-31b-it:free`
- `baidu/qianfan-ocr-fast:free`

Paid models (no `:free` suffix) — ask the user before using:

- `openai/gpt-4o`
- `anthropic/claude-3.5-sonnet`
- `google/gemini-pro-vision`

To get the latest list of free vision models from OpenRouter:

```bash
python3 -c "
import json, urllib.request
d = json.load(urllib.request.urlopen('https://openrouter.ai/api/v1/models'))
for m in d['data']:
    if 'image' in m.get('architecture',{}).get('modality','') and ':free' in m['id']:
        print(m['id'])
"
```
