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
- **Source mix** (checked by the build, `newsroom/sourcecheck.py`; it warns in the log and never blocks): every story links **at least one primary source** (the regulator, agency, court, legislature, Federal Register, SEC/SEDAR filing, company press release or investor page, or the journal/DOI/PubMed record); **no single outlet supplies more than 60%** of the sources; and when the headline names a **report, study, filing, ruling, bill or lawsuit, link that document itself**, not only the coverage of it. Fix any story the build flags before pushing when you can.
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
  "tags": ["DEA", "Rescheduling", "Florida"],     // 2–8 topic tags (see "SEO and topic tags")
  "image_prompt": "…",                            // scene for the AI photo (see below)
  "image_alt": "…",                               // short description of that image for screen readers
  "x_post": "…",                                  // ranks 1–3: the post for X, ≤220 chars, no link (added automatically)
  "breaking": false,                              // optional: true = breaking news, alerts go out at once to breaking-news subscribers
  "push": true,                                   // optional: false = no automatic web push alert for this story
  "draft": false                                  // optional: true = not published at all (and never alerted)
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

## SEO and topic tags

Every story is permanent: it keeps its dated URL forever and is never deleted or overwritten. Corrections go in a `corrections` note, and later developments are new stories that link back.

`tags` build evergreen topic hub pages (`/topic/<tag>/`), and those hubs compound in search over time. Rules:
- 2–8 tags per story: the specific companies, states/countries, regulators, laws and themes the story is actually about.
- **Reuse existing tags exactly.** Before tagging, list the tags already used in `content/articles/` and reuse their exact spelling and case ("DEA", not "Drug Enforcement Administration"; "Curaleaf", not "Curaleaf Holdings"). One entity = one tag forever.
- Proper names for entities ("Aurora Cannabis", "Illinois", "Section 280E"); short title-case themes for subjects ("Rescheduling", "M&A", "Licensing", "Hemp").
- Headlines say plainly who did what, using the names people search for. No puns or teasers.

The build publishes a sitemap index (pages, archive pages, a Google News sitemap for the last 48 hours, and every article ever published), per-section RSS feeds, NewsArticle and Breadcrumb schema on every story, a monthly archive, daily edition pages (`/YYYY/MM/DD/`, `/YYYY/MM/`, `/YYYY/`) and paginated section and topic pages (`/section/<s>/page/2/`, 30 stories a page).

### SEO rules for every edition (from the SEO board, 6 Nov 2026)
- **Company tags use the stock-page names** so stories link to `/stocks/<sym>/` automatically: Curaleaf, Green Thumb, Verano, Tilray, Canopy Growth, SNDL, Organigram, Aurora Cannabis, MSOS. `TAG_ALIASES` in `newsroom/templates.py` maps known variants; add a line there rather than inventing a new spelling.
- **Topic hubs index at 3 stories.** Hubs with fewer are `noindex, follow` and stay out of the sitemap, so tag the recurring entities (states, regulators, companies) consistently and the hubs graduate on their own.
- **Banner text keeps the story's tense and certainty.** Promises, plans and predictions stay "would", "plans to", "likely"; never shorten them into done deeds ("would sign" must not become "signed"). The banner and its points are what most people see on X.
- **Absolute dates in headlines and deks.** Write "12 November", never "next Thursday" or "tomorrow": stories stay up forever and are read days later.
- **Headline under 70 characters, dek 120–160.** Lead with the name people search ("Curaleaf", "Ohio", "DEA"), then what happened.
- **`published` is the real publish time** of the edition (the time you commit), not a nominal slot. When a running story changes, set `updated` and add the new facts; don't publish a near-duplicate story.
- **Link our own coverage in the body** when a story continues an earlier one ("as we reported on 6 November") and add the earlier story to `sources` with its full URL (`https://news.metaflora.xyz/2026/11/06/<id>/`, name "MetaFlora News"); the build rejects relative paths.
- **Standing explainers.** When a week is quiet, write one evergreen explainer per week tagged to its hub: what rescheduling to Schedule III changes; how Section 280E works; hemp-derived THC and the federal Total THC rule; how cannabis stocks trade (OTC vs Nasdaq vs Canadian listings); state-by-state legal status. Update the same explainer (`updated`) instead of writing a new one.
- **Stock pages are automatic.** Never write a story whose only content is a price move; the daily stock note covers that. Write a story when there is news (earnings, deals, regulation) and tag the company.

## Legal hubs (state, country and federal pages)

The site's highest-value pages are the evergreen legal hubs in `content/hubs/`: `states/` (all 50 + DC → `/legal/us/<state>/`), `countries/` (→ `/legal/world/<country>/`) and `explainers/` (federal topics → `/explainers/<slug>/`). They answer the questions people search ("Is weed legal in Ohio?") and every story feeds them automatically.

**Tagging (required).** Tag every US state and country a story is about with its full English name exactly as the hub file's `name` ("New York", "District of Columbia", "Czech Republic"), and the federal topic by its hub tag ("Rescheduling", "Section 280E", "SAFER Banking", "Hemp", "Total THC", "DEA"). The build then: lists the story under the hub's "Latest MetaFlora coverage", links the first mention in the story body to the hub, and adds the hub under "Covered in this story".

**Updating a hub when the law changes (required).** If a story reports a change to a hub fact (a law signed, a ballot result, sales starting, a limit changing, a court ruling, a milestone date), edit that hub's JSON in the same run:
- update the fact's `value`, `source` (primary source preferred: statute, regulator, governor, court, Federal Register) and `as_of` (today);
- update `legal` (states/countries) or `where_it_stands` / `next_milestone` (explainers) if the status changed;
- append a dated `timeline` entry and adjust `pending`;
- set `last_verified` to today.
A change to `legal.adult_use`, `legal.medical` or `legal.decriminalized` needs a primary (.gov, legislature or court) source. Never change a hub on the strength of a rumour, a poll or a proposal; proposals go in `pending`.
Never bump `last_verified` when nothing in the file changed.

**Original value (required for every story).** Each story must add at least one thing its sources don't have: context from the hub (e.g. "Ohio becomes the 25th state with adult-use sales", using `/legal/us/` data), a computed figure (price move, count, comparison across states), a primary document the sources didn't link, or a clear "what it means and what to watch" section. A story that only restates one outlet's article is not publishable; fold thin same-day items into a state-desk roundup instead.

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

## Web push alerts

Readers can subscribe with the bell. After each publish, `newsroom/push.py` alerts subscribers whose topics match each new story; full setup and admin controls are in `NOTIFICATIONS.md`.
- Mark a story `"breaking": true` only for genuinely urgent news (a federal ruling, a market-moving deal). It is alerted on its own, immediately. Use it rarely: at most one or two a week.
- The alert is the story's real headline and dek, so both must read well on a lock screen: name first, no teasers.
- `"push": false` keeps a story out of automatic alerts (corrections, minor updates). Editing or re-committing a story never re-alerts it.
