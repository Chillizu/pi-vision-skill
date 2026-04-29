# Pi Vision Skill

让 Pi 能"看见"图片。自动发送图片到免费 vision 模型，取回描述。

## 一键安装

```bash
pi install git:github.com/Chillizu/pi-vision-skill
```

安装后 Pi 会自动发现此 skill。遇到图片时使用它即可。

## 手动安装

```bash
git clone git@github.com:Chillizu/pi-vision-skill.git ~/.agents/skills/pi-vision-skill
```

## 使用

```bash
cd ~/.agents/skills/pi-vision-skill/skills/vision
python3 vision.py /path/to/image.png
```

## 要求

- Pi 已配置 OpenRouter API key（在 `~/.pi/agent/auth.json` 中）
- 可选：在 Pi settings 中添加 `openrouter/*:free` 免费 vision 模型
