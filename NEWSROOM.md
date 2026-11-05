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
4. **Write 6–9 stories** for the edition. Rank 1 is the lead: the story with the most consequence for operators and investors. Every story is **long-form** (see "Long-form standard"). Fetch the full source articles plus at least one extra source for context before writing.
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
  "published": "2026-11-07T06:00:00+02:00",       // the EDITION time, same for every story: 06:00 (am) or 18:00 (pm), Europe/Bucharest offset
  "cat": "Federal",                               // Policy | Federal | Hemp | Markets | Europe | States | Science | Tech
  "headline": "…",                                // under ~90 characters
  "dek": "…",                                     // one sentence
  "key_points": ["…", "…", "…"],                 // 3–4 one-sentence takeaways ("The short version")
  "body": ["paragraph", "## Subhead", "paragraph", "> Pull quote", "…"], // long-form, see below
  "sources": [{"name": "Marijuana Moment", "url": "https://…"}],
  "visual": {
    "motif": "seal",
    "big": "900+",
    "label": "medical dispensaries federally registered"
  },
  "banner": {                                     // the text on the banner image (house style)
    "title": "DEA Registers 900+ Dispensaries",   // 3–6 words, punchy, ≤ 34 characters
    "highlight": ["900+", "DISPENSARIES"],       // 1–2 words of the title in the violet→green gradient
    "sub": "First federal registrations, with strings attached", // ≤ 60 characters; names allowed
    "divider": "Federal desk",                    // short spaced-caps label under the sub line
    "points": [{"icon": "shield", "text": "7 states approved"}, {"icon": "handshake", "text": "Registered-only supply chain"}, {"icon": "coin", "text": "Tax relief ahead"}],
    "corner": ["FEDERAL", "MEDICAL", "ACCESS", "COMPLIANCE"] // optional: 4 single words, bottom-right
  },
  "watch": [{"date": "2026-11-12", "text": "…"}],  // dated upcoming events from the story (front page "What to watch")
  "image_prompt": "…",                            // scene for the AI photo (see below)
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

## Long-form standard

MetaFlora News runs long, useful stories, not briefs.

- **Length:** 700–1,200 words in `body` (ranks 1–3 aim for 1,000+). Never pad: depth comes from reporting, context and consequences, not repetition. If the sources can't support 700 words of facts, combine related developments into one story.
- **Structure:** an opening that states the news in two paragraphs, then 4–6 sections each starting with a `## Subhead` (plain, descriptive: "Who got in, and who is waiting", "The tax prize", "What to watch"). End with a "What to watch" section: dates, decisions and signals ahead.
- **One pull quote** (`> …`) per story: MetaFlora's own one-line insight, never a quote from a source.
- **Key points:** 3–4 one-sentence takeaways in `key_points`.
- **Ad breaks are automatic:** the site inserts a MetaFlora ad (or a paid partner ad) before every second subhead. Don't write ads into the story.
- **Every fact traceable** to a source you opened. Paraphrase. Attribute claims ("the DEA said", "according to AP").

## Banner text (`banner`)

The banner is the story's **X / social card and reel shot only** (never shown on the website): AI photo on the right, MetaFlora logo, "MetaFlora News" pill, a huge two-tone headline, a sub line, a divider and a three-point icon strip. On the website the same AI photo appears clean, with no text, captioned "Photo illustration: AI-generated".
- `title` is NOT the headline: 3–6 punchy words in title case. `highlight` = 1–2 words of it.
- `points`: three short facts (≤ 28 characters each) with icons from: shield, leaf, chart, gavel, flask, pin, ballot, coin, globe, doc, handshake, chip, megaphone, drop, cube.
- Names of real people may appear in `sub` (e.g. "Gov. Gavin Newsom signs AB 2250"); their likeness never appears in the image.

## AI banner images (`image_prompt`)

On every push, GitHub Actions sends each new story's `image_prompt` to the image model (OpenAI `gpt-image-1` by default) with a fixed documentary-photo art direction: shot like a photojournalist on 35mm, available light, muted grade with a faint green cast, subject off-centre, no text, no neon, no smoke, no CGI look. The photo is saved to `content/images/<id>.jpg`. The site shows it clean; `newsroom/banner.py` composes the loud social banner on top of it. Without a photo the site shows a typographic plate (the story's key figure).

Write a real, specific place or object, not a metaphor:
- Good: "A dispensary counter at closing time, sealed medical jars on the shelf behind, a hand turning the sign." "Long greenhouse rows at dawn in the Canadian prairie." "Ballot counting table, hands sorting envelopes under fluorescent light."
- Bad: glowing seals, holograms, neon leaves, epic skylines, anything "cinematic".
- Never request text, logos, flags or signage. Never depict real, identifiable people: hands, backs and out-of-focus figures only.
- No minors, no consumption close-ups, no weapons, nothing graphic. Vary scenes across the edition.

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
