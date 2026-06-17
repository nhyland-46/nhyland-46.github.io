#!/usr/bin/env python3
"""Re-rank figures.json by a blend of Wikipedia pageviews + Wikidata sitelinks.

Sitelink count (the old `fame`) rewards cross-language encyclopedic coverage,
which over-ranks saints, nobility, and nationally-but-not-globally famous people.
Actual pageviews track recognition far better. We blend the two so recognition
dominates while sitelinks keep the ordering stable against recent-news spikes.

For each figure we add:
  - `views`     : total English Wikipedia views over a fixed 3-year window
  - `sitelinks` : the former `fame` value (raw Wikidata sitelink count)
  - `fame`      : blended 0-1000 score, used for tier slicing + autocomplete rank

The array is re-sorted by `fame` (descending). Pure re-rank: no figure dropped.

Run:  python3 scripts/blend_fame.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PV_BASE = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
           "en.wikipedia/all-access/all-agents/")
WINDOW = ("2022010100", "2024123100")  # fixed 3-year window -> deterministic
W_PV = 0.85  # pageviews weight (vs 0.15 sitelinks). Higher -> recognition matters more.
USER_AGENT = "HistorileBuilder/1.0 (https://github.com/historile; nhyland46@gmail.com)"
FIG_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "data", "figures.json")
WORKERS = 6


def title_from_wiki(url, name):
    """Canonical article title from the stored wiki URL (falls back to name)."""
    if url and "/wiki/" in url:
        return urllib.parse.unquote(url.rsplit("/wiki/", 1)[1])
    return name


def pageviews(title):
    """Total EN pageviews over WINDOW, or 0 on miss."""
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = f"{PV_BASE}{t}/monthly/{WINDOW[0]}/{WINDOW[1]}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                items = json.load(resp).get("items", [])
            return sum(i.get("views", 0) for i in items)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 0  # article has no pageview record
            time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 * (attempt + 1))
    return 0


def percentile_ranks(figures, key):
    """Map each figure index -> percentile rank (0=lowest, 1=highest) for `key`."""
    n = len(figures)
    order = sorted(range(n), key=lambda i: figures[i][key])
    ranks = [0.0] * n
    for rank, i in enumerate(order):
        ranks[i] = rank / (n - 1) if n > 1 else 1.0
    return ranks


def main():
    with open(FIG_PATH, encoding="utf-8") as f:
        figures = json.load(f)

    # rename the old sitelink-based `fame` -> `sitelinks` (keep the raw signal)
    for fig in figures:
        if "sitelinks" not in fig:
            fig["sitelinks"] = fig.get("fame", 0)

    def fetch_into(targets, workers):
        """Fetch views for `targets` in place. Genuine 0 is essentially impossible
        for a figure with an article, so a 0 is treated as a failure to retry."""
        def work(fig):
            fig["views"] = pageviews(title_from_wiki(fig.get("wiki"), fig["name"]))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(work, targets))

    print(f"Fetching pageviews for {len(figures)} figures ...", file=sys.stderr)
    fetch_into([f for f in figures if not f.get("views")], WORKERS)

    # Repair loop: any 0 is a rate-limited miss, not a real value. Re-fetch the
    # stragglers gently (low concurrency) until they resolve or we plateau.
    for attempt in range(4):
        zeros = [f for f in figures if not f.get("views")]
        if not zeros:
            break
        print(f"  repairing {len(zeros)} zero-view figures (pass {attempt + 1}) ...",
              file=sys.stderr)
        time.sleep(3)
        fetch_into(zeros, 2)
    remaining = [f for f in figures if not f.get("views")]
    if remaining:
        print(f"  ! {len(remaining)} still zero: {', '.join(f['name'] for f in remaining)}",
              file=sys.stderr)

    pv = percentile_ranks(figures, "views")
    sl = percentile_ranks(figures, "sitelinks")
    for i, fig in enumerate(figures):
        fig["fame"] = round(1000 * (W_PV * pv[i] + (1 - W_PV) * sl[i]))

    figures.sort(key=lambda f: f["fame"], reverse=True)

    with open(FIG_PATH, "w", encoding="utf-8") as f:
        json.dump(figures, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[done] re-ranked {len(figures)} figures (W_pv={W_PV})", file=sys.stderr)
    print("Top 12:", ", ".join(f["name"] for f in figures[:12]), file=sys.stderr)


if __name__ == "__main__":
    main()
