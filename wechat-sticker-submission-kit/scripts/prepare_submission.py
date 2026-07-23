#!/usr/bin/env python3
import argparse
import csv
import io
import json
import pathlib
import urllib.request
import zipfile

def fetch_rules(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.load(response)
    if payload.get("code") != 0:
        raise RuntimeError(payload.get("message") or "rules request failed")
    return payload["data"]


def save_png(image, size, max_kb, opaque=False):
    rgba = image.convert("RGBA")
    if opaque:
        canvas = ImageOps.fit(rgba.convert("RGB"), size, Image.Resampling.LANCZOS)
    else:
        image = ImageOps.contain(rgba, size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2), image)
    for colors in (None, 256, 128, 64):
        candidate = canvas if colors is None else canvas.quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
        out = io.BytesIO()
        candidate.save(out, "PNG", optimize=True)
        if out.tell() <= max_kb * 1024:
            return out.getvalue()
    raise RuntimeError(f"PNG cannot be reduced below {max_kb} KB")


def csv_bytes(rows):
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerows(rows)
    return text.getvalue().encode("utf-8-sig")


def validate_files(files, rules, count):
    errors = []
    warnings = []
    specs = {
        "main": rules["main"], "thumb": rules["thumb"], "banner": rules["banner"],
        "cover": rules["cover"], "icon": rules["icon"],
    }
    for name, data in files.items():
        category = next((key for key in specs if f"/{key}/" in name or name.endswith(f"/{key}.png")), None)
        if not category:
            continue
        image = Image.open(io.BytesIO(data))
        rule = specs[category]
        if list(image.size) != rule["size"]:
            errors.append({"file": name, "code": "dimensions"})
        if len(data) > rule["maxKb"] * 1024:
            errors.append({"file": name, "code": "fileSize"})
        if image.format.lower() not in rule["formats"]:
            errors.append({"file": name, "code": "format"})
        if category in ("main", "cover", "icon"):
            alpha = image.convert("RGBA").getchannel("A")
            if alpha.getextrema()[0] == 255:
                errors.append({"file": name, "code": "transparency"})
            bbox = alpha.getbbox()
            if bbox and (bbox[0] < 2 or bbox[1] < 2 or bbox[2] > image.width - 2 or bbox[3] > image.height - 2):
                warnings.append({"file": name, "code": "edgeMargin"})
    main_names = {pathlib.PurePosixPath(name).stem for name in files if "/main/" in name}
    thumb_names = {pathlib.PurePosixPath(name).stem for name in files if "/thumb/" in name}
    if main_names != thumb_names or len(main_names) != count:
        errors.append({"code": "pairing"})
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Prepare a static WeChat sticker submission ZIP")
    parser.add_argument("--source", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--output", default="submission-package.zip")
    parser.add_argument("--rules-url", default="https://stickerprep.com/api/rules/active")
    args = parser.parse_args()

    global Image, ImageOps
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise SystemExit("Pillow is required: python3 -m pip install Pillow")

    source = pathlib.Path(args.source)
    metadata = json.loads(pathlib.Path(args.metadata).read_text(encoding="utf-8"))
    if not metadata.get("pack_name") or len(metadata["pack_name"]) > 8:
        raise RuntimeError("metadata pack_name is required and must be <=8 characters")
    if not metadata.get("description") or len(metadata["description"]) > 80:
        raise RuntimeError("metadata description is required and must be <=80 characters")
    active = fetch_rules(args.rules_url)
    rules = active["rules"]
    images = sorted(path for path in source.glob("*.png") if path.stem.isdigit())
    count = len(images)
    if count not in rules["main"]["countOptions"]:
        raise RuntimeError(f"expected {rules['main']['countOptions']} main images, got {count}")
    expected = [f"{index:02d}" for index in range(1, count + 1)]
    if [path.stem for path in images] != expected:
        raise RuntimeError(f"main images must be consecutively named {expected[0]}.png through {expected[-1]}.png")
    labels = metadata.get("labels", [])
    if len(labels) != count or len(set(labels)) != count or any(not label or len(label) > 4 for label in labels):
        raise RuntimeError("metadata labels must be unique, non-empty, <=4 characters, and match the sticker count")

    files = {}
    first = None
    for path in images:
        image = Image.open(path)
        first = first or image.copy()
        main = save_png(image, tuple(rules["main"]["size"]), rules["main"]["maxKb"])
        thumb = save_png(image, tuple(rules["thumb"]["size"]), rules["thumb"]["maxKb"])
        files[f"wechat-submission/main/{path.stem}.png"] = main
        files[f"wechat-submission/thumb/{path.stem}.png"] = thumb

    package_dir = source / "package"
    derived = {
        "cover": (first, rules["cover"], False),
        "icon": (first, rules["icon"], False),
    }
    banner_path = package_dir / "banner.png"
    if not banner_path.is_file():
        raise RuntimeError("package/banner.png is required; generate a text-free wide scene first")
    derived["banner"] = (Image.open(banner_path), rules["banner"], True)
    for name in ("cover", "icon"):
        custom = package_dir / f"{name}.png"
        if custom.is_file():
            derived[name] = (Image.open(custom), rules[name], False)
    for name, (image, rule, opaque) in derived.items():
        files[f"wechat-submission/package/{name}.png"] = save_png(image, tuple(rule["size"]), rule["maxKb"], opaque)

    optional = {
        "appreciation_guide": ("guide.png", rules["appreciationGuide"]),
        "appreciation_thanks": ("thank_you.png", rules["appreciationThanks"]),
    }
    for source_name, (output_name, rule) in optional.items():
        path = package_dir / f"{source_name}.png"
        if path.is_file():
            files[f"wechat-submission/appreciation/{output_name}"] = save_png(Image.open(path), tuple(rule["size"]), rule["maxKb"], True)

    errors, warnings = validate_files(files, rules, count)
    if errors:
        raise RuntimeError(f"prepared files failed validation: {json.dumps(errors, ensure_ascii=False)}")

    manifest = {
        "pack_name": metadata.get("pack_name", ""),
        "pack_description": metadata.get("description", ""),
        "sticker_count": count,
        "type": "static",
        "uses_ai_generation": bool(metadata.get("uses_ai_generation")),
        "rule_version": active["version"],
    }
    files["wechat-submission/manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    files["wechat-submission/submission_copy.csv"] = csv_bytes([["index", "meaning"]] + [[f"{i:02d}", label] for i, label in enumerate(labels, 1)])
    files["optional-materials/ai/ai_generation_disclosure.md"] = (
        "# AI Generation Disclosure\n\nAI-assisted generation was used. Preserve source references and prompt history for review.\n"
        if manifest["uses_ai_generation"] else "# AI Generation Disclosure\n\nNo AI-assisted generation was declared.\n"
    ).encode()
    files["optional-materials/review/validation_report.json"] = json.dumps({
        "rule_version": active["version"],
        "passed": True,
        "errors": errors,
        "warnings": warnings,
        "sticker_count": count,
    }, ensure_ascii=False, indent=2).encode()
    files["optional-materials/rights/rights_evidence_checklist.md"] = (
        "# Rights evidence checklist\n\n"
        "Attach genuine authorship, IP, portrait, or brand authorization evidence when the submitted content requires it. "
        "This package does not create or assert rights on the creator's behalf.\n"
    ).encode()
    files["README.md"] = (
        f"# WeChat submission package\n\nAutomated checks passed against StickerPrep rule {active['version']} "
        f"with {len(warnings)} warning(s). Technical validation does not guarantee WeChat approval.\n"
    ).encode()

    output = pathlib.Path(args.output)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    print(json.dumps({
        "output": str(output.resolve()),
        "rule_version": active["version"],
        "sticker_count": count,
        "files": len(files),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
