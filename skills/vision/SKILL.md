---
name: vision
description: >
  Analyzes images using vision-capable models. Use whenever the conversation
  contains an image (local file path, URL, or data URI) and the current model
  cannot see images. The agent should read Pi's enabled models, check if any
  support vision, prefer free models, and ask the user before using paid ones.
---

# Vision Skill

Enables Pi to "see" images by delegating to a vision-capable model.
`vision.py` is a thin API client — **the agent decides which model to use**.

## How to Use

When the user shares an image (file path, URL, or data URI):

### 1. Get the API key

Read from Pi's auth file:
```bash
python3 -c "
import json
auth = json.load(open('$HOME/.pi/agent/auth.json'))
# Prefer openrouter, fallback to deepseek, kimi
for p in ('openrouter', 'deepseek', 'kimi-coding'):
    key = auth.get(p, {}).get('key', '')
    if key: print(key); break
"
```

### 2. Figure out which models Pi has enabled

Read `~/.pi/agent/settings.json` → `enabledModels`.

Reference: free vision models on OpenRouter (all may or may not work depending on region/availability):
- `nvidia/nemotron-nano-12b-v2-vl:free`
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- `google/gemma-4-26b-a4b-it:free`
- `google/gemma-4-31b-it:free`
- `google/gemma-3-27b-it:free`
- `baidu/qianfan-ocr-fast:free`

Paid models (check the user before using):
- `openai/gpt-4o`
- `anthropic/claude-3.5-sonnet`
- `google/gemini-pro-vision`

To check if a model is **free**: model ID ends with `:free`.

### 3. Decide which model to use

The agent should:
1. **Check Pi's enabled models** — if any support vision and are free, use them
2. **If none enabled**, use the recommended free models from the list above
3. **If only paid models are available**, ask the user before proceeding:
   > "这个模型需要付费（xxx），要用吗？"

To check if a model supports vision, you can:
- Look at the model ID: if it contains `vision`, `vl`, `omni`, etc., it likely does
- Or call the vision.py with it — if it returns None/empty, it doesn't
- Or check OpenRouter's model list: `curl -s "https://openrouter.ai/api/v1/models" | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data'] if 'image' in m.get('architecture',{}).get('modality','') and ':free' in m['id']]"`

To check if a model is **free**: model ID ends with `:free`.
To check if a model is **paid**: no `:free` suffix → ask user.

### 4. Run the analysis

```bash
python3 <SKILL_DIR>/vision.py \
  --model <SELECTED_MODEL> \
  --api-key <API_KEY> \
  --prompt "Describe this image" \
  <IMAGE_PATH_OR_URL>
```

- Use the user's language for the prompt
- If the user asked a specific question, pass it as `--prompt`
- If the model returns None/empty → try a different model
- If HTTP 429 (rate limited) → try a different model
- If HTTP 400 with "location" → skip all models from that provider

## Usage Examples

```bash
# Get the API key
API_KEY=$(python3 -c "import json; print(json.load(open('$HOME/.pi/agent/auth.json'))['openrouter']['key'])")

# Analyze with a free model
python3 <SKILL_DIR>/vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  --api-key "$API_KEY" \
  /tmp/screenshot.png

# Ask a specific question
python3 <SKILL_DIR>/vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  --api-key "$API_KEY" \
  --prompt "这段代码有什么bug？" \
  /tmp/code.png

# Image from URL
python3 <SKILL_DIR>/vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  --api-key "$API_KEY" \
  https://example.com/diagram.png
```

## OpenRouter Free Models Reference

You can check the latest list of free vision models at any time:
```bash
python3 -c "
import json, urllib.request
d = json.load(urllib.request.urlopen('https://openrouter.ai/api/v1/models'))
for m in d['data']:
    if 'image' in m.get('architecture',{}).get('modality','') and ':free' in m['id']:
        print(m['id'])
"
```
