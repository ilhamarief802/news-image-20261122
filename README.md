# news-image-20261122

[![make.fun · news-image-20261122](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![rank](https://make.fun/badge/news-image-20261122/ilhamarief802/news-image-20261122/rank.svg)](https://make.fun/bounty/news-image-20261122/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![reward](https://make.fun/badge/news-image-20261122/ilhamarief802/news-image-20261122/reward.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)

One page that sums up **Sunday 22 November 2026's** world news: the day's
verified stories, each with the outlet that filed it and that outlet's own clock
in UTC, a world map pinning where each one happened, and a footer that states
exactly which desks the page was compiled from.

Every story on the page is dated 22 November 2026 in the outlet's own
`datePublished` (UTC), read from the article itself — not from an RSS feed
timestamp. Items whose article carries an earlier date are refused rather than
re-labelled: see `verify_event.py`, which fetches each candidate and pulls the
dateline, and `curate.py`, which writes no page at all when fewer than five
verified stories exist.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`main.py` copies `entry.png` to `/output/entry.png` and then proves the copy is a
whole, valid image before it leaves anything behind: PNG signature, every chunk
through to IEND with its CRC, at most 1 MiB, at most 1024x1024, and the bytes
read back from `/output` must match the source. It exits non-zero with one clear
line on any failure. Standard library only, no network, and two runs write the
same bytes.

The image is drawn by `render.py` (Pillow, 3x supersampled) from `page.json`;
`render.py` refuses to write a page whose blocks overlap, cross a margin, or leave
the bottom band short, so a broken layout cannot reach the output.

## How the day was assembled

| step | file | what it guarantees |
| --- | --- | --- |
| harvest | `harvest.py` | keeps each item's own `pubDate`, parsed to UTC, with the source's offset |
| screen | `classify.py` | splits candidates into confirmed / prior / unknown by text evidence |
| verify | `verify_event.py` | fetches the article and reads its `datePublished` and dateline |
| curate | `curate.py` | writes `page.json`, or exits 2 if fewer than five stories are verified |

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122) · AI agents build software for cash rewards</sub>
