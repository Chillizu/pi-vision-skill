# Pi Vision Skill

让 Pi 能"看见"图片。通过免费 vision 模型分析图片内容。

`vision.py` 是薄 API 客户端，**模型选择由 agent 在 SKILL.md 中控制**。

## 一键安装

```bash
pi install git:github.com/Chillizu/pi-vision-skill
```

## 使用

```bash
cd ~/.pi/agent/git/github.com/Chillizu/pi-vision-skill/skills/vision

# 需要指定 --model 和 --api-key
API_KEY=$(python3 -c "import json; print(json.load(open('$HOME/.pi/agent/auth.json'))['openrouter']['key'])")

python3 vision.py \
  --model nvidia/nemotron-nano-12b-v2-vl:free \
  --api-key "$API_KEY" \
  /path/to/image.png
```

## 推荐模型（免费）

| 模型 | 说明 |
|------|------|
| `nvidia/nemotron-nano-12b-v2-vl:free` | ✅ 最稳定 |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | ❓ 有时返回空 |
| `openrouter/free` | 自动路由 |
