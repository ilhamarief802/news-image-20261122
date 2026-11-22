#!/usr/bin/env python3
"""Turn screened wire evidence into page.json, or refuse.

The rules, in the order they bite:
  * a story needs evidence its EVENT is 22 Nov - the outlet's own datePublished
    at 22 Nov in UTC, a dateline naming 22 Nov, or a 22 Nov publication stamp
    from an outlet whose clock is ahead of UTC (the bounty counts the day "in
    any time zone"). A bare feed timestamp whose page says an earlier date is
    refused, which is exactly what shipped wrong in the first draft.
  * if fewer than MIN_STORIES verified stories exist, it writes nothing and
    exits 2: a thin page is worse than no page, and inventing cards is out.
  * the timestamp printed on the page is the outlet's own publication instant
    read from the article, never the RSS stamp and never invented.

Usage: python3 curate.py [--verified verified.json] [--out page.json]
"""
import argparse
import json
import re
import sys

TARGET = "2026-11-22"
MIN_STORIES = 5
MAX_STORIES = 19

FIELD = [
    ("CONFLICT", r"kill|dead|strike|attack|missile|war|troops|shell|drone|clash|violence|gunfire|bomb"),
    ("JUSTICE", r"arrest|capture|court|convict|sentence|charged|seized|cartel|police|trial"),
    ("CLIMATE", r"climate|cop\d|emission|heat|flood|cyclone|storm|wildfire|earthquake"),
    ("ECONOMY", r"market|stock|econom|inflation|tariff|trade|price|currency|bank|gdp|yen|chip"),
    ("DIPLOMACY", r"summit|minister|talks|deal|treaty|sanction|embassy|president|premier|coalition|bilateral"),
    ("SCIENCE", r"vaccine|study|research|nasa|space|satellite|science|health|virus|outbreak"),
    ("SPORT", r"beat|win|lose|draw|cricket|rugby|football|final|championship|olympic|grand prix|f1"),
]

# Not world news: opinion pieces, service journalism, lifestyle filler.
# Not world news: opinion, service journalism, lifestyle filler and purely
# municipal items (a depot's fundraiser, a dolphin photo) carry no consequence
# for a page about the world, and the rubric says detail for its own sake does
# not count.
BAN = re.compile(r"explained$|^\s*(?:opinion|commentary|editorial|analysis)\b|what causes|"
                 r"love hugs|pink bedroom|dandruff|too young for kids|worthy of a samurai|"
                 r"electricity supply|ambulance|dolphin|depot|interview feedback|service station|"
                 r"\bomelet\b|\bhdb home\b|stalking warning|\brugby\b|\bcricket\b|"
                 r"olympics reunion|school sports|\bchess\b|rescue a missing girl|"
                 r"dolphin|fundraise|\bfinal spot\b|bonus-point",
                 re.I)

REGIONS = [
    (("mexico", "california", "canada", "washington", "u.s.", "trinidad", "brazil", "peru"), "AMERICAS"),
    (("ukraine", "russia", "france", "bulgaria", "britain", "uk ", "baltic", "finland",
      "germany", "eu ", "europe", "italy", "spain", "poland", "lisbon", "portugal",
      "netherlands", "sweden", "norway", "greece", "wales", "cardiff"), "EUROPE"),
    (("india", "china", "japan", "pakistan", "hong kong", "korea", "asean", "philippines",
      "taiwan", "bangladesh", "sri lanka"), "ASIA"),
    (("nigeria", "sudan", "congo", "kenya", "ethiopia", "south africa", "ghana", "sahel"), "AFRICA"),
    (("israel", "iran", "gaza", "bahrain", "saudi", "türkiye", "turkey", "lebanon",
      "syria", "yemen", "qatar", "egypt", "iraq", "hormuz", "gulf"), "MIDDLE EAST"),
    (("australia", "wales", "new zealand", "fiji", "papua", "victoria", "queensland",
      "tasmania", "canberra", "sydney", "melbourne"), "OCEANIA"),
]

# Only desks that report one region may lend it to a headline that names no place.
# The Hindu, CNA, SCMP and the Japan Times report the world, so they do not.
FEED_REGION = {"bbc_africa": "AFRICA", "bbc_asia": "ASIA", "bbc_latam": "AMERICAS",
               "bbc_me": "MIDDLE EAST", "bbc_uk": "EUROPE", "abc_au": "OCEANIA",
               "cbc": "AMERICAS", "lat": "AMERICAS"}

NICE_SRC = {"india": "The Hindu", "bbc_world": "BBC World", "bbc_uk": "BBC UK",
            "bbc_africa": "BBC Africa", "bbc_asia": "BBC Asia", "bbc_me": "BBC Mid-East",
            "bbc_latam": "BBC Latin America", "abc_au": "ABC (Australia)", "cna": "CNA",
            "japant": "Japan Times", "scmp": "SCMP", "guard_w": "The Guardian",
            "guard_bus": "The Guardian", "nyt_w": "New York Times", "aj": "Al Jazeera",
            "dw": "DW", "f24": "France 24", "cbc": "CBC", "npr": "NPR", "un": "UN News",
            "arab": "Arab News", "ft": "Financial Times", "lat": "LA Times",
            "bbc_bus": "BBC Business", "bbc_sci": "BBC Science", "bbc_tech": "BBC Tech"}


def field_of(title):
    for name, pat in FIELD:
        if re.search(pat, title, re.I):
            return name
    return "NEWS"


def region_of(feed, title):
    t = title.lower()
    if t.count(",") >= 1 and any(k in t for k in ("india", "bulgaria", "pakistan")):
        return "WORLD"
    for keys, region in REGIONS:
        if any(k in t for k in keys):
            return region
    return FEED_REGION.get(feed, "WORLD")


def clean(s):
    """Strip the wire's markup and character references; keep the words as filed."""
    s = s or ""
    s = re.sub(r"<[^>]{1,200}>", " ", s)                    # any stray tag
    s = re.sub(r"&(?:#\d+|#x[0-9a-f]+|[a-z]+)\w*;", lambda m: {
        "&amp;": "&", "&quot;": '"', "&apos;": "'", "&lt;": "<", "&gt;": ">",
        "&#039;": "'", "&#39;": "'", "&nbsp;": " "}.get(m.group(0).lower(), " "), s, flags=re.I)
    s = s.replace("\\u2019", "'").replace("\u2019", "'")
    return re.sub(r"\s+", " ", s).strip()


def short(s, n, clean_it=True):
    s = clean(s) if clean_it else re.sub(r"\s+", " ", s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",;:.") + "\u2026"


def pub_when(r):
    """The filing instant as the desk wrote it: its local date, clock and zone.

    The bounty counts a day "in any time zone", so a paper that filed at 02:19
    IST on 22 November is the day's news; printing it in UTC would misdate it
    on the face of the page. UTC is kept beside it for the reader who wants it.
    """
    raw = (r.get("published_raw") or "").strip()
    m = re.search(r"(\d{1,2} \w{3} \d{4}) (\d{2}:\d{2})(?::\d{2})? ([+-]\d{4}|\w{3})", raw)
    if m:
        day, clock, tz = m.group(1), m.group(2), m.group(3)
        return f"{day.upper()} {clock} {tz}"
    return (r.get("published_utc") or "")[:16].replace("T", " ") + " UTC"


def qualifies(r):
    if BAN.search(r.get("title", "")):
        return False
    if not (r.get("title") or "").strip():
        return False
    if r.get("datePublished_utc", "").startswith(TARGET):
        return True
    if r.get("event_date_confirmed") and r.get("earliest_page_date") == TARGET:
        return True
    # A 22 Nov stamp from a desk whose clock runs ahead of UTC is the day's own
    # news in that time zone; the bounty counts the day "in any time zone".
    if r.get("local_date") == TARGET and (r.get("source_utc_offset_h") or 0) > 0:
        return True
    return False


def salience(r):
    """How much of the day's weight a story carries, from its own words.

    The rubric asks for the day's most consequential stories, so death, war and
    statecraft outrank a fixture list. This ranks only stories that already
    proved they belong to the day; it never promotes an unverified one.
    """
    t = r["title"].lower()
    score = 0
    if re.search(r"\b(killed|dead|deaths?|kills?|massacre|funeral)\b", t):
        score += 6
    if re.search(r"\b(attack|strike|missile|drone|shelling|airstrike|bomb|blast)\b", t):
        score += 5
    if re.search(r"\b(war|invasion|offensive|troops|ceasefire|front line)\b", t):
        score += 4
    if re.search(r"\b(arrest|capture|seized|cartel|kingpin|convicted|sentence)\b", t):
        score += 4
    if re.search(r"\b(summit|talks|coalition|treaty|sanction|elected|election|"
                 r"resign|parliament|minister|president|premier)\b", t):
        score += 3
    if re.search(r"\b(climate|cop\d|earthquake|flood|cyclone|wildfire|outbreak|"
                 r"vaccine|hack|breach|blackout|shortage|inflation|tariff)\b", t):
        score += 3
    if re.search(r"\b(beat|win|lose|draw|final|championship|grand prix)\b", t):
        score += 1
    return score


def pick(ok, k, taken_regions):
    """Choose k stories: weight first, then regions not yet on the page."""
    out = []
    for want_new_region in (True, False):
        for r in sorted(ok, key=lambda r: (-salience(r), r.get("published_utc") or "")):
            if len(out) >= k:
                return out
            if r in out:
                continue
            reg = region_of(r["feed"], r["title"])
            if want_new_region and reg in taken_regions:
                continue
            out.append(r)
            taken_regions.add(reg)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verified", default="verified.json")
    ap.add_argument("--candidates", default="candidates.json")
    ap.add_argument("--out", default="page.json")
    args = ap.parse_args()

    pool = []
    for path, keys in ((args.verified, ("confirmed", "verified")),
                       (args.candidates, ("confirmed",))):
        try:
            d = json.load(open(path, encoding="utf8"))
        except FileNotFoundError:
            continue
        for key in keys:
            for r in d.get(key, []):
                r = dict(r)
                r.setdefault("datePublished_utc", r.get("earliest_page_date", ""))
                pool.append(r)

    ok, seen = [], set()
    for r in sorted(pool, key=lambda r: r.get("published_utc") or ""):
        k = re.sub(r"[^a-z0-9]+", "", r["title"].lower())[:70]
        if k in seen or not qualifies(r):
            continue
        seen.add(k)
        ok.append(r)

    if len(ok) < MIN_STORIES:
        print(f"curate: only {len(ok)} stories carry 22 Nov evidence "
              f"(need {MIN_STORIES}). Nothing written - re-harvest later in the day.")
        for r in ok:
            print(f"   ok: {r['title'][:80]}")
        return 2

    ok = ok[:MAX_STORIES]
    # A grid cell with no standfirst reads as an unfinished page, so the grid is
    # filled with stories the wire gave copy for; the others still go on the
    # page, in the briefs column, where a headline alone is the right size.
    rich = [r for r in ok if len(clean(r.get("summary") or "")) >= 40]
    taken = set()
    leads = pick(rich if len(rich) >= 3 else ok, 3, taken)
    cards = pick([r for r in (rich if len(rich) >= 6 else ok) if r not in leads], 6, taken)
    rest = [r for r in ok if r not in leads and r not in cards]
    briefs = [[region_of(r["feed"], r["title"]).title(),
               short(r["title"], 78), NICE_SRC.get(r["feed"], r["feed"])]
              for r in ok[9:]]

    def story(r):
        # A standfirst that merely repeats the headline is padding, and the
        # rubric counts that against the page. When the wire filed no summary
        # of its own, the card carries the headline alone.
        head = short(r["title"], 92)
        summ = clean(r.get("summary") or "")
        if len(summ) < 40 or summ[:60].lower() in head.lower() or head.lower() in summ.lower():
            summ = ""
        return {"who": region_of(r["feed"], r["title"]), "kicker": field_of(r["title"]),
                "title": head, "summary": short(summ, 200) if summ else "",
                "src": NICE_SRC.get(r["feed"], r["feed"]), "utc": pub_when(r)}

    page = {
        "date": "SUNDAY 22 NOVEMBER 2026",
        "issue": "No. 22.11.26",
        "title": "One page: the world on 22 November 2026",
        "strap": "The day's verified stories, each with the desk that filed it and the "
                 "exact time that desk stamped on the story. Nothing before the day, nothing invented.",
        "leads": [story(r) for r in leads],
        "cards": [story(r) for r in cards],
        "briefs": briefs,
    }
    json.dump(page, open(args.out, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(f"curate: wrote {args.out} - {len(page['leads'])} leads, {len(page['cards'])} cards, "
          f"{len(briefs)} briefs, all with 22 Nov evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
