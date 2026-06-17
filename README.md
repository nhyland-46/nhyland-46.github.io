# Historile

A web game: you see a world map with a **green marker (birthplace)** and a
**red marker (death place)**, each labeled with a year. Guess the historical
figure those locations and dates belong to.

## Run it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # static SPA in dist/
```

Deploys as a static SPA (Vercel, GitHub Pages, Netlify). No backend.

## How it plays

- **Endless mode** — a random figure from the active difficulty tier.
- **Unlimited guesses** with an autocomplete that suggests names as you type;
  matching is deliberately generous (case/diacritic-insensitive, surname-only,
  typo-tolerant, partial-name).
- **🔀 Shuffle** jumps to a new figure at any time; **Give up** reveals the answer.
- **Difficulty tiers** are slices of the fame-ranked pool: Easy (top 500),
  Medium (top 2,000), Hard (full pool).
- The reveal shows the name, dates, a Wikipedia link, and a portrait when available.

## Data

The app ships with a static `src/data/figures.json` — there is **no live API at
runtime**. Each entry:

```json
{ "name": "Napoleon", "birthYear": 1769, "deathYear": 1821,
  "birthLat": 41.92, "birthLng": 8.74, "deathLat": -15.94, "deathLng": -5.7,
  "fame": 320, "wiki": "https://en.wikipedia.org/wiki/Napoleon" }
```

`fame` is the Wikidata sitelink count (notability proxy) and drives both the
difficulty tiers and autocomplete ranking. `image` and `wiki` are optional.

### Rebuilding the dataset

`scripts/fetch_data.py` pulls the full pool (~5,000 figures) from Wikidata's
SPARQL endpoint and overwrites `figures.json`:

```bash
npm run fetch-data   # or: python3 scripts/fetch_data.py
```

It runs two passes — a paged core query (person, dates, coordinates, fame),
then a batched enrichment pass for portraits (`P18`) and Wikipedia links — and
respects rate limits with backoff.

> **Note:** the repo currently ships a curated ~50-figure seed dataset. The full
> fetch was blocked at build time by an active Wikidata Query Service outage
> (`HTTP 504` / `429: rate-limiting to 1 req/min`). Re-run `npm run fetch-data`
> once [query.wikidata.org](https://query.wikidata.org) is healthy to populate
> the full pool.

## Stack

React + Vite + Tailwind. The map is an SVG world (`world-atlas` TopoJSON)
projected with `d3-geo` (`geoNaturalEarth1`) — flat, no tiles. Autocomplete
fuzzy matching uses Fuse.js. Markers that land on the same spot (born and died
in one city) are automatically nudged apart with a dashed connector.
