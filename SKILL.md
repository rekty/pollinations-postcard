---
name: pollinations-postcard
description: >
  Turns a one-line brief into a four-panel illustrated postcard with a
  narrated line, using the Pollinations image, text and speech models. Use when
  someone wants a visual keepsake from a place, a memory, a mood or a trip, or
  asks for a postcard, a small zine, a mood board with captions, or images with
  a spoken voice-over. Output is one self-contained HTML card plus the PNG and
  MP3 files it embeds.
license: MIT
---

# Pollinations Postcard

One brief in, one postcard out: four captioned panels and a spoken line,
rendered as a single HTML file you can open, send or screenshot.

## When to use

- "Make me a postcard from Lisbon", "turn this memory into four images",
  "a small zine about the night market", "images with a voice-over".
- Any request where a few images plus one short line of narration is a better
  answer than a paragraph of text.

## Run it

```bash
python3 scripts/postcard.py "a rainy night in Jakarta" --out out/jakarta
```

Options:

| Flag | Meaning |
|---|---|
| `--login` | Sign in with Pollinations in the browser (device code), then exit. |
| `--logout` | Forget the token saved by `--login`. |
| `--out DIR` | Output directory, created if missing. Default `out/postcard`. |
| `--panels N` | Number of panels. Default 4. |
| `--voice NAME` | Speech voice, default `nova`. |
| `--seed N` | First image seed; later panels use `N+1`, `N+2`, … |
| `--no-audio` | Skip narration even when signed in. |

## What it produces

```
out/jakarta/
  postcard.html      self-contained card: images and audio are inlined
  panel-1.jpg …      the panels as files
  narration.mp3      only when a key was available
  manifest.json      brief, prompts, captions, models, seeds
```

## Requirements

- Python 3.9+, standard library only. No install step.
- **Sign-in is optional and never asks for a key.** Run
  `python3 scripts/postcard.py --login` once: the script prints a short code,
  opens `enter.pollinations.ai/device`, you approve it there, and the token is
  stored in `~/.config/pollinations-postcard/token.json` (mode 600). A key
  already saved by `polli auth login` is reused as-is, and
  `POLLINATIONS_API_KEY` still works for CI. Nothing is pasted into the skill.
- Images work signed out too, through `image.pollinations.ai`, at one image
  every 45 seconds per IP. The script reads the limit's own retry hint and
  waits, so a signed-out four-panel card takes about three minutes.

Signed out, the skill still runs: it plans the four panels locally from style
suffixes, generates the images anonymously, skips narration and says so in the
output. That fallback exists so the skill is useful before an account is set
up, not to pretend the model calls happened.

Sign-in scopes are `generate profile`: enough to plan, narrate and read the
account name, and nothing that can create or rotate API keys.

## How it works

1. **Plan.** A text model (`openai/gpt-5.4-nano` by default) turns the brief
   into `{"panels":[{"prompt","caption"}],"narration"}`, JSON only. Any parse
   failure falls back to the local plan instead of failing the run.
2. **Draw.** Each panel prompt goes to the image endpoint with a fixed seed, so
   a rerun with the same seed reproduces the same card.
3. **Speak.** The narration line goes to `/v1/audio/speech` as MP3.
4. **Assemble.** `postcard.html` inlines every image and the audio as base64,
   so the card survives being moved into an email, a chat or a folder.

## Notes

- Image models: the anonymous endpoint serves its own default. Set a key and
  pass `POSTCARD_IMAGE_MODEL` to pick any image model from `/v1/models`.
- Text and speech models are overridable with `POSTCARD_TEXT_MODEL` and
  `POSTCARD_SPEECH_MODEL`.
- Billing: images and speech spend the account's pollen, like any other call.
  A four-panel card is a handful of calls, so run it in a loop deliberately.
