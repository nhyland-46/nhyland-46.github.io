// Flag figures whose "Known for" blurb is circular -- i.e. it just restates the
// occupation ("most famous for being a boxer", "for his paintings") and adds no
// specific achievement. Those get `kfCircular: true`, and the hint layer shows
// the Description for them instead of Known for.
//
// Heuristic: take the same redacted first-sentence we'd show as the hint, strip
// boilerplate + the occupation's own words, and if almost nothing distinctive
// remains, it's circular. Runs over all figures.
//
// Run:  node scripts/flag_circular.js

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { knownFor } from "../src/lib/hints.js"; // reuse the exact hint logic

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIG_PATH = path.join(__dirname, "..", "src", "data", "figures.json");

// Words that carry no identifying content on their own.
const FILLER = new Set([
  "most", "famous", "for", "being", "a", "an", "the", "his", "her", "their", "its",
  "and", "or", "of", "to", "as", "in", "on", "was", "were", "is", "are", "who",
  "known", "professional", "work", "works", "career", "world", "best", "one",
  "first", "people", "person", "she", "he", "they", "with",
]);

// Nationality/demonym words -- a known-for that's just "an American singer" is
// still circular (the Description already conveys nationality + role).
const NATIONALITY = new Set([
  "american", "english", "british", "french", "german", "italian", "spanish",
  "dutch", "russian", "chinese", "japanese", "indian", "greek", "roman",
  "egyptian", "persian", "mexican", "brazilian", "canadian", "australian",
  "irish", "scottish", "welsh", "polish", "swedish", "norwegian", "danish",
  "austrian", "swiss", "portuguese", "turkish", "arab", "jewish", "jamaican",
  "korean", "vietnamese", "iranian", "israeli", "hungarian", "czech", "belgian",
]);

// Generic profession words (+ common derived/related forms) that, by themselves,
// just echo the occupation rather than name an achievement.
const PROFESSION = new Set([
  "singer", "song", "songs", "songwriter", "actor", "actress", "acting", "star",
  "musician", "music", "band", "painter", "painting", "paintings", "paint",
  "artist", "art", "artworks", "writer", "writing", "writings", "novelist",
  "novels", "poet", "poetry", "poems", "author", "books", "boxer", "boxing",
  "athlete", "athletics", "player", "footballer", "football", "soccer", "tennis",
  "golfer", "basketball", "dancer", "dancing", "composer", "composing",
  "sculptor", "sculpture", "director", "filmmaker", "comedian", "rapper",
  "photographer", "model", "wrestler", "swimmer", "cyclist", "skater",
]);

function isCircular(fig) {
  if (!fig.occupation || !fig.famous_for || !fig.description) return false;
  const kf = knownFor(fig);
  if (!kf) return true; // no usable "Known for" -> fall back to Description
  const occWords = new Set(fig.occupation.toLowerCase().split(/\s+/));
  const remaining = kf
    .toLowerCase()
    .replace(/[^a-z\s]/g, " ")
    .split(/\s+/)
    .filter(
      (w) =>
        w.length >= 3 &&
        !FILLER.has(w) &&
        !PROFESSION.has(w) &&
        !NATIONALITY.has(w) &&
        !occWords.has(w)
    );
  // nothing distinctive left at all -> it only named the profession/nationality
  return remaining.length === 0;
}

const figures = JSON.parse(fs.readFileSync(FIG_PATH, "utf8"));
let flagged = 0;
const examples = [];
for (const fig of figures) {
  if (isCircular(fig)) {
    fig.kfCircular = true;
    flagged++;
    if (examples.length < 20) examples.push(`${fig.name} — "${knownFor(fig)}" -> ${fig.description}`);
  } else if (fig.kfCircular) {
    delete fig.kfCircular; // idempotent: clear a stale flag if rerun
  }
}
fs.writeFileSync(FIG_PATH, JSON.stringify(figures));
console.log(`Flagged ${flagged}/${figures.length} circular "Known for" figures.`);
console.log("Examples (will show Description instead):");
examples.forEach((e) => console.log("  - " + e));
