#!/usr/bin/env python3
"""Re-rank figures.json toward a US/contemporary player's sense of "famous".

Pantheon's HPI is a global, all-of-history fame signal, so it ranks
internationally- or anciently-famous figures (Ferdinand Marcos, Numa Pompilius)
above people a US player recognizes more readily. We nudge the ranking with two
tunable, additive boosts on top of HPI:

  ANGLO_BONUS -- flat boost for anyone *born* in an English-speaking country
                 (US/UK/Ireland/Canada/Australia/NZ) -- birthplace, not death-
                 place, so Marcos (died Honolulu, born Philippines) isn't boosted.
  recency    -- a ramp that boosts more-recent deaths (living memory beats
                antiquity), 0 before RECENCY_START, full at RECENCY_FULL.

`hpi` preserves the original score; `fame` is the boosted ranking score used for
tier slicing + autocomplete. Birth country is fetched once from Pantheon (by
Wikidata id) and cached as `birthCountry`, so re-tuning the weights is instant.

Run:  python3 scripts/rescore_us.py
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

# Birth countries treated as "familiar to an English-speaking player". US-born
# figures get a larger bump than the rest of the Anglosphere.
ENGLISH_SPEAKING = {
    "United States", "United Kingdom", "Ireland",
    "Canada", "Australia", "New Zealand",
}
US_BONUS = 12.0       # HPI points for US-born figures (double the rest of the Anglosphere)
ANGLO_BONUS = 6.0     # HPI points for other English-speaking countries
RECENCY_MAX = 8.0     # max HPI points for the most recent deaths
RECENCY_START = 1900  # deaths at/before this get no recency boost
RECENCY_FULL = 2025   # deaths at/after this get the full RECENCY_MAX
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


def recency_boost(death_year):
    if death_year <= RECENCY_START:
        return 0.0
    frac = min((death_year - RECENCY_START) / (RECENCY_FULL - RECENCY_START), 1.0)
    return RECENCY_MAX * frac


def main():
    with open(FIG_PATH, encoding="utf-8") as f:
        figures = json.load(f)

    for fig in figures:
        fig.setdefault("hpi", fig.get("fame", 0))  # preserve original HPI once

    # fetch + cache birth country for any figure missing it
    need = [f for f in figures if "birthCountry" not in f and f.get("wd_id")]
    if need:
        print(f"Fetching birth country for {len(need)} figures ...", file=sys.stderr)
        by_qid = {}
        qids = [f["wd_id"] for f in need]
        for i in range(0, len(qids), CHUNK):
            chunk = qids[i:i + CHUNK]
            rows = api_get(f"/person?wd_id=in.({','.join(chunk)})&select=wd_id,bplace_country")
            for r in rows:
                by_qid[r["wd_id"]] = r.get("bplace_country")
            print(f"  {min(i + CHUNK, len(qids))}/{len(qids)}", file=sys.stderr)
        for fig in need:
            fig["birthCountry"] = by_qid.get(fig["wd_id"])

    anglo = 0
    for fig in figures:
        boost = recency_boost(fig["deathYear"])
        if fig.get("birthCountry") == "United States":
          boost += US_BONUS
          anglo += 1
        elif fig.get("birthCountry") in ENGLISH_SPEAKING:
            boost += ANGLO_BONUS
            anglo += 1
        fig["fame"] = round(fig["hpi"] + boost, 2)

    figures.sort(key=lambda f: f["fame"], reverse=True)
    with open(FIG_PATH, "w", encoding="utf-8") as f:
        json.dump(figures, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[done] anglo +{ANGLO_BONUS} ({anglo} figures), "
          f"recency +{RECENCY_MAX} ramp {RECENCY_START}->{RECENCY_FULL}", file=sys.stderr)
    print("New top 15:", ", ".join(f["name"] for f in figures[:15]), file=sys.stderr)


if __name__ == "__main__":
    main()
