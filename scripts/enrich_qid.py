#!/usr/bin/env python3
"""Add portraits + Wikipedia links to figures.json using exact Wikidata QIDs.

Pantheon gives every figure a `wd_id`, so we resolve each one's English
Wikipedia article via Wikidata's Action API (exact -- no name guessing), then
pull a clean thumbnail from the Wikipedia REST summary of that title. Figures
without a QID (or without an English article) fall back to a name lookup.

Run:  python3 scripts/enrich_qid.py
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
from enrich_images import summary, _get_json  # reuse tested REST + retry helpers

WD_API = "https://www.wikidata.org/w/api.php"
FIG_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "data", "figures.json")
WORKERS = 6


def enwiki_titles(qids):
    """{qid: english_article_title} via batched wbgetentities (50/call)."""
    titles = {}
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        url = WD_API + "?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "sitelinks", "sitefilter": "enwiki", "format": "json",
        })
        data = _get_json(url)
        for qid, ent in (data or {}).get("entities", {}).items():
            t = (ent.get("sitelinks", {}).get("enwiki", {}) or {}).get("title")
            if t:
                titles[qid] = t
        print(f"  titles {min(i + 50, len(qids))}/{len(qids)}", file=sys.stderr)
    return titles


def main():
    with open(FIG_PATH, encoding="utf-8") as f:
        figures = json.load(f)

    qids = [f["wd_id"] for f in figures if f.get("wd_id")]
    print(f"{len(figures)} figures, resolving {len(qids)} Wikidata ids ...", file=sys.stderr)
    titles = enwiki_titles(qids)

    done = 0

    def work(fig):
        nonlocal done
        title = titles.get(fig.get("wd_id"))
        if title:
            if "wiki" not in fig:
                fig["wiki"] = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
                    title.replace(" ", "_"), safe=""
                )
            img, _ = summary(title)  # clean thumbnail for the exact article
            if img and "image" not in fig:
                fig["image"] = img
        else:  # no QID / no English article -> best-effort name lookup
            img, wiki = summary(fig["name"])
            if wiki and "wiki" not in fig:
                fig["wiki"] = wiki
            if img and "image" not in fig:
                fig["image"] = img
        done += 1
        if done % 250 == 0:
            print(f"  enriched {done}/{len(figures)}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(work, figures))

    with open(FIG_PATH, "w", encoding="utf-8") as f:
        json.dump(figures, f, ensure_ascii=False, separators=(",", ":"))

    img = sum(1 for f in figures if f.get("image"))
    wiki = sum(1 for f in figures if f.get("wiki"))
    print(f"[done] {img}/{len(figures)} images, {wiki}/{len(figures)} wiki links",
          file=sys.stderr)


if __name__ == "__main__":
    main()
