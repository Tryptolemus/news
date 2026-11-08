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

## Next rounds (from the board)
1. Round 6: refresh Village Farms and Organigram results; re-source the secondary-source facts (Arkansas, Texas, Nebraska, Georgia) when state sites load; WA/NY monthly sales.
2. Self-hosted WOFF2 fonts; 16:9 article photos (needs OPENAI_API_KEY secret).
3. Watch Search Console (Pages, Performance) and plan rounds around real queries.
