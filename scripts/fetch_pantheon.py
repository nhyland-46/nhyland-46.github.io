#!/usr/bin/env python3
"""Build figures.json from Pantheon (MIT Media Lab).

Pantheon's HPI (Historical Popularity Index) is purpose-built to rank globally
famous *historical figures* -- a far better fame signal than raw Wikidata
sitelinks. Its public PostgREST API (https://api.pantheon.world) gives us the
whole core record from one reliable source (no Wikidata Query Service):

  person_ranks  -> name, HPI, rank, birth/death year, occupation, both place
                   GeoNames ids (filtered to people with both places + a death year)
  person        -> wd_id (Wikidata QID) for exact image/link enrichment later
  place         -> GeoNames id -> lat/lon

Output: top-N by HPI as src/data/figures.json (image/wiki added by enrich step).

Run:  python3 scripts/fetch_pantheon.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.pantheon.world"
USER_AGENT = "HistorileBuilder/1.0 (https://github.com/historile; nhyland46@gmail.com)"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "data", "figures.json")

TARGET = 1500        # final pool size (most-famous figures with both places)
PULL = 1800          # ranked rows to pull (buffer for unresolved coordinates)
PAGE = 800           # PostgREST rows per request
CHUNK = 200          # ids per batched lookup (keeps URLs short)


def api_get(path, attempts=5):
    req = urllib.request.Request(
        API + path, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.load(resp)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"  ! {e} (retry)", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"GET {path} failed")


def fetch_ranked():
    """Top PULL people by HPI with both places + a death year."""
    flt = ("deathyear=not.is.null&bplace_geonameid=not.is.null"
           "&dplace_geonameid=not.is.null")
    cols = ("id,name,hpi,rank,birthyear,deathyear,occupation,"
            "bplace_geonameid,dplace_geonameid")
    rows = []
    offset = 0
    while len(rows) < PULL:
        page = api_get(f"/person_ranks?{flt}&select={cols}"
                       f"&order=rank.asc&limit={PAGE}&offset={offset}")
        if not page:
            break
        rows.extend(page)
        offset += PAGE
        print(f"  ranked {len(rows)}", file=sys.stderr)
    return rows[:PULL]


def batch_lookup(table, ids, cols):
    """Return {id: row} for ids via PostgREST `in.(...)`, chunked."""
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        joined = ",".join(str(x) for x in chunk)
        rows = api_get(f"/{table}?id=in.({joined})&select={cols}")
        for r in rows:
            out[r["id"]] = r
    return out


def main():
    print("Fetching HPI-ranked people from Pantheon ...", file=sys.stderr)
    ranked = fetch_ranked()

    # wd_id (Wikidata QID) for later exact enrichment
    print("Fetching Wikidata ids ...", file=sys.stderr)
    wd = batch_lookup("person", {r["id"] for r in ranked}, "id,wd_id")

    # resolve every birth/death GeoNames id to coordinates
    print("Resolving place coordinates ...", file=sys.stderr)
    geoids = {r["bplace_geonameid"] for r in ranked} | {r["dplace_geonameid"] for r in ranked}
    places = batch_lookup("place", geoids, "id,lat,lon")

    figures = []
    dropped = 0
    for r in ranked:
        bp = places.get(r["bplace_geonameid"])
        dp = places.get(r["dplace_geonameid"])
        if not bp or not dp or bp.get("lat") is None or dp.get("lat") is None:
            dropped += 1
            continue
        fig = {
            "name": r["name"],
            "birthYear": int(r["birthyear"]),
            "deathYear": int(r["deathyear"]),
            "birthLat": round(float(bp["lat"]), 4),
            "birthLng": round(float(bp["lon"]), 4),
            "deathLat": round(float(dp["lat"]), 4),
            "deathLng": round(float(dp["lon"]), 4),
            "fame": round(float(r["hpi"]), 2),
        }
        if r.get("occupation"):
            fig["occupation"] = r["occupation"]
        qid = (wd.get(r["id"]) or {}).get("wd_id")
        if qid:
            fig["wd_id"] = qid
        figures.append(fig)
        if len(figures) >= TARGET:
            break

    figures.sort(key=lambda f: f["fame"], reverse=True)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(figures, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[done] {len(figures)} figures (dropped {dropped} for missing coords)",
          file=sys.stderr)
    print("Top 12:", ", ".join(f["name"] for f in figures[:12]), file=sys.stderr)


if __name__ == "__main__":
    main()
