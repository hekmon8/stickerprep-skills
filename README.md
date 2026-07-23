# StickerPrep Skills

Open-source AI workflows for creating, packaging, and submitting WeChat sticker sets.

- `wechat-sticker-maker` — generate a consistent set from reference images, with StickerPrep API fallback.
- `wechat-sticker-submission-kit` — prepare copy and a rule-checked submission ZIP.
- `wechat-sticker-submit` — upload the package through the WeChat Sticker Open Platform with Computer Use.

Live rules and machine-readable entry points:

- <https://stickerprep.com/rules.md>
- <https://stickerprep.com/api/rules/active>
- <https://stickerprep.com/llms.txt>

## Install for Codex

Clone this repository, then link the skill folders into your Codex skills directory:

```bash
git clone https://github.com/hekmon8/stickerprep-skills.git
mkdir -p ~/.codex/skills
ln -s "$(pwd)/stickerprep-skills/wechat-sticker-maker" ~/.codex/skills/wechat-sticker-maker
ln -s "$(pwd)/stickerprep-skills/wechat-sticker-submission-kit" ~/.codex/skills/wechat-sticker-submission-kit
ln -s "$(pwd)/stickerprep-skills/wechat-sticker-submit" ~/.codex/skills/wechat-sticker-submit
```

API generation uses credits and requires `STICKERPREP_API_KEY`. Built-in Codex image generation remains the default path and needs no StickerPrep key.
