#!/usr/bin/env node
/**
 * Vision API client for Pi — sends an image to a vision model and returns text.
 *
 * Usage:
 *   node vision.mjs --model x/img:free image.png
 *   node vision.mjs --model x/img:free --prompt "Describe" https://...
 */

import { readFileSync, existsSync } from "fs";
import { homedir } from "os";
import { join, extname } from "path";

// ── Config ────────────────────────────────────────────────────────────────

const DEFAULTS = {
  prompt: "Please describe this image in detail.",
  apiUrl: "https://openrouter.ai/api/v1/chat/completions",
  timeout: 120_000,
};

// ── CLI parser (minimal, no deps) ─────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { model: null, prompt: DEFAULTS.prompt, apiKey: null, apiUrl: DEFAULTS.apiUrl, image: null };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "-m": case "--model": opts.model = args[++i]; break;
      case "-p": case "--prompt": opts.prompt = args[++i]; break;
      case "--api-key": opts.apiKey = args[++i]; break;
      case "--api-url": opts.apiUrl = args[++i]; break;
      default:
        if (!opts.image) opts.image = args[i];
    }
  }

  if (!opts.model) { console.error("[vision] --model is required"); process.exit(1); }
  if (!opts.image) { console.error("[vision] Missing image argument"); process.exit(1); }

  return opts;
}

// ── API key resolution ────────────────────────────────────────────────────

function resolveApiKey(provided) {
  if (provided) return provided;
  if (process.env.VISION_API_KEY) return process.env.VISION_API_KEY;
  if (process.env.OPENROUTER_API_KEY) return process.env.OPENROUTER_API_KEY;

  try {
    const auth = JSON.parse(readFileSync(join(homedir(), ".pi/agent/auth.json"), "utf-8"));
    for (const p of ["openrouter", "deepseek", "kimi-coding"]) {
      if (auth[p]?.key) return auth[p].key;
    }
  } catch { /* ignore */ }

  return null;
}

// ── Image loading ─────────────────────────────────────────────────────────

function loadImage(path) {
  // Data URI
  if (path.startsWith("data:image/")) {
    return { type: "image_url", image_url: { url: path } };
  }

  // URL
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return { type: "image_url", image_url: { url: path } };
  }

  // Local file
  if (!existsSync(path)) throw new Error(`Image not found: ${path}`);

  const mimeMap = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp" };
  const mime = mimeMap[extname(path).toLowerCase()] || "image/png";
  const b64 = readFileSync(path).toString("base64");

  return { type: "image_url", image_url: { url: `data:${mime};base64,${b64}` } };
}

// ── API call ──────────────────────────────────────────────────────────────

async function callVision(imageData, prompt, model, apiKey, apiUrl) {
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${apiKey}`,
  };
  if (apiUrl.includes("openrouter")) {
    headers["HTTP-Referer"] = "https://github.com/pi-vision-skill";
    headers["X-Title"] = "Pi Vision Skill";
  }

  const body = JSON.stringify({
    model,
    messages: [{
      role: "user",
      content: [{ type: "text", text: prompt }, imageData],
    }],
    max_tokens: 1024,
  });

  const resp = await fetch(apiUrl, { method: "POST", headers, body, signal: AbortSignal.timeout(DEFAULTS.timeout) });

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    console.error(`[vision] HTTP ${resp.status} from ${model}:`, file => process.stderr);
    console.error(`  ${text.slice(0, 500)}`);
    process.exit(1);
  }

  const result = await resp.json();
  const content = result?.choices?.[0]?.message?.content;

  if (content == null) {
    console.error(`[vision] Model returned null — it may not support vision.`);
    process.exit(1);
  }
  const s = content.trim();
  if (!s || ["none", "null", "undefined"].includes(s.toLowerCase())) {
    console.error(`[vision] Model returned '${s}' — it may not support vision.`);
    process.exit(1);
  }

  return content;
}

// ── Main ──────────────────────────────────────────────────────────────────

async function main() {
  const opts = parseArgs();

  const apiKey = resolveApiKey(opts.apiKey);
  if (!apiKey) {
    console.error("[vision] No API key found. Set VISION_API_KEY env var or configure Pi auth.json.");
    process.exit(1);
  }

  let imageData;
  try {
    imageData = loadImage(opts.image);
  } catch (e) {
    console.error(`[vision] Error: ${e.message}`);
    process.exit(1);
  }

  const result = await callVision(imageData, opts.prompt, opts.model, apiKey, opts.apiUrl);
  console.log(result);
}

main().catch(e => { console.error(`[vision] ${e.message}`); process.exit(1); });
