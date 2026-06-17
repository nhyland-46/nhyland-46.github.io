#!/usr/bin/env python3
"""Backfill portraits + Wikipedia links into figures.json.

Two-stage, best-effort, idempotent (figures that already have both fields are
skipped, and the file is rewritten at the end):

  1. PRIMARY  -- English Wikipedia REST summary API, looked up by name. Fast and
     reliable; covers names whose Wikidata label matches the article title.

  2. FALLBACK -- for names the REST step can't resolve (disambiguation pages like
     "Victoria"/"Seneca", or bad labels like "TutanKhamun"), search Wikidata's
     Action API for the entity, pick the *human* whose birth year matches this
     figure (so "Victoria" -> Queen Victoria, not the Australian state), read its
     English sitelink + P18 image, then summarise that exact title.

Both APIs are independent of the often-overloaded Wikidata Query Service.

Run:  python3 scripts/enrich_images.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WD_API = "https://www.wikidata.org/w/api.php"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"
USER_AGENT = "HistorileBuilder/1.0 (https://github.com/historile; nhyland46@gmail.com)"
FIG_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "data", "figures.json")
WORKERS = 4  # gentle: avoids the rate-limit/timeout storms that lost rows last time


def _get_json(url, attempts=5):
    """GET JSON with patient backoff on 429/5xx/timeout. None on give-up."""
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(3 * (attempt + 1))  # 429 / 5xx
        except (urllib.error.URLError, TimeoutError):
            time.sleep(3 * (attempt + 1))
    return None


def summary(title):
    """(image, wiki) from the REST summary of an exact title/name. ( ,  ) on miss."""
    data = _get_json(SUMMARY + urllib.parse.quote(title.replace(" ", "_"), safe=""))
    if not data or data.get("type") == "disambiguation":
        return None, None
    img = (data.get("thumbnail") or {}).get("source") or (
        data.get("originalimage") or {}
    ).get("source")
    wiki = ((data.get("content_urls") or {}).get("desktop") or {}).get("page")
    return img, wiki


def _year(time_value):
    """Wikidata time '+1819-05-24T..' -> 1819 ; '-0004-..' -> -4. None if bad."""
    if not time_value:
        return None
    neg = time_value.startswith("-")
    body = time_value.lstrip("+-")
    head = body.split("-", 1)[0]
    return (-int(head) if neg else int(head)) if head.isdigit() else None


def wikidata_fallback(name, birth_year):
    """Resolve an ambiguous/mismatched name via Wikidata, return (image, wiki)."""
    search = _get_json(
        WD_API + "?" + urllib.parse.urlencode({
            "action": "wbsearchentities", "search": name, "language": "en",
            "uselang": "en", "type": "item", "limit": 7, "format": "json",
        })
    )
    ids = [hit["id"] for hit in (search or {}).get("search", [])]
    if not ids:
        return None, None

    ent = _get_json(
        WD_API + "?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(ids),
            "props": "claims|sitelinks", "sitefilter": "enwiki", "format": "json",
        })
    )
    entities = (ent or {}).get("entities", {})

    humans = []
    for qid in ids:  # keep search-relevance order
        e = entities.get(qid)
        if not e:
            continue
        claims = e.get("claims", {})
        p31 = claims.get("P31", [])
        is_human = any(
            (c.get("mainsnak", {}).get("datavalue", {}).get("value", {}) or {}).get("id") == "Q5"
            for c in p31
        )
        if not is_human:
            continue
        by = None
        for c in claims.get("P569", []):
            by = _year((c.get("mainsnak", {}).get("datavalue", {}).get("value", {}) or {}).get("time"))
            if by is not None:
                break
        title = (e.get("sitelinks", {}).get("enwiki", {}) or {}).get("title")
        p18 = None
        for c in claims.get("P18", []):
            p18 = (c.get("mainsnak", {}).get("datavalue", {}) or {}).get("value")
            if p18:
                break
        humans.append({"by": by, "title": title, "p18": p18})

    if not humans:
        return None, None
    # Prefer a birth-year match (strong disambiguator); else accept a lone human.
    match = next((h for h in humans if h["by"] is not None and abs(h["by"] - birth_year) <= 1), None)
    if match is None:
        match = humans[0] if len(humans) == 1 else None
    if match is None:
        return None, None

    img, wiki = (None, None)
    if match["title"]:
        img, wiki = summary(match["title"])  # clean thumbnail + canonical URL
        if not wiki:
            wiki = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
                match["title"].replace(" ", "_"), safe=""
            )
    if not img and match["p18"]:
        img = FILEPATH + urllib.parse.quote(match["p18"].replace(" ", "_"), safe="")
    return img, wiki


def main():
    with open(FIG_PATH, encoding="utf-8") as f:
        figures = json.load(f)

    todo = [fig for fig in figures if not (fig.get("image") and fig.get("wiki"))]
    print(f"{len(figures)} figures, {len(todo)} need enrichment", file=sys.stderr)

    done = 0
    fb_hits = 0

    def work(fig):
        nonlocal done, fb_hits
        img, wiki = summary(fig["name"])
        if not (img and wiki):  # primary missed something -> try Wikidata fallback
            fimg, fwiki = wikidata_fallback(fig["name"], fig.get("birthYear", 0))
            if (fimg or fwiki) and not (img and wiki):
                fb_hits += 1
            img = img or fimg
            wiki = wiki or fwiki
        if img and "image" not in fig:
            fig["image"] = img
        if wiki and "wiki" not in fig:
            fig["wiki"] = wiki
        done += 1
        if done % 25 == 0:
            print(f"  {done}/{len(todo)} (fallback recovered {fb_hits})", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pool.map(work, todo)

    with open(FIG_PATH, "w", encoding="utf-8") as f:
        json.dump(figures, f, ensure_ascii=False, separators=(",", ":"))

    img_total = sum(1 for fig in figures if fig.get("image"))
    wiki_total = sum(1 for fig in figures if fig.get("wiki"))
    still = [fig["name"] for fig in figures if not fig.get("image")]
    print(f"[done] {img_total}/{len(figures)} images, {wiki_total}/{len(figures)} wiki links",
          file=sys.stderr)
    print(f"[still imageless] {len(still)}: {', '.join(still)}", file=sys.stderr)


if __name__ == "__main__":
    main()
