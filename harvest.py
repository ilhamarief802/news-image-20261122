#!/usr/bin/env python3
"""Harvest 22 November 2026 wire copy, keeping publication time and source zone.

For every item this writes: title, link, the outlet's own <pubDate> as written,
that <pubDate> parsed to UTC, the source's UTC offset, the feed it came from, and
a summary if the feed carries one. It writes nothing else: no event time is
inferred here, because inferring it is the whole problem. classify.py decides an
event time only from text the outlet itself printed.

Usage: python3 harvest.py [--out news22.json]
"""
import argparse
import email.utils
import glob
import html
import json
import os
import re
import sys
import urllib.request

FEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feeds")

# Every feed below is a general-news desk in its own region, so a story that
# happens at 23:00 local is still 22 Nov there. Zone comes from the feed's own
# pubDate offset, never guessed from the outlet's name.
FEEDS = [
    ("bbc_world", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("bbc_uk", "https://feeds.bbci.co.uk/news/uk/rss.xml"),
    ("bbc_us", "https://feeds.bbci.co.uk/news/world/us_canada/rss.xml"),
    ("bbc_asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml"),
    ("bbc_africa", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
    ("bbc_me", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("bbc_latam", "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml"),
    ("bbc_bus", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("bbc_tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("bbc_sci", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("bbc_sport", "https://feeds.bbci.co.uk/news/sport/rss.xml"),
    ("bbc_pol", "https://feeds.bbci.co.uk/news/politics/rss.xml"),
    ("aj", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("nyt_w", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("guard_w", "https://www.theguardian.com/world/rss"),
    ("npr_w", "https://feeds.npr.org/1004/rss.xml"),
    ("f24", "https://www.france24.com/en/rss"),
    ("dw", "https://rss.dw.com/rdf/rss-en-world"),
    ("cbc", "https://www.cbc.ca/webfeed/rss/rss-world"),
    ("abc_au", "https://www.abc.net.au/news/feed/51120/rss.xml"),
    ("cna", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"),
    ("scmp", "https://www.scmp.com/rss/91/feed"),
    ("japant", "https://www.japantimes.co.jp/feed/"),
    ("arab", "https://www.arabnews.com/rss.xml"),
    ("india", "https://www.thehindu.com/news/international/feeder/default.rss"),
    ("ft", "https://www.ft.com/world?format=rss"),
    ("un", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
    ("almon", "https://www.al-monitor.com/rss"),
    ("lat", "https://www.latimes.com/world-nation/rss2.0.xml"),
    ("nyt_bus", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("nyt_tech", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"),
    ("guard_bus", "https://www.theguardian.com/uk/business/rss"),
    ("guard_tech", "https://www.theguardian.com/uk/technology/rss"),
]

DAY = "2026-11-22"


def fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf8", "replace")


def strip_tags(s: str) -> str:
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def parse_items(doc: str):
    """Yield (title, link, pub_raw, summary) for RSS <item> and Atom <entry>."""
    for block in re.findall(r"<item\b.*?</item>", doc, flags=re.S):
        def grab(tag):
            m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", block, flags=re.S)
            return m.group(1) if m else ""
        yield (strip_tags(grab("title")), strip_tags(grab("link")),
               strip_tags(grab("pubDate")) or strip_tags(grab("dc:date")),
               strip_tags(grab("description")))
    for block in re.findall(r"<entry\b.*?</entry>", doc, flags=re.S):
        def grab2(tag):
            m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", block, flags=re.S)
            return m.group(1) if m else ""
        link = ""
        m = re.search(r'<link[^>]*href="([^"]+)"', block)
        if m:
            link = m.group(1)
        yield (strip_tags(grab2("title")), link,
               strip_tags(grab2("updated")) or strip_tags(grab2("published")),
               strip_tags(grab2("summary")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="news22.json")
    ap.add_argument("--dir", default=FEED_DIR)
    ap.add_argument("--day", default=DAY)
    args = ap.parse_args()

    os.makedirs(args.dir, exist_ok=True)
    rows, failures = [], []
    for name, url in FEEDS:
        path = os.path.join(args.dir, f"{name}.xml")
        try:
            doc = fetch(url)
            if len(doc) < 400:
                raise ValueError(f"feed body is {len(doc)} bytes")
            with open(path, "w", encoding="utf8") as fh:
                fh.write(doc)
        except Exception as exc:                      # a dead desk is data too
            failures.append((name, str(exc)))
            doc = None
        if doc is None and os.path.isfile(path):
            doc = open(path, encoding="utf8", errors="replace").read()
        if not doc:
            continue
        for title, link, pub_raw, summary in parse_items(doc):
            if not pub_raw or not title:
                continue
            try:
                dt = email.utils.parsedate_to_datetime(pub_raw)
                if dt is None:
                    continue
                off = dt.utcoffset()
                utc = dt.astimezone(tz=None).astimezone()  # normalise below
            except Exception:
                continue
            from datetime import timezone
            utc = dt.astimezone(timezone.utc)
            rows.append({
                "feed": name,
                "title": title,
                "link": link,
                "summary": summary,
                "published_raw": pub_raw,
                "published_utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_utc_offset_h": (off.total_seconds() / 3600.0) if off else 0.0,
                "local_date": dt.strftime("%Y-%m-%d"),
            })

    # Dedupe on the normalised headline, keeping the earliest publication.
    seen, out = {}, []
    for r in sorted(rows, key=lambda r: r["published_utc"]):
        key = re.sub(r"[^a-z0-9]+", "", r["title"].lower())[:90]
        if key in seen:
            continue
        seen[key] = 1
        out.append(r)

    day = [r for r in out if r["published_utc"].startswith(args.day)
           or r["local_date"] == args.day]
    with open(args.out, "w", encoding="utf8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)

    print(f"feeds: {len(FEEDS) - len(failures)} ok, {len(failures)} failed"
          + (f" ({', '.join(n for n, _ in failures)})" if failures else ""))
    print(f"items: {len(out)} deduped; {len(day)} carry a 22 Nov publication stamp")
    print(f"written: {args.out}")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
