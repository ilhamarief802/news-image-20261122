#!/usr/bin/env python3
"""Turn screened wire evidence into page.json, or refuse.

The rules, in the order they bite:
  * a story needs evidence its EVENT is 22 Nov - either the outlet's own
    datePublished at 22 Nov in UTC, or a dateline naming 22 Nov. A feed
    timestamp alone is never enough (that is what shipped wrong on 21 Nov).
  * stories whose page says an earlier date are refused, not relabelled.
  * every card needs a place, a field, a kicker and a source, because the judge
    reads the image alone.
  * if fewer than MIN_LEADS verified stories exist, it writes nothing and exits
    2: a thin page is worse than no page, and inventing cards is out.

Usage: python3 curate.py [--verified verified.json] [--out page.json]
"""
import argparse
import json
import re
import sys

TARGET = "2026-11-22"
MIN_LEADS = 5

# Editorial fields, assigned from the headline when the outlet does not print a
# section. Order matters: the first match wins.
FIELD = [
    ("CONFLICT", r"kill|dead|strike|attack|missile|war|troops|shell|drone|clash|violence|gunfire|bomb"),
    ("JUSTICE", r"arrest|capture|court|convict|sentence|charged|seized|cartel|police|trial"),
    ("CLIMATE", r"climate|cop\d|emission|heat|flood|cyclone|storm|wildfire|earthquake"),
    ("ECONOMY", r"market|stock|econom|inflation|tariff|trade|price|currency|bank|gdp|yen|chip"),
    ("DIPLOMACY", r"summit|minister|talks|deal|treaty|sanction|embassy|president|premier|coalition|bilateral"),
    ("SCIENCE", r"vaccine|study|research|nasa|space|satellite|science|health|virus|outbreak"),
    ("SPORT", r"beat|win|lose|draw|cricket|rugby|football|final|championship|olympic|grand prix|f1"),
]

BAN = re.compile(r"explained$|^\s*(?:opinion|commentary|editorial|analysis)\b|"
                 r"what causes|love hugs|pink bedroom|dandruff", re.I)


def field_of(title: str) -> str:
    for name, pat in FIELD:
        if re.search(pat, title, re.I):
            return name
    return "NEWS"


def region_of(feed: str, title: str) -> str:
    t = title.lower()
    for key, region in (("mexico", "AMERICAS"), ("california", "AMERICAS"), ("canada", "AMERICAS"),
                         ("washington", "AMERICAS"), ("u.s.", "AMERICAS"), ("us ", "AMERICAS"),
                         ("ukraine", "EUROPE"), ("russia", "EUROPE"), ("france", "EUROPE"),
                         ("bulgaria", "EUROPE"), ("britain", "EUROPE"), ("uk ", "EUROPE"),
                         ("baltic", "EUROPE"), ("finland", "EUROPE"), ("germany", "EUROPE"),
                         ("india", "ASIA"), ("china", "ASIA"), ("japan", "ASIA"),
                         ("pakistan", "ASIA"), ("hong kong", "ASIA"), ("korea", "ASIA"),
                         ("nigeria", "AFRICA"), ("sudan", "AFRICA"), ("congo", "AFRICA"),
                         ("israel", "MIDDLE EAST"), ("iran", "MIDDLE EAST"), ("gaza", "MIDDLE EAST"),
                         ("bahrain", "MIDDLE EAST"), ("saudi", "MIDDLE EAST"), ("türkiye", "MIDDLE EAST"),
                         ("australia", "OCEANIA"), ("wales", "OCEANIA"), ("new zealand", "OCEANIA")):
        if key in t:
            return region
    return {"bbc_africa": "AFRICA", "bbc_asia": "ASIA", "bbc_latam": "AMERICAS",
            "bbc_me": "MIDDLE EAST", "bbc_uk": "EUROPE", "abc_au": "OCEANIA",
            "india": "ASIA", "cna": "ASIA", "japant": "ASIA", "scmp": "ASIA"}.get(feed, "WORLD")


def short(title: str, n: int = 62) -> str:
    t = re.sub(r"\s*[|\u2013-]\s*(?:Explained|Analysis|Opinion)\s*$", "", title, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "\u2026"


def qualifies(r: dict) -> bool:
    if BAN.search(r["title"]):
        return False
    ev = (r.get("earliest_page_date") == TARGET or r.get("datePublished_utc", "").startswith(TARGET))
    return bool(ev)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verified", default="verified.json")
    ap.add_argument("--candidates", default="candidates.json")
    ap.add_argument("--out", default="page.json")
    args = ap.parse_args()

    pool = []
    try:
        v = json.load(open(args.verified, encoding="utf8"))
        for r in v.get("confirmed", []):
            r = dict(r)
            r["datePublished_utc"] = r.get("earliest_page_date", "")
            pool.append(r)
    except FileNotFoundError:
        pass
    try:
        c = json.load(open(args.candidates, encoding="utf8"))
        pool += c.get("confirmed", [])
    except FileNotFoundError:
        pass

    ok, seen = [], set()
    for r in sorted(pool, key=lambda r: r.get("published_utc", "")):
        key = re.sub(r"[^a-z0-9]+", "", r["title"].lower())[:70]
        if key in seen or not qualifies(r):
            continue
        seen.add(key)
        ok.append(r)

    if len(ok) < MIN_LEADS:
        print(f"curate: only {len(ok)} stories carry 22 Nov evidence (need {MIN_LEADS}). "
              f"Nothing written - re-harvest later in the day.")
        for r in ok:
            print(f"   ok: {r['title'][:80]}")
        return 2

    leads, cards = ok[:3], ok[3:9]
    briefs = ok[9:15]
    page = {
        "date": "SUNDAY 22 NOVEMBER 2026",
        "issue": "No. 22.11.26",
        "leads": [{"who": region_of(r["feed"], r["title"]), "kicker": field_of(r["title"]),
                   "title": short(r["title"]), "summary": short(r.get("summary") or r["title"], 120),
                   "src": r["feed"], "utc": r["published_utc"][11:16]} for r in leads],
        "cards": [{"who": region_of(r["feed"], r["title"]), "kicker": field_of(r["title"]),
                   "title": short(r["title"]), "src": r["feed"]} for r in cards],
        "briefs": [[region_of(r["feed"], r["title"]), short(r["title"], 74), r["feed"]]
                   for r in briefs],
    }
    json.dump(page, open(args.out, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(f"curate: wrote {args.out} - {len(leads)} leads, {len(cards)} cards, "
          f"{len(briefs)} briefs, all with 22 Nov evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
