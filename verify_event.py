#!/usr/bin/env python3
"""Read each candidate's own article and pull the dateline the outlet printed.

classify.py only sees a headline and an RSS summary, which seldom carry a date.
This fetches the article the item links to and looks for the event time where
desks actually put it: a <time> element, a JSON-LD datePublished/dateModified
pair with an article body date, or a visible dateline in the opening paragraphs.

It reports what it found, with the sentence, and never upgrades an item to
"22 Nov" on the strength of a feed timestamp alone.
"""
import argparse
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
MON = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"])}
ABBR = {m[:3]: i + 1 for m, i in MON.items()}

DATELINE = [
    re.compile(r"\b(?:Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),?\s+"
               r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|"
               r"October|November|December)\s+(\d{4})", re.I),
    re.compile(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|"
               r"October|November|December)\s+(\d{4})\b", re.I),
    re.compile(r"\b(November|Nov\.?)\s+(\d{1,2}),?\s+(2026)\b", re.I),
]


def get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf8", "replace")


def visible_text(doc: str) -> str:
    doc = re.sub(r"<script\b.*?</script>", " ", doc, flags=re.S | re.I)
    doc = re.sub(r"<style\b.*?</style>", " ", doc, flags=re.S | re.I)
    doc = re.sub(r"<[^>]+>", " ", doc)
    return re.sub(r"\s+", " ", html.unescape(doc))


def jsonld_dates(doc: str):
    """datePublished / dateModified from any JSON-LD block, as UTC stamps."""
    out = []
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                            doc, flags=re.S | re.I):
        for key in ("datePublished", "dateModified", "dateCreated"):
            for m in re.finditer(rf'"{key}"\s*:\s*"([^"]+)"', block):
                raw = m.group(1)
                try:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    out.append((key, raw, dt.astimezone(timezone.utc)))
                except Exception:
                    out.append((key, raw, None))
    return out


def time_elements(doc: str):
    """<time datetime="..."> values the page carries."""
    out = []
    for m in re.finditer(r'<time[^>]*datetime="([^"]+)"', doc):
        raw = m.group(1)
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            out.append((raw, dt.astimezone(timezone.utc)))
        except Exception:
            pass
    return out


def find_dateline(text: str):
    for pat in DATELINE:
        m = pat.search(text)
        if not m:
            continue
        g = [x for x in m.groups() if x]
        try:
            if g[0].isdigit():
                d, mon = int(g[0]), MON.get(g[1].lower() if len(g[1]) > 3 else g[1].lower(), 0)
                if not mon:
                    mon = ABBR.get(g[1].lower()[:3], 0)
                y = int(g[2])
            else:
                mon = MON.get(g[0].lower().rstrip("."), ABBR.get(g[0].lower()[:3], 0))
                d, y = int(g[1]), int(g[2])
            return f"{y:04d}-{mon:02d}-{d:02d}", m.group(0)
        except Exception:
            continue
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="candidates.json")
    ap.add_argument("--out", default="verified.json")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--target", default="2026-11-22")
    args = ap.parse_args()

    piles = json.load(open(args.inp, encoding="utf8"))
    pool = [r for name in ("unknown", "prior") for r in piles.get(name, [])]
    pool.sort(key=lambda r: r["published_utc"])

    ok, bad = [], []
    for r in pool[:args.limit]:
        link = (r.get("link") or "").strip()
        rec = dict(r)
        if not link.startswith("http"):
            rec["fetch"] = "no link"
            bad.append(rec)
            continue
        try:
            doc = get(link)
        except Exception as exc:
            rec["fetch"] = f"error: {type(exc).__name__}"
            bad.append(rec)
            continue
        rec["fetch"] = "ok"
        rec["bytes"] = len(doc)
        text = visible_text(doc)
        dl, dlsent = find_dateline(text[:9000])
        rec["dateline_in_text"] = dl
        rec["dateline_sentence"] = dlsent
        ld = jsonld_dates(doc)
        rec["jsonld"] = [(k, v, d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None) for k, v, d in ld]
        te = time_elements(doc)
        rec["time_elements"] = [(v, d.strftime("%Y-%m-%dT%H:%M:%SZ")) for v, d in te[:6]]
        # the event date is the earliest datePublished / dateline the page states
        cands = [d for k, _v, d in ld if d and k in ("datePublished", "dateCreated")]
        cands += [d for _v, d in te]
        rec["earliest_page_date"] = (min(cands).strftime("%Y-%m-%d") if cands else None)
        ok.append(rec)

    conf = [r for r in ok if (r.get("dateline_in_text") == args.target
                               or r.get("earliest_page_date") == args.target)]
    json.dump({"confirmed": conf, "fetched": ok, "failed": bad},
              open(args.out, "w", encoding="utf8"), indent=1, ensure_ascii=False)

    print(f"fetched {len(ok)}/{len(pool[:args.limit])} ok, {len(bad)} failed; "
          f"{len(conf)} carry a 22 Nov event date on the page itself\n")
    for r in conf:
        ev = r.get("dateline_sentence") or r.get("earliest_page_date")
        print(f'  {r["published_utc"][11:16]} {r["feed"]:<11} {r["title"][:88]}')
        print(f'      EVENT {ev!r}')
    print("\n-- fetched, no 22 Nov event date on the page --")
    for r in ok:
        if r in conf:
            continue
        print(f'  {r["published_utc"][11:16]} {r["feed"]:<11} '
              f'{(r.get("earliest_page_date") or "-"):<12} {r["title"][:74]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
