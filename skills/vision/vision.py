#!/usr/bin/env python3
"""
Vision API client for Pi — sends an image to a vision model and returns text.

Auto-detects Pi config for API key.
Agent selects the model (see SKILL.md).

Usage:
  python3 vision.py --model nvidia/nemotron-nano-12b-v2-vl:free image.png
  python3 vision.py --model openai/gpt-4o --prompt "What's in this?" https://...
"""

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


# ── Image Loading ──────────────────────────────────────────────────────────

def load_image(path: str) -> dict:
    """Load image from local file, URL, or data URI. Returns OpenAI-style content block."""
    # Data URI
    if path.startswith("data:image/"):
        match = re.match(r"data:(image/[^;]+);base64,(.+)", path)
        if not match:
            raise ValueError(f"Invalid data URI: {path[:80]}...")
        return {"type": "image_url", "image_url": {"url": f"data:{match.group(1)};base64,{match.group(2)}"}}

    # URL
    if path.startswith(("http://", "https://")):
        return {"type": "image_url", "image_url": {"url": path}}

    # Local file
    if os.path.isfile(path):
        mime_type, _ = mimetypes.guess_type(path)
        if not mime_type:
            mime_type = {".png": "image/png", ".jpg": "image/jpeg",
                         ".jpeg": "image/jpeg", ".gif": "image/gif",
                         ".webp": "image/webp", ".bmp": "image/bmp"}.get(
                Path(path).suffix.lower(), "image/png")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}

    raise FileNotFoundError(f"Image not found: {path}")


# ── Pi Config Reader ───────────────────────────────────────────────────────

def find_api_key(provided_key: str | None = None) -> str | None:
    """Find API key: arg > env var > Pi auth file."""
    if provided_key:
        return provided_key

    for var in ("VISION_API_KEY", "OPENROUTER_API_KEY"):
        val = os.environ.get(var)
        if val:
            return val

    auth_path = os.path.expanduser("~/.pi/agent/auth.json")
    try:
        with open(auth_path) as f:
            auth = json.load(f)
        for provider in ("openrouter", "deepseek", "kimi-coding"):
            key = auth.get(provider, {}).get("key", "")
            if key:
                return key
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    return None


# ── API Call ───────────────────────────────────────────────────────────────

def call_vision_api(
    image_data: dict,
    prompt: str,
    model: str,
    api_key: str,
    api_url: str,
    max_tokens: int = 1024,
) -> str:
    """Send image + prompt to a vision model. Returns text or exits on error."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in api_url:
        headers["HTTP-Referer"] = "https://github.com/pi-vision-skill"
        headers["X-Title"] = "Pi Vision Skill"

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": prompt}, image_data],
        }],
        "max_tokens": max_tokens,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[vision] HTTP {e.code} error from {model}:", file=sys.stderr)
        print(f"  {body[:500]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[vision] Network error: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[vision] Invalid JSON response: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract response text
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        print(f"[vision] Unexpected response format:", file=sys.stderr)
        print(f"  {json.dumps(result, indent=2)[:500]}", file=sys.stderr)
        sys.exit(1)

    # Validate content
    if content is None:
        print(f"[vision] Model returned null — it may not support vision.", file=sys.stderr)
        sys.exit(1)
    stripped = content.strip()
    if not stripped:
        print(f"[vision] Model returned empty response.", file=sys.stderr)
        sys.exit(1)
    if stripped.lower() in ("none", "null", "undefined"):
        print(f"[vision] Model returned '{stripped}' — it may not support vision.", file=sys.stderr)
        sys.exit(1)

    return content


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Send an image to a vision model and get a text description.",
    )
    parser.add_argument("image", help="Local image path, URL, or base64 data URI")
    parser.add_argument("-m", "--model", required=True,
                        help="Vision model ID (e.g. nvidia/nemotron-nano-12b-v2-vl:free)")
    parser.add_argument("-p", "--prompt",
                        default="Please describe this image in detail.",
                        help="Prompt or question about the image")
    parser.add_argument("--api-key", default=None,
                        help="Override API key (default: auto-detect from Pi config / env)")
    parser.add_argument("--api-url",
                        default="https://openrouter.ai/api/v1/chat/completions",
                        help="API endpoint URL (default: OpenRouter)")
    parser.add_argument("--max-tokens", type=int, default=1024,
                        help="Maximum tokens in response (default: 1024)")

    args = parser.parse_args()

    # Resolve API key: arg > env > Pi auth
    api_key = find_api_key(args.api_key)
    if not api_key:
        print("[vision] No API key found. Set VISION_API_KEY env var or configure Pi auth.json.",
              file=sys.stderr)
        sys.exit(1)

    # Load image
    try:
        image_data = load_image(args.image)
    except (FileNotFoundError, ValueError) as e:
        print(f"[vision] Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Call API
    result = call_vision_api(
        image_data=image_data,
        prompt=args.prompt,
        model=args.model,
        api_key=api_key,
        api_url=args.api_url,
        max_tokens=args.max_tokens,
    )
    print(result)


if __name__ == "__main__":
    main()
