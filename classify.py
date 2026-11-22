#!/usr/bin/env python3
"""Screen harvested items for evidence that the EVENT, not just the filing, is 22 Nov.

The bounty's judge penalises an image that shows, as its day's news, events that
happened before that day. So an item earns a place only if the outlet's own text
names 22 November for the event, and loses it if the text names an earlier day.
This script does not decide: it groups candidates into three piles and prints the
sentence the evidence came from, so a human (or the agent) reads the evidence.

  confirmed  the text names 22 Nov for the event
  prior      the text names an earlier day for the event -> excluded
  unknown    no date in the text at all -> cannot be used as a 22 Nov story
"""
import argparse
import json
import re
import sys

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

# "22 November", "22 Nov", "November 22", "Nov. 22" - with the year optional.
DAY22 = [
    re.compile(r"\b22(?:st)?\s+(?:of\s+)?nov(?:ember)?\b\.?(?:\s*,?\s*2026)?", re.I),
    re.compile(r"\bnov(?:ember)?\.?\s+22(?:nd)?\b(?:\s*,?\s*2026)?", re.I),
]
# Any other calendar day nailed to November / an earlier month, for the prior pile.
PRIOR = [
    re.compile(r"\b(?:1[0-9]|2[01]|[1-9])(?:st|nd|rd|th)?\s+(?:of\s+)?nov(?:ember)?\b", re.I),
    re.compile(r"\bnov(?:ember)?\.?\s+(?:1[0-9]|2[01]|[1-9])\b", re.I),
    re.compile(r"\b(?:1[0-9]|2[01]|[1-9])(?:st|nd|rd|th)?\s+(?:of\s+)?oct(?:ober)?\b\.?", re.I),
    re.compile(r"\b(?:yesterday|last night|on friday|on thursday|on saturday)\b", re.I),
]
SUNDAY = re.compile(r"\b(?:on\s+)?sunday\b", re.I)


def has22(text: str):
    for pat in DAY22:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


def prior_hits(text: str):
    out = []
    for pat in PRIOR:
        for m in pat.finditer(text):
            out.append(m.group(0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="news22.json")
    ap.add_argument("--day", default="2026-11-22")
    ap.add_argument("--json-out", default="candidates.json")
    args = ap.parse_args()

    rows = json.load(open(args.inp, encoding="utf8"))
    stamped = [r for r in rows if r["published_utc"].startswith(args.day)
               or r["local_date"] == args.day]

    piles = {"confirmed": [], "prior": [], "unknown": []}
    for r in stamped:
        blob = f'{r["title"]} . {r.get("summary", "")}'
        ev = has22(blob)
        prior = prior_hits(blob)
        r["evidence_22"] = ev
        r["evidence_prior"] = prior
        r["event_date_confirmed"] = bool(ev) and not prior
        if ev and not prior:
            piles["confirmed"].append(r)
        elif prior and not ev:
            piles["prior"].append(r)
        else:
            piles["unknown"].append(r)

    json.dump(piles, open(args.json_out, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    for name in ("confirmed", "prior", "unknown"):
        print(f"\n===== {name.upper()}  ({len(piles[name])})")
        for r in piles[name]:
            print(f'  {r["published_utc"][11:16]} {r["feed"]:<11} {r["title"][:96]}')
            if r["evidence_22"]:
                print(f'      EV 22 Nov: "{r["evidence_22"]}"')
            if r["evidence_prior"]:
                print(f'      PRIOR    : {r["evidence_prior"][:4]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
