#!/usr/bin/env python3
"""Fetch the Historile dataset from Wikidata's SPARQL endpoint.

Pulls humans that have BOTH a birth place/date and a death place/date with
coordinates, ranked by sitelink count (a proxy for fame). Writes a static
JSON file the app ships with -- there is no live API at runtime.

Two passes, because the OPTIONAL image/article joins are too heavy to run
inline against the geo joins (they 504):
  1. core  -- person, label, dates, coords, fame  (paged, fame-ordered)
  2. enrich -- image (P18) + English Wikipedia URL, batched over the QIDs

The endpoint is sometimes rate-limited to 1 req/min during outages, so every
request retries with long backoff and honours an explicit 429.

Run:  python3 scripts/fetch_data.py
Out:  src/data/figures.json
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "HistorileBuilder/1.0 (https://github.com/historile; nhyland46@gmail.com)"

SITELINK_FLOOR = 30       # pool size knob. Lower -> more obscure figures.
PAGE_SIZE = 300           # core rows per request (smaller survives an overloaded endpoint)
TARGET_ROWS = 5000        # stop once we have this many raw rows
ENRICH_BATCH = 200        # QIDs per enrichment request
POLITE_WAIT = 3           # seconds between successful requests (raised to 60 on 429)
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "data", "figures.json")

CORE_QUERY = """
SELECT ?person ?personLabel ?birthDate ?deathDate
       ?birthLat ?birthLng ?deathLat ?deathLng ?sitelinks
WHERE {{
  ?person wdt:P31 wd:Q5 ;
          wdt:P569 ?birthDate ;
          wdt:P570 ?deathDate ;
          wdt:P19 ?birthPlace ;
          wdt:P20 ?deathPlace ;
          wikibase:sitelinks ?sitelinks .
  ?birthPlace p:P625/psv:P625 [ wikibase:geoLatitude ?birthLat ;
                                wikibase:geoLongitude ?birthLng ] .
  ?deathPlace p:P625/psv:P625 [ wikibase:geoLatitude ?deathLat ;
                                wikibase:geoLongitude ?deathLng ] .
  FILTER(?sitelinks >= {floor})
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
ORDER BY DESC(?sitelinks) ?person
LIMIT {limit} OFFSET {offset}
"""

ENRICH_QUERY = """
SELECT ?person ?image ?article WHERE {{
  VALUES ?person {{ {values} }}
  OPTIONAL {{ ?person wdt:P18 ?image . }}
  OPTIONAL {{
    ?article schema:about ?person ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }}
}}
"""

# global so the polite delay can lengthen after we get rate-limited
_polite_wait = POLITE_WAIT


def run_query(query, attempts=6):
    """POST one query. Retries 429/504/5xx/timeouts with long backoff."""
    global _polite_wait
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _polite_wait = max(_polite_wait, 62)  # endpoint asked for 1 req/min
                wait = 62
            else:
                wait = 15 * (attempt + 1)
            print(f"  ! HTTP {e.code} -- waiting {wait}s", file=sys.stderr)
        except (urllib.error.URLError, TimeoutError) as e:
            wait = 15 * (attempt + 1)
            print(f"  ! {e} -- waiting {wait}s", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError("query failed after retries")


def parse_year(value):
    """'1769-08-15T00:00:00Z' -> 1769 ; '-0044-03-15T...' -> -44 (BCE). None if bad."""
    if not value:
        return None
    neg = value.startswith("-")
    body = value[1:] if neg else value
    year_str = body.split("-", 1)[0]
    if not year_str.isdigit():
        return None
    year = int(year_str)
    return -year if neg else year


def fetch_core():
    rows = []
    offset = 0
    while len(rows) < TARGET_ROWS:
        print(f"[core] offset {offset} ...", file=sys.stderr)
        try:
            page = run_query(CORE_QUERY.format(floor=SITELINK_FLOOR, limit=PAGE_SIZE, offset=offset))
        except RuntimeError as e:
            # WDQS is flaky right now: a single page exhausting its retries must
            # NOT discard everything we already gathered. Keep the partial pool.
            print(f"  ! page at offset {offset} gave up ({e}); keeping {len(rows)} rows so far",
                  file=sys.stderr)
            break
        if not page:
            break
        rows.extend(page)
        offset += PAGE_SIZE
        if len(page) < PAGE_SIZE:
            break  # end of pool
        time.sleep(_polite_wait)
    return rows


def clean(rows):
    """Dedupe by QID, drop bad/missing dates, return (figures, qid_order_map)."""
    seen = set()
    figures = []
    qid_of = {}
    dropped = 0
    for r in rows:
        qid = r["person"]["value"].rsplit("/", 1)[-1]
        if qid in seen:
            continue
        name = r.get("personLabel", {}).get("value", "")
        if not name or name == qid:
            dropped += 1
            continue
        by = parse_year(r.get("birthDate", {}).get("value"))
        dy = parse_year(r.get("deathDate", {}).get("value"))
        if by is None or dy is None or by > dy:
            dropped += 1
            continue
        try:
            fig = {
                "name": name,
                "birthYear": by,
                "deathYear": dy,
                "birthLat": round(float(r["birthLat"]["value"]), 4),
                "birthLng": round(float(r["birthLng"]["value"]), 4),
                "deathLat": round(float(r["deathLat"]["value"]), 4),
                "deathLng": round(float(r["deathLng"]["value"]), 4),
                "fame": int(r["sitelinks"]["value"]),
            }
        except (KeyError, ValueError):
            dropped += 1
            continue
        seen.add(qid)
        qid_of[qid] = fig
        figures.append(fig)
    print(f"[clean] kept {len(figures)}, dropped {dropped}", file=sys.stderr)
    return figures, qid_of


def enrich(qid_of):
    """Best-effort: attach image + wiki URL. Never fails the whole run."""
    qids = list(qid_of.keys())
    for i in range(0, len(qids), ENRICH_BATCH):
        batch = qids[i:i + ENRICH_BATCH]
        print(f"[enrich] {i}/{len(qids)} ...", file=sys.stderr)
        values = " ".join(f"wd:{q}" for q in batch)
        try:
            page = run_query(ENRICH_QUERY.format(values=values))
        except RuntimeError as e:
            print(f"  ! enrich batch failed ({e}); skipping", file=sys.stderr)
            continue
        for r in page:
            qid = r["person"]["value"].rsplit("/", 1)[-1]
            fig = qid_of.get(qid)
            if not fig:
                continue
            if "image" in r and "image" not in fig:
                fig["image"] = r["image"]["value"]
            if "article" in r and "wiki" not in fig:
                fig["wiki"] = r["article"]["value"]
        time.sleep(_polite_wait)


def write(figures):
    figures.sort(key=lambda f: f["fame"], reverse=True)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(figures, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[write] {len(figures)} figures -> {os.path.relpath(OUT_PATH)}", file=sys.stderr)


# Below this, assume the endpoint failed too early to be worth shipping and keep
# whatever figures.json already exists (e.g. the curated seed).
MIN_KEEP = 60


def main():
    rows = fetch_core()
    print(f"[core] {len(rows)} raw rows", file=sys.stderr)
    figures, qid_of = clean(rows)
    if len(figures) < MIN_KEEP:
        print(f"[abort] only {len(figures)} figures (< {MIN_KEEP}); leaving existing "
              f"{os.path.relpath(OUT_PATH)} untouched. Re-run when WDQS is healthier.",
              file=sys.stderr)
        return
    write(figures)          # write core first so a failed enrich still leaves data
    enrich(qid_of)
    write(figures)          # rewrite with enrichment
    print("[done]", file=sys.stderr)


if __name__ == "__main__":
    main()
