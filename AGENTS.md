# Agent Instructions — Agentic Reels Studio

You are operating inside **Agentic Reels Studio** (`SadiTLM/agentic-reels-studio`), a modular system for discovering trends, ideating, reviewing via the Elephant-Goldfish pattern, producing 9:16 Reels and carousels, humanizing copy, and publishing to Instagram via Meta Graph API.

## Directory Contract

- `skills/` — Installed agent skills (read the matching `SKILL.md` before executing a stage).
- `brand/voice.md` — Brand voice, positioning, banned AI phrasing, and CTA rules.
- `brand/projects.json` — Real projects and metrics showcased in Reels and on the landing page (`site/`).
- `pipeline/01_trends/` — Grounded trend research (`last30days`) and viral swipe logs (`ig-viral`).
- `pipeline/02_ideas/` — Candidate content ideas (`<id>.json`, `<id>.md`) with scored hooks (`hookscore.py`) and Goldfish review records.
- `pipeline/03_approved/` — Human-approved ideas cleared for rendering.
- `pipeline/04_production/` — Rendered 9:16 MP4, Cover JPG, safe-zone check (`reel.py zones`), review sheets (`sheet.jpg`, `cuts.jpg`), linted caption, and feed preview (`preview.html`).
- `pipeline/05_ready_to_post/` — Verified post bundles ready for `scripts/ig_publish.py` or manual upload.
- `pipeline/06_published/` — Archive of published posts (`posts.json`) for `ig-audit`.
- `remotion-studio/` — Local Remotion renderer (`node render.mjs`).
- `site/` — Public landing page promoting SadiTLM's agentic automation engineering.

## Mandatory Guardrails

1. **Zero Invented Claims**: Never fabricate client results, metrics, or case studies. Only cite real metrics from `brand/projects.json`, verified benchmarks, or observed outputs.
2. **Elephant-Goldfish Review Before Approval**: Every idea in `pipeline/02_ideas/` should be challenged by an independent zero-context Goldfish reviewer before moving to `pipeline/03_approved/`.
3. **Human Approval Gate**: Never auto-approve (`studio.py approve`) or auto-publish (`ig_publish.py`) without explicit user confirmation on the generated preview/sheet and caption.
4. **Media Validation**: Every rendered MP4 or image must pass `skills/instagram-skill/scripts/ig_check.py` and safe-zone verification before entering `pipeline/05_ready_to_post/`.
5. **Copy Hygiene**: Every caption must pass `skills/ig-caption/caption.py` (check 125-char fold + max 5 hashtags) and `skills/ig-human/detect.py`.
