# SEO board: state of play (handoff, 8 Nov 2026)

Score history lives in `content/seo/history.json` (63.4 baseline → 80.5 after round 5).
Run `python3 newsroom/seo_audit.py --label "Round N: …"` after each round; it appends to the history.
Dashboard (claude.ai artifact, Greg's account): https://claude.ai/artifact/2qq8t17WAGAuNuTcqAA2iq
To update it: upload `content/seo/history.json` as an asset to that artifact, then point `datasets/history.source.url` at the new asset.

## Page families (all built by `newsroom/hubs.py` from `content/hubs/<kind>/*.json`)
| Kind | Data dir | URL | Notes |
|---|---|---|---|
| US states | `states/` (51) | `/legal/us/<slug>/` + tracker `/legal/us/` (CSV) | quick answers, neighbours, computed comparisons, operators, sales link |
| Countries | `countries/` (22) | `/legal/world/<slug>/` | |
| Explainers | `explainers/` (32) | `/explainers/<slug>/` | public-housing is partial (noindex) |
| Glossary | `glossary/` (60) | `/glossary/<slug>/` | |
| Companies | `companies/` (13) | `/company/<slug>/` | MSOS partial (fund). Village Farms Q3 due 9 Nov; Organigram FY results pending |
| Sales data | `sales/` (21) | `/data/<slug>-cannabis-sales/` (CSV) | 13 indexable; WA, NY, MO, ME, MI, MN, DE, RI partial |

Rules: `page_status: "complete"` = indexable, anything else = noindex. Never a key named `status` at top level.
Every fact is `{value, source, as_of}`; bump `last_verified` only when something changed; add a `changelog` line.

## Other things that must not be undone
- `build.py` writes `google9150a2b1ed3521a0.html` (Google Search Console ownership for gt.elysium@gmail.com). Never remove.
- Search Console: property `https://news.metaflora.xyz/` verified; `sitemap.xml` + `sitemap-news.xml` submitted 7–8 Nov.
- Topic pages owned by a hub are 1 KB redirect stubs (canonical + refresh), not noindex.
- Titles use `TITLE_YEAR` in hubs.py (bump in a dated sweep, not per build).

## Round 7 (8 Nov 2026) – shipped
- By-state tables (`newsroom/bystate.py`): /legal/us/by-state/ + possession, home grow, hemp THC (noindex until 41/51 states have a sourced `hemp_thc`), public consumption, DUI, where tourists can buy; /data/cannabis-sales-by-state/ (official full-year totals only). Each has CSV, Dataset/FAQPage/ItemList JSON-LD.
- Autolink: every state, country and company a story names (full name only for untagged hubs; `AMBIGUOUS` names like Washington only when tagged; `in_proper_name`/`place_ok` skip other meanings), plus up to 3 specific glossary terms. Hub "Latest coverage" also counts stories that name the place/company.
- Self-hosted subset WOFF2 fonts (`newsroom/webfonts.py`), Newsreader italic via a non-blocking Google Fonts link; SW navigation preload; titles never truncated; descriptions end on whole sentences; small footer/mast images; 404 has no canonical.
- `STOCK_PAGES` comes from `market.TICKERS`. Board files: scratchpad seo-board/r7_*.md.

## Next rounds (from the board)
1. Round 8: 16:9/4:3/1:1 lead images rendered from each story's visual motif (Discover); source-mix build check (>=1 primary source, <=60% from one outlet, link the named report/bill/ruling); Wikidata sameAs (verified ids only) + NewsArticle about/mentions; archive pagination + daily edition pages; feeds per state/company; IndexNow for changed hubs.
2. Data: source `hemp_thc` and `taxes` for the 24 states missing each; Village Farms Q3 (9 Nov), Organigram FY.
3. Owner decisions: a named human reviewer for top stories (Google AI-content guidance); Google News Publisher Center + Bing Webmaster Tools; Cloudflare proxy for caching.
4. Watch Search Console (Pages, Performance) and plan rounds around real queries.
