#!/usr/bin/env python3
"""Turn a one-line brief into a four-panel postcard with a narrated line."""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

IMAGE_HOST = "https://image.pollinations.ai/prompt"
API_HOST = "https://gen.pollinations.ai"
DEFAULT_TEXT_MODEL = os.environ.get("POSTCARD_TEXT_MODEL", "openai/gpt-5.4-nano")
DEFAULT_SPEECH_MODEL = os.environ.get("POSTCARD_SPEECH_MODEL", "openai/tts-1")
IMAGE_MODEL = os.environ.get("POSTCARD_IMAGE_MODEL", "").strip()

# Used when no key is set, or when the model's plan cannot be parsed.
STYLES = [
    ("wide establishing shot, morning light", "the way in"),
    ("close-up detail, shallow depth of field", "what you noticed"),
    ("shot from the street, people passing", "the noise of it"),
    ("last light of the day, long shadows", "the way out"),
]


def api_key():
    return os.environ.get("POLLINATIONS_API_KEY", "").strip()


def retry_hint(detail):
    match = re.search(r"[Rr]etry after (\d+)s", detail)
    return int(match.group(1)) + 3 if match else None


def fetch(url, timeout=180, retries=7):
    """GET bytes, honouring the anonymous limit's own retry hint."""
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            last = f"HTTP {error.code}: {detail[:200]}"
            wait = retry_hint(detail)
            if attempt < retries and (wait is not None or error.code >= 500):
                pause = wait if wait is not None else 5 * (attempt + 1)
                if wait is not None:
                    print(f"  provider busy, waiting {pause}s")
                time.sleep(pause)
                continue
            raise SystemExit(f"request failed: {url}\n  {last}")
        except (urllib.error.URLError, TimeoutError) as error:
            last = error
            if attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
    raise SystemExit(f"request failed: {url}\n  {last}")


def fetch_json(url, payload, key, timeout=120):
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def image_url(prompt, seed, model=""):
    query = {"width": 1024, "height": 576, "nologo": "true", "seed": seed}
    if model:
        query["model"] = model
    return f"{IMAGE_HOST}/{urllib.parse.quote(prompt)}?{urllib.parse.urlencode(query)}"


def plan_locally(brief, panels):
    chosen = STYLES[:panels] + STYLES[: max(0, panels - len(STYLES))]
    return {
        "panels": [
            {"prompt": f"{brief}, {style}", "caption": caption}
            for style, caption in chosen
        ],
        "narration": f"A postcard from {brief}.",
    }


def plan_with_model(brief, panels, key):
    system = (
        "You plan a postcard. Reply with JSON only, no prose and no code fences: "
        '{"panels":[{"prompt":"<image prompt>","caption":"<five words max>"}],'
        '"narration":"<one spoken sentence>"}. '
        f"Return exactly {panels} panels. Each prompt is a self-contained visual "
        "scene: subject, setting, light, lens. Captions are lowercase and short. "
        "The narration is one sentence, under 200 characters, present tense."
    )
    raw = fetch_json(
        f"{API_HOST}/v1/chat/completions",
        {
            "model": DEFAULT_TEXT_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": brief},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.8,
        },
        key,
    )
    content = json.loads(raw)["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content[content.find("{") :]
    plan = json.loads(content)
    planned = [
        {"prompt": str(p["prompt"]), "caption": str(p["caption"]).lower()}
        for p in plan["panels"][:panels]
        if p.get("prompt")
    ]
    if len(planned) < panels:
        raise ValueError(f"only {len(planned)} usable panels")
    return {"panels": planned, "narration": str(plan["narration"])}


def narrate(text, voice, key):
    return fetch_json(
        f"{API_HOST}/v1/audio/speech",
        {
            "model": DEFAULT_SPEECH_MODEL,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        },
        key,
        timeout=180,
    )


def data_uri(path, mime):
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def render(brief, plan, image_paths, audio_path):
    figures = []
    for index, (panel, path) in enumerate(zip(plan["panels"], image_paths), start=1):
        figures.append(
            '<figure class="panel">'
            f'<img src="{data_uri(path, "image/jpeg")}" alt="{panel["caption"]}">'
            f'<figcaption><span>{index:02d}</span>{panel["caption"]}</figcaption>'
            "</figure>"
        )
    audio = ""
    if audio_path:
        audio = (
            '<audio controls preload="metadata" '
            f'src="{data_uri(audio_path, "audio/mpeg")}"></audio>'
        )
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        TEMPLATE.replace("__BRIEF__", brief)
        .replace("__PANELS__", "\n".join(figures))
        .replace("__AUDIO__", audio)
        .replace("__NARRATION__", plan["narration"])
        .replace("__STAMP__", stamp)
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Postcard — __BRIEF__</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 48px 24px; background: #14110f; color: #f3ece3;
    font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  }
  .card { max-width: 980px; margin: 0 auto; }
  header { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
  h1 { margin: 0; font-size: clamp(1.6rem, 4vw, 2.6rem); font-weight: 500; letter-spacing: -0.02em; }
  header span { color: #a89a89; font-size: 0.8rem; letter-spacing: 0.18em; text-transform: uppercase; }
  .rule { height: 1px; background: linear-gradient(90deg, #b4703f, transparent); margin: 20px 0 28px; }
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
  @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }
  .panel { margin: 0; background: #1d1916; border-radius: 10px; overflow: hidden; }
  .panel img { display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: cover; }
  figcaption { display: flex; gap: 12px; padding: 12px 14px; font-size: 0.95rem; color: #e6dccd; }
  figcaption span { color: #b4703f; font-variant-numeric: tabular-nums; }
  .voice { display: flex; align-items: center; gap: 18px; margin-top: 28px; flex-wrap: wrap; }
  .voice p { margin: 0; flex: 1; min-width: 260px; font-style: italic; color: #cdbfae; }
  audio { width: 260px; max-width: 100%; }
  footer { margin-top: 28px; color: #7f7264; font-size: 0.8rem; letter-spacing: 0.06em; }
</style>
</head>
<body>
<div class="card">
  <header><h1>__BRIEF__</h1><span>postcard</span></header>
  <div class="rule"></div>
  <div class="grid">
__PANELS__
  </div>
  <div class="voice">
    __AUDIO__
    <p>__NARRATION__</p>
  </div>
  <footer>made with pollinations.ai · __STAMP__</footer>
</div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief")
    parser.add_argument("--out", default="out/postcard")
    parser.add_argument("--panels", type=int, default=4)
    parser.add_argument("--voice", default="nova")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="redraw panels that already exist in the output directory",
    )
    args = parser.parse_args()

    if not 1 <= args.panels <= 8:
        raise SystemExit("--panels must be 1..8")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    key = api_key()

    if key:
        try:
            plan = plan_with_model(args.brief, args.panels, key)
            print(f"plan: {DEFAULT_TEXT_MODEL}")
        except Exception as error:  # noqa: BLE001 - any plan failure uses the fallback
            print(f"plan: falling back to local panels ({error})")
            plan = plan_locally(args.brief, args.panels)
    else:
        print("plan: local panels (no POLLINATIONS_API_KEY)")
        plan = plan_locally(args.brief, args.panels)

    image_paths = []
    for index, panel in enumerate(plan["panels"]):
        seed = args.seed + index
        target = out / f"panel-{index + 1}.jpg"
        if target.exists() and not args.force:
            print(f"panel {index + 1}: reusing {target.name}")
        else:
            target.write_bytes(
                fetch(image_url(panel["prompt"], seed, IMAGE_MODEL))
            )
            print(f"panel {index + 1}: seed {seed}")
        image_paths.append(target)

    audio_path = None
    if key and not args.no_audio:
        audio_path = out / "narration.mp3"
        audio_path.write_bytes(narrate(plan["narration"], args.voice, key))
        print(f"narration: {DEFAULT_SPEECH_MODEL} / {args.voice}")
    elif not key:
        print("narration: skipped (needs POLLINATIONS_API_KEY)")

    (out / "postcard.html").write_text(
        render(args.brief, plan, image_paths, audio_path), encoding="utf-8"
    )
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "brief": args.brief,
                "planned_by": DEFAULT_TEXT_MODEL if key else "local",
                "speech_model": DEFAULT_SPEECH_MODEL if audio_path else None,
                "image_model": IMAGE_MODEL or "endpoint default",
                "seed": args.seed,
                **plan,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"card: {out / 'postcard.html'}")


if __name__ == "__main__":
    sys.exit(main())
