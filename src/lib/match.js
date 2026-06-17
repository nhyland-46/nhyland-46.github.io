import Fuse from "fuse.js";

// Lowercase, strip diacritics, drop punctuation, collapse whitespace.
export function normalize(str) {
  return (str || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "") // strip combining diacritics
    .toLowerCase()
    .replace(/[.,'"`’()]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Cheap Levenshtein for short typo tolerance on a single guess.
function editDistance(a, b) {
  const m = a.length;
  const n = b.length;
  if (Math.abs(m - n) > 2) return 3; // early out: too far to matter
  const dp = Array.from({ length: m + 1 }, (_, i) => i);
  for (let j = 1; j <= n; j++) {
    let prev = dp[0];
    dp[0] = j;
    for (let i = 1; i <= m; i++) {
      const tmp = dp[i];
      dp[i] = Math.min(
        dp[i] + 1,
        dp[i - 1] + 1,
        prev + (a[i - 1] === b[j - 1] ? 0 : 1)
      );
      prev = tmp;
    }
  }
  return dp[m];
}

// Is `guess` an acceptable answer for `figure`? Deliberately generous:
// exact match, last-name / first-name match, "name contains guess as words",
// or a near-miss typo on the full name.
export function isCorrect(guess, figure) {
  const g = normalize(guess);
  if (!g) return false;
  const name = normalize(figure.name);
  if (g === name) return true;

  const nameTokens = name.split(" ").filter(Boolean);
  const guessTokens = g.split(" ").filter(Boolean);

  // Single-word guess that matches any meaningful name token (e.g. "napoleon",
  // "bonaparte", "trotsky"). Ignore very short tokens to avoid false hits.
  if (guessTokens.length === 1 && g.length >= 4) {
    if (nameTokens.includes(g)) return true;
    // typo tolerance against the last name
    const last = nameTokens[nameTokens.length - 1];
    if (last && last.length >= 4 && editDistance(g, last) <= 1) return true;
  }

  // Token-subset either direction (order-free):
  //  - guess is a subset of the name: "martin luther king" -> "Martin Luther King Jr."
  //  - name is a subset of the guess: "Napoleon Bonaparte" -> "Napoleon"
  // Ignore tokens shorter than 3 chars (initials, particles) on the name side.
  if (guessTokens.length >= 2) {
    const guessSubset = guessTokens.every((t) => nameTokens.includes(t));
    const meaningfulName = nameTokens.filter((t) => t.length >= 3);
    const nameSubset =
      meaningfulName.length > 0 &&
      meaningfulName.every((t) => guessTokens.includes(t));
    if (guessSubset || nameSubset) return true;
  }

  // Typo tolerance on the whole name (scaled to length).
  const tol = name.length > 12 ? 2 : 1;
  if (editDistance(g, name) <= tol) return true;

  return false;
}

// Build an autocomplete index over a pool of figures.
export function buildSearch(pool) {
  return new Fuse(pool, {
    keys: ["name"],
    threshold: 0.4, // fuzzy but not wild
    ignoreLocation: true,
    minMatchCharLength: 2,
  });
}

// Suggestions for the current query, fame-ordered within the match set.
export function suggest(fuse, pool, query, limit = 7) {
  const q = query.trim();
  if (q.length < 2) return [];
  const hits = fuse.search(q, { limit: limit * 3 }).map((h) => h.item);
  // Fuse orders by relevance; nudge famous figures up so the obvious answer
  // surfaces first when several names are similar.
  hits.sort((a, b) => b.fame - a.fame);
  return hits.slice(0, limit);
}
