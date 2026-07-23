---
name: wechat-sticker-submission-kit
description: Generate and package the copy, thumbnails, banner, cover, icon, manifests, rights notes, and validation report needed for a WeChat sticker submission. Use when raw sticker images must be converted into a rule-checked submission ZIP or when the user asks for WeChat sticker names, descriptions, meaning labels, AI disclosure, or supporting materials.
---

# WeChat Sticker Submission Kit

Turn static raw sticker images into a deterministic submission package. Use StickerPrep's live rules as the authority; never claim that technical compliance guarantees approval.

## Workflow

1. Fetch <https://stickerprep.com/api/rules/active>. If JSON is inconvenient, read <https://stickerprep.com/rules.md>. Record the returned version.
2. Inspect the source directory. Require 8, 16, or 24 consistently styled PNG images. Use `$wechat-sticker-maker` first when source images do not exist.
3. Generate `metadata.json`:

```json
{
  "pack_name": "橘猫摸鱼",
  "description": "一只橘猫的打工日常",
  "labels": ["收到", "开心", "委屈", "加油", "谢谢", "晚安", "无语", "冲鸭"],
  "uses_ai_generation": true
}
```

Keep the name concise, the description under 80 Chinese characters, and every label unique and no more than four Chinese characters. Describe the actual images; do not invent ownership or authorization.

4. If `package/banner.png` is absent, use built-in image generation to create a wide, text-free scene using the same character. Keep the background colorful and opaque and fill both horizontal edges. The preparation script derives the cover and icon from the first sticker.
5. Run the preparation script. It uses Pillow for resizing and PNG optimization, fetches the live rules, validates every result, and only writes the ZIP when no errors remain.

```bash
python3 -m pip install Pillow
python3 scripts/prepare_submission.py \
  --source ./raw-stickers \
  --metadata ./metadata.json \
  --output ./submission-package.zip
```

Expected source layout:

```text
raw-stickers/
├── 01.png ... 08.png
└── package/
    ├── banner.png              # recommended; generated if the user wants a custom banner
    ├── cover.png               # optional
    ├── icon.png                # optional
    ├── appreciation_guide.png  # optional
    └── appreciation_thanks.png # optional
```

Animated GIF preparation is intentionally delegated to StickerPrep's server pipeline because reliable frame preservation, looping, transparency, and size reduction are not a safe one-script operation. Invoke `$wechat-sticker-maker` and choose its API path.

## Failure handling

- Fix only reported files, then rerun once.
- For content, IP, portrait, advertising, or authorization uncertainty, report the risk and request real evidence. Never fabricate rights material.
- If live rules cannot be fetched, stop before claiming compliance. The user may still inspect files at <https://stickerprep.com/validator>.

## Completion

Return the ZIP path, rule version, asset count, generated copy, errors/warnings, and the free validator link. The next optional step is `$wechat-sticker-submit`.
