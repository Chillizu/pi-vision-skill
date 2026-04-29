#!/usr/bin/env python3
"""
Vision Skill for Pi — Sends images to a vision-capable model and returns text.

Key features:
- Reads Pi's auth.json for API keys automatically (no env vars needed)
- Reads Pi's settings.json to find which models are enabled
- Queries OpenRouter for free vision-capable models
- Prioritizes: (1) Pi-enabled vision models → (2) any free vision model
- Supports local files, URLs, and base64 data URIs

Configuration (optional overrides via env vars):
  VISION_API_URL    — API endpoint (default: OpenRouter)
  VISION_MAX_TOKENS — Max tokens in response (default: 1024)
"""

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ── Pi Config Reader ───────────────────────────────────────────────────────

PI_DIR = Path.home() / ".pi" / "agent"
AUTH_FILE = PI_DIR / "auth.json"
SETTINGS_FILE = PI_DIR / "settings.json"

# Hardcoded list of free vision models as ultimate fallback
FALLBACK_FREE_VISION_MODELS = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "openrouter/free",
]

DEFAULT_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MAX_TOKENS = 1024


def read_pi_auth() -> dict:
    """Read Pi's auth.json to get API keys."""
    if AUTH_FILE.exists():
        try:
            return json.loads(AUTH_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def read_pi_settings() -> dict:
    """Read Pi's settings.json."""
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def get_api_key(auth: dict) -> str:
    """Get API key: env var first, then Pi auth (prefer OpenRouter)."""
    # Check env vars
    key = os.environ.get("VISION_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key

    # Check Pi auth — prefer openrouter, then deepseek, then kimi
    for provider in ("openrouter", "deepseek", "kimi-coding"):
        if provider in auth and "key" in auth[provider]:
            return auth[provider]["key"]

    return ""


def get_pi_enabled_models(settings: dict) -> list[str]:
    """Get the list of enabled models from Pi settings."""
    return settings.get("enabledModels", [])


def fetch_free_vision_models(api_key: str) -> list[dict]:
    """Query OpenRouter API for free models that support vision (text+image input)."""
    if not api_key:
        return []

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    free_vision = []
    for model in data.get("data", []):
        model_id = model.get("id", "")
        # Free model?
        if ":free" not in model_id:
            continue
        # Supports image input?
        modality = model.get("architecture", {}).get("modality", "")
        if "image" not in modality:
            continue
        # Has text output?
        if "->text" not in modality:
            continue

        free_vision.append({
            "id": model_id,
            "modality": modality,
            "context_length": model.get("context_length", 0),
            "name": model.get("name", model_id),
        })

    # Sort by context length desc (bigger = more capable generally)
    free_vision.sort(key=lambda m: m["context_length"], reverse=True)
    return free_vision


def select_vision_model(
    pi_enabled: list[str],
    free_models: list[dict],
    quiet: bool = False,
) -> str:
    """
    Select the best vision model:
    1. Pi-enabled models that are also free vision models (cross-reference)
    2. First available free vision model
    3. Hardcoded fallback
    """
    free_model_ids = {m["id"] for m in free_models}

    # Cross-reference Pi enabled models with free vision models
    for model_id in pi_enabled:
        if model_id in free_model_ids:
            if not quiet:
                print(f"[vision] Using Pi-enabled vision model: {model_id}", file=sys.stderr)
            return model_id
        if model_id.startswith("openrouter/"):
            stripped = model_id[len("openrouter/"):]
            if stripped in free_model_ids:
                if not quiet:
                    print(f"[vision] Using Pi-enabled vision model: {stripped}", file=sys.stderr)
                return stripped

    # Fallback: first free vision model from OpenRouter
    if free_models:
        model = free_models[0]["id"]
        if not quiet:
            print(f"[vision] No Pi-enabled vision model found. Using free: {model}", file=sys.stderr)
        return model

    # Ultimate fallback
    fallback = FALLBACK_FREE_VISION_MODELS[0]
    if not quiet:
        print(f"[vision] No free vision models available. Trying: {fallback}", file=sys.stderr)
    return fallback


def resolve_provider(model_id: str) -> str:
    """Determine which provider API URL to use based on model."""
    # OpenRouter models all go through OpenRouter
    # DeepSeek models go through DeepSeek
    # Kimi models go through Kimi (Moonshot)
    if model_id.startswith(("openrouter/", "google/", "nvidia/", "meta-llama/", 
                            "anthropic/", "openai/", "mistralai/", "qwen/", "baidu/")):
        return "openrouter"
    if model_id.startswith("deepseek/"):
        return "deepseek"
    if model_id.startswith("kimi-coding/") or model_id.startswith("moonshot/"):
        return "kimi-coding"
    return "openrouter"  # default


# ── Image Loading ──────────────────────────────────────────────────────────

def is_url(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def is_data_uri(path: str) -> bool:
    return path.startswith("data:image/")


def is_local_file(path: str) -> bool:
    return os.path.isfile(path)


def encode_image_file(image_path: str) -> tuple[str, str]:
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        ext = Path(image_path).suffix.lower()
        mime_map = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        }
        mime_type = mime_map.get(ext, "image/png")
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, mime_type


def load_image(path: str) -> dict:
    if is_data_uri(path):
        match = re.match(r"data:(image/[^;]+);base64,(.+)", path)
        if not match:
            raise ValueError(f"Invalid data URI: {path[:80]}...")
        mime_type, b64_data = match.group(1), match.group(2)
        return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}}

    if is_url(path):
        return {"type": "image_url", "image_url": {"url": path}}

    if is_local_file(path):
        b64_data, mime_type = encode_image_file(path)
        return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}}

    raise FileNotFoundError(f"Image not found: {path}")


# ── API Call ───────────────────────────────────────────────────────────────

class VisionAPIError(Exception):
    """Raised when the vision API call fails (retryable)."""
    pass


def call_vision_api(
    image_data: dict,
    prompt: str,
    api_key: str,
    api_url: str,
    model: str,
    max_tokens: int,
) -> str:
    """Call vision API. Raises VisionAPIError on failure (allows fallback)."""
    if not api_key:
        raise VisionAPIError("No API key found.")

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
            "content": [
                {"type": "text", "text": prompt},
                image_data,
            ],
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
        raise VisionAPIError(f"HTTP {e.code}: {body[:500]}")
    except urllib.error.URLError as e:
        raise VisionAPIError(f"Network error: {e.reason}")
    except json.JSONDecodeError as e:
        raise VisionAPIError(f"Invalid JSON response: {e}")

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise VisionAPIError(f"Unexpected response: {json.dumps(result, indent=2)[:500]}")


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Send an image to a free vision model and get text back.",
    )
    parser.add_argument(
        "image", nargs="?", default=None,
        help="Path to local image file, image URL, or base64 data URI",
    )
    parser.add_argument(
        "-p", "--prompt", default="Please describe this image in detail.",
        help="Prompt/question about the image",
    )
    parser.add_argument(
        "-m", "--model", default=None,
        help="Override the auto-detected vision model",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="Override the API key",
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="List detected free vision models and exit",
    )
    parser.add_argument(
        "--config", action="store_true",
        help="Show auto-detected Pi configuration and exit",
    )

    args = parser.parse_args()

    # Load Pi configuration
    auth = read_pi_auth()
    settings = read_pi_settings()
    api_key = args.api_key or get_api_key(auth)
    pi_enabled = get_pi_enabled_models(settings)
    free_models = fetch_free_vision_models(api_key)

    if args.config:
        print("=== Pi Configuration ===")
        print(f"Auth providers: {list(auth.keys())}")
        print(f"API key found: {'Yes' if api_key else 'No'}")
        print(f"Enabled models: {pi_enabled}")
        print(f"\n=== Free Vision Models (OpenRouter) ===")
        if free_models:
            for m in free_models:
                enabled = "✓ ENABLED" if m["id"] in pi_enabled else ""
                print(f"  {m['id']} | {m['modality']} | ctx={m['context_length']} {enabled}")
        else:
            print("  (could not fetch — API key may be needed)")
        sys.exit(0)

    if args.list_models:
        print("=== Free Vision Models on OpenRouter ===")
        if free_models:
            for m in free_models:
                enabled = " ✓ (enabled in Pi)" if (
                    m["id"] in pi_enabled or 
                    f"openrouter/{m['id']}" in pi_enabled
                ) else ""
                print(f"  {m['id']}{enabled}")
        else:
            print("  Could not fetch. Trying cached list:")
            fallback_ids = free_model_ids = set()
            for fv in FALLBACK_FREE_VISION_MODELS:
                print(f"  {fv}")
        print(f"\nCurrent auto-selected model: {select_vision_model(pi_enabled, free_models, quiet=True)}")
        sys.exit(0)

    if not args.image:
        parser.print_help()
        sys.exit(1)

    # Build candidate models list (for fallback)
    if args.model:
        candidates = [args.model]
    else:
        candidates = []
        # Pi-enabled vision models first
        free_model_ids = {m["id"] for m in free_models}
        for mid in pi_enabled:
            if mid in free_model_ids:
                candidates.append(mid)
            elif mid.startswith("openrouter/") and mid[len("openrouter/"):] in free_model_ids:
                candidates.append(mid[len("openrouter/"):])
        # Then remaining free vision models
        for m in free_models:
            if m["id"] not in candidates:
                candidates.append(m["id"])
        # Finally, hardcoded fallbacks
        for fb_id in FALLBACK_FREE_VISION_MODELS:
            if fb_id not in candidates:
                candidates.append(fb_id)

    # Determine API URL
    api_url = os.environ.get("VISION_API_URL", DEFAULT_API_URL)
    max_tokens = int(os.environ.get("VISION_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))

    # Load image
    try:
        image_data = load_image(args.image)
    except (FileNotFoundError, ValueError) as e:
        print(f"[vision] Error loading image: {e}", file=sys.stderr)
        sys.exit(1)

    # Try each model with fallback
    last_error = None
    for i, model in enumerate(candidates):
        if i > 0:
            print(f"[vision] Falling back to: {model}", file=sys.stderr)
        else:
            print(f"[vision] Using model: {model}", file=sys.stderr)
        try:
            result = call_vision_api(image_data, args.prompt, api_key, api_url, model, max_tokens)
            print(result)
            return
        except VisionAPIError as e:
            last_error = e
            print(f"[vision] Failed with {model}: {e}", file=sys.stderr)
            continue

    print(f"[vision] All models failed. Last error: {last_error}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
