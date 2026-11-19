# Pollinations Postcard

[![Made with pollinations.ai](https://raw.githubusercontent.com/pollinations/pollinations/main/packages/ui/src/brand/badge-made-with.svg)](https://pollinations.ai/?ref=badge)

An [Agent Skill](https://agentskills.io) that turns a one-line brief into a
four-panel illustrated postcard with a narrated line, built on the
[Pollinations](https://pollinations.ai) text, image and speech models.

```bash
python3 scripts/postcard.py "a rainy night in Jakarta" --out out/jakarta
open out/jakarta/postcard.html
```

```
out/jakarta/
  postcard.html   self-contained card, images and audio inlined
  panel-1.jpg     … the panels as files
  narration.mp3   only when signed in
  manifest.json   brief, prompts, captions, models, seeds
```

## How it works

1. **Plan** — `openai/gpt-5.4-nano` turns the brief into four image prompts,
   four short captions and one sentence of narration, JSON only. A parse
   failure falls back to local panels instead of failing the run.
2. **Draw** — each prompt goes to the Pollinations image endpoint with a fixed
   seed, so the same seed reproduces the same card.
3. **Speak** — the narration line goes to `/v1/audio/speech` as MP3.
4. **Assemble** — `postcard.html` inlines everything as base64, so the card
   survives being moved into an email, a chat or a folder.

## Install as a skill

Copy this directory into your agent's skills folder, or point the agent at
`SKILL.md`. Nothing else is needed: the script is Python standard library only
(3.9+), with no dependencies to install.

## Sign in (optional, no key to paste)

Images work anonymously through `image.pollinations.ai`. Planning and narration
need an account, so the skill signs in the Pollinations way:

```bash
python3 scripts/postcard.py --login   # prints a code, opens enter.pollinations.ai/device
python3 scripts/postcard.py --logout  # forget the stored token
```

Approve the code in the browser and the token is saved to
`~/.config/pollinations-postcard/token.json` (mode 600). Nothing is pasted into
the skill and no `sk_` key is needed. The script reuses a key already saved by
`polli auth login`, and still honours `POLLINATIONS_API_KEY` for CI. Lookup
order: postcard token, then polli credentials, then the environment variable.

Scopes requested: `generate profile`. Every call spends that account's pollen,
like any other Pollinations request. Overridable models: `POSTCARD_TEXT_MODEL`,
`POSTCARD_SPEECH_MODEL`, `POSTCARD_IMAGE_MODEL`.

## Example

`examples/jakarta-rain/` is a real run of the whole pipeline: `openai/gpt-5.4-nano`
wrote the four prompts, captions and the narration line, the image endpoint drew
the panels anonymously (so the script waited out the 45 s/IP limit), and
`openai/tts-1` spoke the line into `narration.mp3` with the polli sign-in already
on disk. `manifest.json` records the models, prompts and seeds.

## Files

| Path | What |
|---|---|
| `SKILL.md` | the skill definition an agent reads |
| `scripts/postcard.py` | the generator |
| `examples/jakarta-rain/` | a real run |

MIT.
