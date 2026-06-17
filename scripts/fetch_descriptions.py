#!/usr/bin/env python3
"""Add Pantheon `description`, `gender`, `famous_for` to the in-play figures (top 900).

These power richer hints: a one-line description ("18th-century German
composer"), gender, and a "famous for" blurb. Only the top 900 by fame are
surfaced in the game, so we only fetch for those. Looked up by exact Wikidata id
via Pantheon's person table. Note `famous_for` embeds the person's name, so the
hint layer redacts it at display time.

Run:  python3 scripts/fetch_descriptions.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.pantheon.world"
USER_AGENT = "HistorileBuilder/1.0 (https://github.com/historile; nhyland46@gmail.com)"
FIG_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "data", "figures.json")
TOP_N = 900
CHUNK = 150


def api_get(path, attempts=5):
    req = urllib.request.Request(API + path, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.load(resp)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"  ! {e} (retry)", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"GET {path} failed")


def main():
    with open(FIG_PATH, encoding="utf-8") as f:
        figures = json.load(f)

    # any figure with a QID that's missing one of the fields (idempotent: skips
    # figures already enriched, so re-running only fills the gaps)
    targets = [
        f for f in figures
        if f.get("wd_id") and not (f.get("description") and f.get("gender") and f.get("famous_for"))
    ]
    print(f"Fetching description + gender + famous_for for {len(targets)} figures ...", file=sys.stderr)

    rows = {}
    qids = [f["wd_id"] for f in targets]
    for i in range(0, len(qids), CHUNK):
        chunk = qids[i:i + CHUNK]
        data = api_get(f"/person?wd_id=in.({','.join(chunk)})&select=wd_id,description,gender,famous_for")
        for r in data:
            rows[r["wd_id"]] = r
        print(f"  {min(i + CHUNK, len(qids))}/{len(qids)}", file=sys.stderr)

    desc = gen = fam = 0
    for fig in targets:
        r = rows.get(fig["wd_id"])
        if not r:
            continue
        if r.get("description"):
            fig["description"] = r["description"]
            desc += 1
        if r.get("gender"):
            fig["gender"] = r["gender"]  # "M" / "F"
            gen += 1
        if r.get("famous_for"):
            fig["famous_for"] = r["famous_for"]
            fam += 1

    with open(FIG_PATH, "w", encoding="utf-8") as f:
        json.dump(figures, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[done] added {desc} descriptions, {gen} genders, {fam} famous_for",
          file=sys.stderr)


if __name__ == "__main__":
    main()
