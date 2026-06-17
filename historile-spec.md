# Historile — Project Brief

A daily/endless web game: players see a world map with a **green marker (birthplace)** and a **red marker (death place)**, each labeled with a year, and guess the famous historical figure those locations + dates belong to.

This file is the starting brief for Claude Code. Build it in the order below.

---

## Stack

- **Frontend:** React + Vite + Tailwind
- **Map:** SVG world map with two plotted markers (no tiles — flat stylized look, like the reference). Use a world GeoJSON projected with `d3-geo` (`geoNaturalEarth1` or `geoEquirectangular`).
- **Data source:** Wikidata SPARQL (one-time fetch into a static JSON file — no live API at runtime)
- **Hosting:** TBD. Keep it a static SPA so it deploys cleanly to Vercel or GitHub Pages later. No backend required.

---

## Build order

### 1. Data pipeline (`/scripts/fetch_data.py`)

Pull the dataset once from Wikidata's SPARQL endpoint and write a static JSON the app ships with. Do **not** scrape Wikipedia HTML — use structured Wikidata properties.

Properties needed:
- `P569` birth date → derive `birthYear`
- `P570` death date → derive `deathYear`
- `P19` place of birth → its `P625` coordinates → `birthLat`, `birthLng`
- `P20` place of death → its `P625` coordinates → `deathLat`, `deathLng`
- Sitelink count as a **fame score** (proxy for notability, used for difficulty tiers + autocomplete ranking)

**Starter SPARQL query** (humans with both birth and death coordinates + dates, ordered by fame):

```sparql
SELECT ?person ?personLabel ?birthDate ?deathDate
       ?birthLat ?birthLng ?deathLat ?deathLng ?sitelinks
WHERE {
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
  FILTER(?sitelinks >= 30)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
ORDER BY DESC(?sitelinks)
LIMIT 5000
```

Implementation notes:
- Endpoint: `https://query.wikidata.org/sparql` with `format=json`. Set a descriptive `User-Agent` header (Wikidata requires it or returns 403).
- The `>= 30` sitelink floor controls the size of the pool; lower it for more obscure figures, raise it for only-famous.
- Dedupe people with multiple birth/death places (keep the first, or the one with a coordinate).
- Drop rows where birth/death year is missing or birthYear > deathYear (bad data).
- Output `/src/data/figures.json` as an array of:
  ```json
  { "name": "...", "birthYear": 1769, "deathYear": 1821,
    "birthLat": 41.9, "birthLng": 8.7,
    "deathLat": -15.9, "deathLng": -5.7, "fame": 312 }
  ```

### 2. Difficulty tiers

No extra fetch — slice the fame-ranked list:
- **Easy:** top ~500 (household names)
- **Medium:** top ~2,000
- **Hard:** full ~5,000 pool
Tier is a runtime filter over `figures.json`.

### 3. Game UI

Core loop:
1. Pick a random figure from the active difficulty tier (or a date-seeded one for a daily mode).
2. Render the SVG world map. Plot **green = birthplace** and **red = death place**, each labeled with its year (matching the reference screenshots).
3. **Free-text input with autocomplete** — suggestions come from the names in the active tier. Match case-insensitively, tolerate minor typos (e.g. Fuse.js fuzzy match).
4. On submit: reveal correct/incorrect, show the person's name, and (nice-to-have) a Wikipedia link.
5. Endless/score mode + a daily mode (seed the RNG with the date so everyone gets the same figure).

UI details:
- Markers should visually match the reference: a filled dot inside a ringed circle, green for birth / red for death, year label adjacent.
- Keep the map flat and clean — light landmasses, muted background, no country labels.
- Mobile-first layout (the reference is a vertical phone video).

---

## Reference

Inspired by a TikTok/Instagram format (@solunaaaa16): "Can I name the historical figure from their birth and death?" Two markers, two years, guess the person. Examples seen:
- 1769 (green, Corsica) → 1821 (red, South Atlantic) = Napoleon
- 1879 (green, Europe) → 1940 (red, Mexico) = Trotsky
- 1137 (green, Levant) → 1193 (red, Levant) = Saladin

## Open questions to resolve while building
- Daily puzzle vs endless as the default landing mode?
- How many guesses per figure (1 shot, or 3 tries Wordle-style)?
- Show the years always, or make a hard mode that hides them?
