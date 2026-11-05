# MetaFlora News — Newsroom runbook

This repo is news.metaflora.xyz. The site is static: `content/articles/*.json` is the source of truth, `newsroom/build.py` renders everything into `docs/`, and GitHub Pages serves `docs/` on the custom domain.

The AI newsroom runs twice a day: the **morning edition** (`am`, ~06:00 EET) and the **evening edition** (`pm`, ~18:00 EET). Publishing is fully automatic. Greg approved automatic publishing for this site.

## One run, step by step

1. **Pull** the latest `main`.
2. **Check what's already covered.** Read the headlines of the last ~30 files in `content/articles/` (newest by filename). Do not repeat a story unless there is a real new development; then write it as a new story that leads with what changed.
3. **Report.** Search the last 12–24 hours of cannabis news, with several searches sent together:
   - US federal: DEA, rescheduling, registration, hemp/total-THC, banking, Congress
   - US states: licensing windows, rule changes, ballot measures, enforcement, market data
   - Europe: Germany, Romania, UK, Czechia, Switzerland, Netherlands, EU-level
   - Global companies: M&A, earnings, listings, bankruptcies (Canada, US MSOs, EU-GMP producers)
   - Science and medicine: trials, reviews, public-health data
   - Tech: cannabis + AI, blockchain, track-and-trace, payments (only real news)
   Prefer original reporting: Marijuana Moment, MJBizDaily, Cannabis Business Times, Marijuana Herald, Reuters, Business of Cannabis, regulators' own releases. Open (fetch) the key articles; don't write from snippets alone.
4. **Write 6–9 stories** for the edition. Rank 1 is the lead: the story with the most consequence for operators and investors.
5. **Save one JSON file per story** at `content/articles/YYYY-MM-DD-<id>.json` (schema below).
6. **Validate:** `python3 newsroom/build.py --no-media`. It checks every file and fails loudly on a bad one. Fix and re-run until it passes.
7. **Commit and push** only `content/articles/` to `main` with a message like `Morning edition 2026-11-07: <lead headline>`. (`docs/` is build output and is not committed.)
8. **GitHub Actions takes over** (`.github/workflows/publish.yml`): generates the AI banners, builds the site, social cards and video reel, deploys to news.metaflora.xyz, then posts the top 3 stories to X.
9. **Report** in two lines: edition, story count, lead headline. If research, build or push fails, push nothing and say what failed.

## Writing rules (non-negotiable)

- **Own words only.** Every headline, dek and paragraph is MetaFlora's own writing. No copied sentences, no lightly reworded sentences, no mirroring an article's structure.
- **Quotes:** at most one short quote per source, under 15 words, and only when the exact words matter.
- **Facts only from sources you actually opened.** Never invent figures, names, dates or URLs. If unsure, leave it out.
- **Link every source** you drew on, at least one per story.
- **Tone:** sharp, plain, useful to operators and investors. No hype, no puns in headlines, no advice ("buy", "you should").
- **No photos of real people**, no other outlets' images or logos.

## Article schema

```json
{
  "id": "dea-registration",                       // url slug: lowercase, hyphens, unique forever
  "edition": "2026-11-07-am",                     // YYYY-MM-DD-am | YYYY-MM-DD-pm
  "rank": 1,                                      // 1 = lead
  "published": "2026-11-07T06:02:00+02:00",       // ISO, Europe/Bucharest offset
  "cat": "Federal",                               // Policy | Federal | Hemp | Markets | Europe | States | Science | Tech
  "headline": "…",                                // under ~90 characters
  "dek": "…",                                     // one sentence
  "body": ["paragraph", "paragraph", "paragraph"],// 2–4 short paragraphs
  "sources": [{"name": "Marijuana Moment", "url": "https://…"}],
  "visual": {
    "motif": "seal",
    "big": "900+",
    "label": "medical dispensaries federally registered"
  },
  "image_prompt": "…",                            // scene for the AI banner (see below)
  "image_alt": "…",                               // short description of that image for screen readers
  "x_post": "…"                                   // ranks 1–3: the post for X, ≤220 chars, no link (added automatically)
}
```

### The cover graphic (`visual`)

Every story's cover image, social card and reel shot are generated from `visual`.

| motif | use for | extra fields |
|---|---|---|
| `ballot` | elections, votes, ballot measures | – |
| `seal` | federal agencies, registrations, approvals | `word` (e.g. "DEA"), `sub` (e.g. "REGISTERED") |
| `calendar` | deadlines, effective dates | `mon` ("NOV"), `day` ("12") |
| `merge` | M&A, partnerships | `a`, `b`: 2–4 letter tickers or short names |
| `gavel` | courts, rulings, enforcement | – |
| `pins` | state/regional roundups, licensing, store counts | – |
| `molecule` | science, medicine, research | – |
| `chart` | earnings, prices, sales | `vals`: 5–9 numbers 0–1 tracing the trend |
| `leaf` | anything else | – |

- `big`: the one striking figure from the story, ≤7 characters ("C$561M", "-27%", "6 days", "65K"). It must be a fact from the sources.
- `label`: under 50 characters, explains the figure in plain words.
- Vary motifs across an edition where the stories allow.

## AI banner images (`image_prompt`)

On every push, GitHub Actions sends each new story's `image_prompt` to the image model (OpenAI `gpt-image-1` by default) with MetaFlora's fixed art direction: dark #131313 ground, lime and violet light, cinematic editorial photo, no text. The result is saved to `content/images/<id>.jpg` and becomes the story's banner, social card and reel shot. If generation fails or no key is set, the designed cover is used.

Write the scene, not the style (the style is added automatically):
- One concrete, visual scene that a reader connects to the story in a second: objects, places, materials, light. 1–2 sentences.
- Never ask for text, numbers, logos, flags, brand names or signage.
- Never depict real, identifiable people. People only as anonymous hands, silhouettes or from behind.
- No minors, no consumption close-ups, no weapons, nothing graphic.
- Vary scenes across the edition (lab, greenhouse, storefront, courtroom, landscape, product still life).

## Posting to X

After each deploy the publish workflow waits for each page to go live and then posts the edition's top 3 stories (by rank) to @MetaFloraLabs, each with a link to its article so X shows the cover card.

Write an `x_post` for ranks 1–3: a sharp, factual hook in MetaFlora's voice, ≤220 characters, no link and no hashtags (the script adds the link and #cannabis). No hype, no advice, no claims beyond the article. If `x_post` is missing the script falls back to headline + dek.

## Local preview

```
python3 newsroom/build.py            # full build with media
python3 newsroom/build.py --no-media # HTML only, fast
cd docs && python3 -m http.server 8000
```

Requirements: Python 3.10+, Pillow, `rsvg-convert` (librsvg), `ffmpeg`.
