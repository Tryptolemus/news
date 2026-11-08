"""Source-mix check: warns (never fails) when a story leans on secondary reporting.

For every published article:
  - primary: at least one primary source (government / regulator / court / legislature, SEC and other filings,
    company IR or press-release wires, journals / DOI / PubMed / NIH)
  - concentration: share of external sources from the single most-used secondary outlet (warn above 60%;
    several primary documents, e.g. three SEC filings, do not count as one outlet)
  - named document: a headline that says report / study / filing / ruling / bill / lawsuit should link a
    primary document of the matching kind

Prints a WARNING summary in the build log and writes docs/admin/sourcecheck.json (admin/ is disallowed in
robots.txt and linked from nowhere). Usage on its own: python3 newsroom/sourcecheck.py
"""
import json
import re
from collections import Counter
from urllib.parse import urlparse

MAX_SHARE = 0.6
OWN = "news.metaflora.xyz"

# second-level public suffixes, so "bbc.co.uk" and "health.gov.au" group by the right registrable domain
_SLD = {"co", "com", "gov", "org", "net", "ac", "edu", "go", "gob", "gouv", "govt", "nic"}

GOV_EXACT = {
    # non-.gov government, regulator and court domains
    "europa.eu", "canada.ca", "gc.ca", "ontario.ca", "gov.bc.ca", "quebec.ca", "alberta.ca",
    "admin.ch", "bund.de", "bundesregierung.de", "bundesgesundheitsministerium.de", "bfarm.de", "bundestag.de",
    "bundesrat.de", "bundesverfassungsgericht.de", "bundesgerichtshof.de",
    "rijksoverheid.nl", "government.nl", "overheid.nl", "tweedekamer.nl", "public.lu", "gouvernement.lu", "chd.lu",
    "parliament.uk", "legislation.gov.uk", "gov.uk", "nhs.uk", "nice.org.uk", "mhra.gov.uk",
    "gov.cz", "psp.cz", "senat.cz", "gov.ro", "ms.ro", "cdep.ro", "senat.ro", "gov.pl", "sejm.gov.pl",
    "boe.es", "lamoncloa.gob.es", "gazzettaufficiale.it", "governo.it", "parlamento.it", "legifrance.gouv.fr",
    "gov.au", "tga.gov.au", "aph.gov.au", "govt.nz", "parliament.nz", "go.th", "gov.il", "gov.za",
    "un.org", "unodc.org", "who.int", "incb.org", "emcdda.europa.eu", "euda.europa.eu",
    "masscannabiscontrol.com", "courtlistener.com", "supremecourt.gov", "uscourts.gov", "federalregister.gov",
    "regulations.gov", "congress.gov", "govinfo.gov",
    # official text hosted elsewhere: government email bulletins, Congressional Research Service reports, statute and case text
    "content.govdelivery.com", "everycrsreport.com", "law.justia.com",
}
FILING_EXACT = {"sec.gov", "sedarplus.ca", "sedar.com", "efts.sec.gov", "companieshouse.gov.uk", "thecse.com",
                "businesswire.com", "globenewswire.com", "prnewswire.com", "newswire.ca", "accesswire.com",
                "newsfilecorp.com", "cision.com", "q4cdn.com", "q4inc.com", "irwebsitedata.com", "otcmarkets.com"}
JOURNAL_EXACT = {"doi.org", "nih.gov", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "clinicaltrials.gov",
                 "jamanetwork.com", "nejm.org", "thelancet.com", "bmj.com", "nature.com", "science.org", "sciencedirect.com",
                 "springer.com", "wiley.com", "frontiersin.org", "mdpi.com", "plos.org", "oup.com", "tandfonline.com",
                 "cell.com", "medrxiv.org", "biorxiv.org", "cochranelibrary.com", "sagepub.com", "karger.com",
                 "liebertpub.com", "cambridge.org", "biomedcentral.com", "aafp.org", "ahajournals.org", "acpjournals.org",
                 "europepmc.org", "jstor.org", "ssrn.com", "researchsquare.com", "cdc.gov", "fda.gov", "samhsa.gov", "drugabuse.gov"}
COURT_HINT = re.compile(r"(^|\.)(courts?|judiciary|supremecourt|uscourts|courtlistener|curia)\.|courts?\.", re.I)
LEG_HINT = re.compile(r"(^|\.)(leg|legis|legislature|legislation|senate|house|assembly|capitol|parliament|congress|bundestag|nysenate|ilga|malegislature)\b", re.I)
IR_HOST = re.compile(r"^(ir|investors?|investor-relations|newsroom|press|media)\.", re.I)
IR_PATH = re.compile(r"/(investors?|investor-relations|press-releases?|news-releases?|newsroom|financial-results|sec-filings)(/|$)", re.I)

DOC_WORDS = {
    "report": {"gov", "filing", "journal", "court", "legislature"},
    "study": {"journal", "gov"},
    "filing": {"filing", "court", "gov"},
    "ruling": {"court", "gov"},
    "bill": {"legislature", "gov"},
    "lawsuit": {"court", "filing", "gov"},
}
DOC_RE = re.compile(r"(?<!tax )(?<!utility )(?<!power )\b(reports?|study|studies|filings?|rulings?|bills?|lawsuits?)\b", re.I)


def host(url):
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def outlet(h):
    """Registrable domain: 'cannabis.ny.gov' -> 'ny.gov', 'www.bbc.co.uk' -> 'bbc.co.uk'."""
    parts = h.split(".")
    if len(parts) >= 3 and (parts[-2] in _SLD or (parts[-1] == "gov" and len(parts[-2]) == 2)):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _in(h, names):
    return any(h == n or h.endswith("." + n) for n in names)


def kind(url):
    """Primary-source kind of a URL ('gov', 'court', 'legislature', 'filing', 'journal') or None."""
    h = host(url)
    if not h or h == OWN:
        return None
    path = urlparse(url).path
    if _in(h, JOURNAL_EXACT):
        return "journal"
    if _in(h, FILING_EXACT) or IR_HOST.match(h) or IR_PATH.search(path):
        return "filing"
    if COURT_HINT.search(h):
        return "court"
    gov = (h.endswith((".gov", ".mil")) or ".gov." in h or ".gob." in h or ".gouv." in h or ".govt." in h
           or re.search(r"\.state\.[a-z]{2}\.us$", h) or h.endswith(".gv.at") or _in(h, GOV_EXACT))
    if gov and re.search(r"/opinions?/", path):
        return "court"
    if gov and LEG_HINT.search(h):
        return "legislature"
    if gov:
        return "gov"
    if LEG_HINT.search(h) and re.search(r"(legis|legislature|parliament|bundestag|senate)", h):
        return "legislature"
    return None


def check_article(a):
    srcs = [s.get("url", "") for s in a.get("sources") or []]
    ext = [u for u in srcs if host(u) and host(u) != OWN]
    kinds = {u: kind(u) for u in ext}
    primary = [u for u, k in kinds.items() if k]
    # concentration counts secondary outlets only: three SEC filings or court dockets are not "one outlet"
    counts = Counter(outlet(host(u)) for u in ext if not kinds[u])
    top, top_n = (counts.most_common(1)[0] if counts else ("", 0))
    share = round(top_n / len(ext), 2) if ext else 0.0
    m = DOC_RE.search(a.get("headline", ""))
    word = None
    if m:
        w = m.group(1).lower()
        word = {"reports": "report", "studies": "study", "filings": "filing", "rulings": "ruling", "bills": "bill", "lawsuits": "lawsuit"}.get(w, w)
    doc_ok = None
    if word:
        doc_ok = any(k in DOC_WORDS[word] for k in kinds.values() if k)
    warnings = []
    if not primary:
        warnings.append("no primary source")
    if share > MAX_SHARE:
        warnings.append(f"{int(share * 100)}% of sources from {top}")
    if word and not doc_ok:
        warnings.append(f"headline names a {word} but no matching primary document is linked")
    return {"id": a["id"], "path": a.get("_path"), "headline": a.get("headline"), "sources": len(srcs), "external": len(ext),
            "own": len(srcs) - len(ext), "primary": len(primary), "primary_urls": primary,
            "primary_kinds": sorted({k for k in kinds.values() if k}), "top_outlet": top, "top_share": share,
            "headline_document": word, "document_linked": doc_ok, "warnings": warnings}


def run(arts, write=None, verbose_limit=12):
    """Check every article, print a WARNING summary, write admin/sourcecheck.json via write(). Never raises."""
    try:
        rows = [check_article(a) for a in arts]
        n = len(rows)
        no_primary = [r for r in rows if not r["primary"]]
        concentrated = [r for r in rows if r["external"] and r["top_share"] > MAX_SHARE]
        named = [r for r in rows if r["headline_document"]]
        unlinked = [r for r in named if not r["document_linked"]]
        summary = {"articles": n, "with_primary": n - len(no_primary), "no_primary": len(no_primary),
                   "over_60pct_one_outlet": len(concentrated), "headline_names_document": len(named),
                   "document_not_linked": len(unlinked),
                   "avg_sources": round(sum(r["sources"] for r in rows) / n, 1) if n else 0,
                   "avg_top_share": round(sum(r["top_share"] for r in rows) / n, 2) if n else 0,
                   "outlets": Counter(r["top_outlet"] for r in rows if r["top_outlet"]).most_common(10)}
        flagged = [r for r in rows if r["warnings"]]
        if flagged:
            print(f"WARNING sourcecheck: {len(flagged)}/{n} stories flagged · no primary source {len(no_primary)} · "
                  f">60% one outlet {len(concentrated)} · named report/bill/ruling not linked {len(unlinked)}/{len(named)} "
                  f"(warning only; see NEWSROOM.md 'Source mix')")
            for r in flagged[:verbose_limit]:
                print(f"  - {r['id']}: {'; '.join(r['warnings'])}")
            if len(flagged) > verbose_limit:
                print(f"  ... and {len(flagged) - verbose_limit} more (docs/admin/sourcecheck.json)")
        else:
            print(f"sourcecheck: all {n} stories pass the source-mix check")
        out = {"summary": summary, "articles": rows}
        if write:
            write("admin/sourcecheck.json", json.dumps(out, indent=1, ensure_ascii=False))
        return out
    except Exception as e:  # noqa: BLE001 - this check must never break an edition build
        print(f"WARNING sourcecheck skipped: {e}")
        return None


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    import build
    arts = build.load_articles()
    res = run(arts)
    if res:
        print(json.dumps(res["summary"], indent=1))
