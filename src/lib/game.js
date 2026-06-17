import figuresData from "../data/figures.json";

// figures.json is fame-ordered (Pantheon HPI, most famous first).
export const figures = figuresData;

// Equal bands off the top of the fame ranking: Easy = #1..N, Medium = next N,
// Hard = next N, where N (the tier size) is player-adjustable. The remainder of
// the scored pool stays in figures.json but isn't surfaced in play.
export const DEFAULT_TIER_SIZE = 300;
// Options must satisfy 3 * size <= figures.length so the bands don't overlap.
export const TIER_SIZE_OPTIONS = [100, 200, 300, 400, 500];

export const TIERS = {
  easy: { label: "Easy" },
  medium: { label: "Medium" },
  hard: { label: "Hard" },
};

const TIER_ORDER = ["easy", "medium", "hard"];

export function tierPool(tier, size = DEFAULT_TIER_SIZE) {
  const i = TIER_ORDER.indexOf(tier);
  if (i < 0) return figures;
  const start = i * size;
  return figures.slice(start, start + size);
}

// Pick a random figure from the tier, avoiding an immediate repeat.
export function pickRandom(tier, avoidName, size = DEFAULT_TIER_SIZE) {
  const pool = tierPool(tier, size);
  if (pool.length === 0) return null;
  if (pool.length === 1) return pool[0];
  let next;
  do {
    next = pool[Math.floor(Math.random() * pool.length)];
  } while (next.name === avoidName);
  return next;
}
