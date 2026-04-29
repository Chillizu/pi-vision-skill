---
name: vision
description: >
  Analyzes images using free vision-capable models via OpenRouter. Use whenever
  the conversation contains an image (local file path, URL, or data URI) and
  you need to understand what's in the image. Automatically detects Pi-configured
  API keys and prefers models already enabled in Pi settings. All models used
  are FREE (zero cost).
---

# Vision Skill

Enables Pi to "see" images by sending them to a free vision model on OpenRouter.

## Quick Start

When you encounter an image in the conversation (file path, URL, or data URI):

```bash
python3 ./vision.py <IMAGE_PATH_OR_URL>
```

The script will:
1. Auto-read Pi auth key from `~/.pi/agent/auth.json`
2. Auto-detect Pi-enabled vision models from `~/.pi/agent/settings.json`
3. Prefer free vision models already enabled in Pi, otherwise fall back to any free vision model
4. All models are **free** — zero cost

## Usage

### Describe an image

```bash
./vision.py /path/to/screenshot.png
```

### Ask a specific question

```bash
./vision.py /path/to/code.png \
  --prompt "What does this code do? Be specific."
```

### Analyze from URL

```bash
./vision.py https://example.com/diagram.png
```

### Use a specific model (override auto-detection)

```bash
./vision.py image.png \
  --model google/gemma-4-31b-it:free
```

### Show configuration

```bash
./vision.py --config
```

### List available free vision models

```bash
./vision.py --list-models
```

## Image Sources Supported

1. **Local files**: `/tmp/screenshot.png`, `./photo.jpg`
2. **URLs**: `https://example.com/image.png`
3. **Data URIs**: `data:image/png;base64,iVBOR...`

## Model Selection Logic (automatic)

1. Reads Pi's `enabledModels` in `~/.pi/agent/settings.json`
2. Cross-references with free vision models fetched from OpenRouter API
3. Uses the first Pi-enabled vision model found, sorted by context size
4. Falls back to the best free vision model if none are Pi-enabled
5. Automatically retries with the next model if one fails

## No Setup Required

- **No pip install** needed (Python stdlib only)
- **No API key export** needed (reads from `~/.pi/agent/auth.json`)
- **No cost** (always uses free models)

## Installation via Pi Package Manager

This skill is a Pi package. Install it on any device with Pi installed:

```bash
pi install git:github.com/Chillizu/pi-vision-skill
```

After install, Pi will auto-discover the skill on next startup.

### Manual Installation (without pi install)

```bash
git clone git@github.com:Chillizu/pi-vision-skill.git ~/.agents/skills/pi-vision-skill
```

Pi scans `~/.agents/skills/` automatically.
