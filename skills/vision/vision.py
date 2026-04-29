#!/usr/bin/env python3
"""
Vision API client for Pi — sends an image to a vision model and returns text.

Auto-detects Pi config for API key.
Has a default model with automatic fallback on failure.
Agent can override with --model.

Usage:
  python3 vision.py image.png
  python3 vision.py --model some/model:free image.png
  python3 vision.py --model some/model --api-key KEY image.png
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


# ── Default Model Priority ─────────────────────────────────────────────────
# Tried in order: if one fails (timeout, 429, null), the next is tried.
# These are free vision models on OpenRouter.
DEFAULT_MODELS = [
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "baidu/qianfan-ocr-fast:free",
]


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
    """Find API key in order: provided arg > env vars > Pi auth file."""
    if provided_key:
        return provided_key

    provided_key = os.environ.get("VISION_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if provided_key:
        return provided_key

    # Try Pi's auth.json
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
    timeout: int = 120,
) -> str:
    """Send image + prompt to a vision model. Returns the text response."""
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}", "detail": body[:500], "model": model}
    except urllib.error.URLError as e:
        return {"error": "network", "detail": str(e.reason), "model": model}
    except TimeoutError:
        return {"error": "timeout", "detail": "Request timed out", "model": model}
    except json.JSONDecodeError as e:
        return {"error": "bad_response", "detail": str(e), "model": model}

    # Extract response text
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return {"error": "unexpected_format", "detail": json.dumps(result, indent=2)[:500], "model": model}

    # Validate content
    if content is None:
        return {"error": "null_content", "detail": "Model returned null — may not support vision", "model": model}
    stripped = content.strip()
    if not stripped:
        return {"error": "empty_content", "detail": "Model returned empty response", "model": model}
    if stripped.lower() in ("none", "null", "undefined"):
        return {"error": "null_content", "detail": f"Model returned '{stripped}'", "model": model}

    return {"success": content, "model": model}


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Send an image to a vision model and get a text description.",
    )
    parser.add_argument("image", help="Local image path, URL, or base64 data URI")
    parser.add_argument("-m", "--model", default=None,
                        help="Vision model ID (default: auto-fallback through free models)")
    parser.add_argument("-p", "--prompt",
                        default="Please describe this image in detail.",
                        help="Prompt or question about the image")
    parser.add_argument("--api-key", default=None,
                        help="API key (default: auto-detect from Pi config / env)")
    parser.add_argument("--api-url",
                        default="https://openrouter.ai/api/v1/chat/completions",
                        help="API endpoint URL (default: OpenRouter)")
    parser.add_argument("--max-tokens", type=int, default=1024,
                        help="Maximum tokens in response (default: 1024)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Timeout per model attempt in seconds (default: 120)")

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

    # Determine which models to try
    models_to_try = [args.model] if args.model else DEFAULT_MODELS

    last_error = None
    for model in models_to_try:
        print(f"[vision] Trying {model} ...", file=sys.stderr)

        result = call_vision_api(
            image_data=image_data,
            prompt=args.prompt,
            model=model,
            api_key=api_key,
            api_url=args.api_url,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        )

        if "success" in result:
            print(result["success"])
            return  # success

        last_error = result
        err_type = result.get("error", "unknown")
        detail = result.get("detail", "")

        # Skip 400 with "location" — provider doesn't support the model
        if err_type == "HTTP 400" and "location" in detail.lower():
            print(f"[vision]  {model} — provider-side error, skipping", file=sys.stderr)
        # Skip 429 — rate limited
        elif err_type == "HTTP 429":
            print(f"[vision]  {model} — rate limited, skipping", file=sys.stderr)
        # Skip null/empty — not a vision model
        elif err_type in ("null_content", "empty_content"):
            print(f"[vision]  {model} — not a vision model, skipping", file=sys.stderr)
        # Timeout
        elif err_type == "timeout":
            print(f"[vision]  {model} — timed out, skipping", file=sys.stderr)
        # Other HTTP errors
        elif err_type.startswith("HTTP "):
            code = err_type.split()[1]
            print(f"[vision]  {model} — HTTP {code}, skipping", file=sys.stderr)
        # Network / unexpected
        else:
            print(f"[vision]  {model} — {err_type}, skipping", file=sys.stderr)

    # All models failed
    if last_error:
        last_model = last_error.get("model", "?")
        print(f"[vision] All models failed. Last ({last_model}): {last_error.get('error', '?')}",
              file=sys.stderr)
    else:
        print("[vision] No models available to try.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
