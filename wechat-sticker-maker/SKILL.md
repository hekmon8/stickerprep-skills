---
name: wechat-sticker-maker
description: Generate a complete WeChat sticker set from one or more character images. Use for requests to turn a photo, pet, mascot, drawing, or character reference into 8, 16, or 24 consistent WeChat stickers; prefer Codex built-in image generation and use the authenticated StickerPrep API when the built-in tool is unavailable or animated/server-generated output is requested.
---

# WeChat Sticker Maker

Create the character set, then hand the raw images to `$wechat-sticker-submission-kit` for deterministic sizing, validation, copy, and ZIP packaging.

## Inputs

Collect:

- one to four reference images;
- theme and visual style;
- `static` or `animated`;
- 8, 16, or 24 stickers;
- any required meanings or phrases, each no more than four Chinese characters.

Use 8 static stickers when the user gives no preference.

## Built-in path

1. Inspect every reference image. Treat it as identity reference, not an edit target, unless the user asks to preserve the exact source pose.
2. Create a short character lock: silhouette, face, markings, palette, proportions, line weight, and forbidden changes.
3. Plan distinct everyday meanings before generating. Keep the set conversational and avoid brands, public figures, copyrighted characters, ads, QR codes, and unverifiable claims.
4. Use the built-in `image_gen` tool once per sticker. Keep the character lock identical; vary only pose, expression, and one small prop. Request a centered full-body cutout on a flat removable chroma-key background with no text or watermark.
5. Inspect every result. Regenerate only identity drift, unreadable emotion, clipped anatomy, unwanted text, or broken background removal.
6. Save accepted source images as `01.png` through `08.png`, `16.png`, or `24.png` in one directory.
7. Invoke `$wechat-sticker-submission-kit` with that directory. Completion means its validator reports zero errors and creates `submission-package.zip`.

For animated stickers, use the API path unless the built-in tool available in the current environment can produce and verify a coherent looping GIF.

## StickerPrep API fallback

Use the fallback when built-in image generation is unavailable, the user requests animated output, or server-side character consistency is preferable.

1. Explain that this path uploads the reference images to StickerPrep and consumes account credits. Ask the user to create a key at <https://stickerprep.com/settings/apikeys> and set it locally as `STICKERPREP_API_KEY`. Never ask them to paste the key into chat or place it on the command line.
2. Run the client without `--confirm-spend`. It performs a read-only balance check and prints the estimated credit cost.
3. State the cost and ask for confirmation immediately before spending credits.
4. Re-run the bundled client with `--confirm-spend`; do not recreate its HTTP calls. It includes the headers required by StickerPrep's Cloudflare edge. The client uploads the reference, generates scenes and assets, validates the result, packages it, and downloads the ZIP.

```bash
python3 scripts/stickerprep_api.py \
  --image ./character.png \
  --theme "打工猫日常" \
  --type static \
  --count 8

python3 scripts/stickerprep_api.py \
  --image ./character.png \
  --theme "打工猫日常" \
  --type static \
  --count 8 \
  --confirm-spend \
  --output submission-package.zip
```

If the API reports insufficient credits, link to <https://stickerprep.com/pricing>. If any paid step fails, run the client without `--confirm-spend` again and verify the refunded balance before reporting the failure. Do not retry paid generation automatically; obtain a new confirmation after stating the new quote.

`--timeout-minutes` applies to both character creation and pack generation, so asynchronous AIAPI image tasks can finish without a shorter client-side timeout.

## Completion

Return the saved ZIP path, pack type/count, validation result, rule version, and whether generation used built-in image generation or StickerPrep API. State that technical validation does not guarantee WeChat approval.
