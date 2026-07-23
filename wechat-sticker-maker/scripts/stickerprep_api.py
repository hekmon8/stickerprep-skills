#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE_URL = "https://stickerprep.com"


def api(base, key, method, path, payload=None, body=None, content_type=None, timeout=120):
    if payload is not None:
        body = json.dumps(payload).encode()
        content_type = "application/json"
    headers = {
        "Authorization": f"Bearer {key}",
        "User-Agent": "StickerPrep-Skill/1.0",
        "Accept": "application/json, text/event-stream, application/zip",
    }
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(f"{base.rstrip('/')}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return raw, response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        message = {
            400: "The request was rejected. Check the supplied files and options.",
            401: "The API key is missing or invalid.",
            403: "The API key is not allowed to perform this action.",
            404: "The requested StickerPrep resource was not found.",
            429: "Too many requests. Wait before retrying.",
        }.get(error.code, "StickerPrep is temporarily unavailable.")
        raise RuntimeError(message) from None


def json_api(base, key, method, path, payload=None):
    raw, _ = api(base, key, method, path, payload=payload)
    result = json.loads(raw)
    if result.get("code") != 0:
        raise RuntimeError(result.get("message") or "StickerPrep request failed")
    return result.get("data")


def multipart(paths):
    boundary = f"----stickerprep-{uuid.uuid4().hex}"
    chunks = []
    for path in paths:
        file_path = pathlib.Path(path)
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode(),
            f"Content-Type: {mimetypes.guess_type(file_path.name)[0] or 'application/octet-stream'}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def uploaded_character(raw):
    character = None
    for block in raw.decode("utf-8", "replace").split("\n\n"):
        event = ""
        data = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
        if event == "error":
            raise RuntimeError(json.loads(data).get("message", "Character upload failed"))
        if event == "complete" and data:
            value = json.loads(data)
            if isinstance(value, dict) and value.get("id"):
                character = value
    if not character:
        raise RuntimeError("StickerPrep did not return a completed character")
    return character


def main():
    parser = argparse.ArgumentParser(description="Generate a WeChat sticker pack with StickerPrep")
    parser.add_argument("--image", action="append", required=True, help="Reference image; repeat up to four times")
    parser.add_argument("--theme", required=True)
    parser.add_argument("--type", choices=("static", "animated"), default="static")
    parser.add_argument("--count", type=int, choices=(8, 16, 24), default=8)
    parser.add_argument("--output", default="submission-package.zip")
    parser.add_argument("--confirm-spend", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--timeout-minutes", type=int, default=60)
    args = parser.parse_args()

    if len(args.image) > 4:
        parser.error("at most four --image values are supported")
    key = os.environ.get("STICKERPREP_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set STICKERPREP_API_KEY locally. Create one at https://stickerprep.com/settings/apikeys")
    for image in args.image:
        if not pathlib.Path(image).is_file():
            parser.error(f"image not found: {image}")

    credits = json_api(BASE_URL, key, "GET", f"/api/credits?summary=1&packType={args.type}&stickerCount={args.count}")
    cost = credits.get("estimatedCredits")
    if not isinstance(cost, int):
        raise RuntimeError("StickerPrep did not return a generation quote")
    plan = {"estimated_credits": cost, "available_credits": credits.get("balance", 0), "requires_confirmation": not args.confirm_spend}
    if not args.confirm_spend:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if credits.get("balance", 0) < cost:
        raise SystemExit(f"Insufficient credits: need about {cost}, have {credits.get('balance', 0)}. Visit https://stickerprep.com/pricing")

    body, content_type = multipart(args.image)
    raw, _ = api(BASE_URL, key, "POST", "/api/characters/upload", body=body, content_type=content_type, timeout=300)
    character = uploaded_character(raw)
    pack = json_api(BASE_URL, key, "POST", "/api/packs", {
        "theme": args.theme,
        "characterId": character["id"],
        "packType": args.type,
        "stickerCount": args.count,
    })
    json_api(BASE_URL, key, "POST", f"/api/packs/{pack['id']}/scenes")
    json_api(BASE_URL, key, "POST", f"/api/packs/{pack['id']}/generate")

    deadline = time.time() + args.timeout_minutes * 60
    while time.time() < deadline:
        detail = json_api(BASE_URL, key, "GET", f"/api/packs/{pack['id']}")
        if detail["status"] == "ready":
            break
        if detail["status"] in ("failed", "canceled"):
            raise RuntimeError(f"Pack generation ended with status {detail['status']}")
        time.sleep(args.poll_seconds)
    else:
        raise RuntimeError(f"Timed out waiting for pack {pack['id']}; it may still be generating")

    validation = json_api(BASE_URL, key, "POST", f"/api/packs/{pack['id']}/validate")
    if not validation.get("passed"):
        print(json.dumps({"pack_id": pack["id"], "validation": validation}, ensure_ascii=False, indent=2))
        raise RuntimeError("Generated pack did not pass validation; no ZIP was downloaded")
    package = json_api(BASE_URL, key, "POST", f"/api/packs/{pack['id']}/package")
    with urllib.request.urlopen(package["zipPackUrl"], timeout=120) as response:
        pathlib.Path(args.output).write_bytes(response.read())
    rules = json_api(BASE_URL, key, "GET", "/api/rules/active")
    print(json.dumps({
        "pack_id": pack["id"],
        "output": str(pathlib.Path(args.output).resolve()),
        "rule_version": rules["version"],
        "validation_passed": True,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
