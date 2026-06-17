import { useEffect, useMemo, useState } from "react";
import WorldMap from "./components/WorldMap.jsx";
import GuessInput from "./components/GuessInput.jsx";
import {
  TIERS,
  tierPool,
  pickRandom,
  DEFAULT_TIER_SIZE,
  TIER_SIZE_OPTIONS,
} from "./lib/game.js";
import { isCorrect } from "./lib/match.js";
import { availableHints } from "./lib/hints.js";

export default function App() {
  const [tier, setTier] = useState("easy");
  const [tierSize, setTierSize] = useState(DEFAULT_TIER_SIZE);
  const [figure, setFigure] = useState(() => pickRandom("easy"));
  const [guesses, setGuesses] = useState([]); // { text, correct }
  const [solved, setSolved] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [stats, setStats] = useState({ solved: 0, played: 0, guesses: 0, hints: 0 });
  const [hintCount, setHintCount] = useState(0);

  const pool = useMemo(() => tierPool(tier, tierSize), [tier, tierSize]);
  const hints = useMemo(() => availableHints(figure), [figure]);
  const done = solved || revealed;

  function startRound(nextTier, nextSize, avoidName) {
    setFigure(pickRandom(nextTier, avoidName, nextSize));
    setGuesses([]);
    setSolved(false);
    setRevealed(false);
    setHintCount(0);
  }

  function nextFigure(nextTier = tier) {
    startRound(nextTier, tierSize, figure?.name);
  }

  function changeTier(t) {
    setTier(t);
    setStats({ solved: 0, played: 0, guesses: 0, hints: 0 });
    startRound(t, tierSize);
  }

  // Changing the pool size shifts every tier's band, so treat it like a fresh
  // difficulty: reset the session stats and draw a new figure.
  function changeTierSize(size) {
    setTierSize(size);
    setStats({ solved: 0, played: 0, guesses: 0, hints: 0 });
    startRound(tier, size);
  }

  function handleGuess(text) {
    if (done || !figure) return;
    const correct = isCorrect(text, figure);
    setGuesses((g) => [...g, { text, correct }]);
    setStats((s) => ({
      ...s,
      guesses: s.guesses + 1,
      solved: correct ? s.solved + 1 : s.solved,
      played: correct ? s.played + 1 : s.played,
    }));
    if (correct) setSolved(true);
  }

  function giveUp() {
    if (done) return;
    setRevealed(true);
    setStats((s) => ({ ...s, played: s.played + 1 }));
  }

  if (!figure) {
    return (
      <div className="mx-auto max-w-md p-6 text-center text-gray-600">
        <h1 className="mb-2 text-2xl font-bold">Historile</h1>
        <p>
          No figures loaded yet. Run <code>npm run fetch-data</code> to build the
          dataset, then reload.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-full max-w-2xl flex-col gap-4 px-4 py-5">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-extrabold tracking-tight">Historile</h1>
        <div className="text-right text-xs leading-tight text-gray-500">
          <div className="text-sm">{stats.solved}/{stats.played} solved</div>
          <div>
            {stats.guesses} guesses · {stats.hints} hints
          </div>
        </div>
      </header>

      <p className="-mt-2 text-sm text-gray-500">
        Green is birth, red is death. Guess the historical figure.
      </p>

      {/* difficulty */}
      <div className="flex gap-2">
        {Object.entries(TIERS).map(([key, t]) => (
          <button
            key={key}
            onClick={() => changeTier(key)}
            className={
              "rounded-full px-3 py-1 text-sm font-medium transition " +
              (tier === key
                ? "bg-gray-900 text-white"
                : "bg-gray-200 text-gray-700 hover:bg-gray-300")
            }
          >
            {t.label}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-1 self-center text-xs text-gray-400">
          <span>figures/tier</span>
          <select
            value={tierSize}
            onChange={(e) => changeTierSize(Number(e.target.value))}
            className="rounded border border-gray-200 bg-white px-1 py-0.5 text-gray-600"
          >
            {TIER_SIZE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="overflow-hidden rounded-2xl shadow-sm ring-1 ring-gray-200">
        <WorldMap figure={figure} />
      </div>

      {/* reveal panel */}
      {done && (
        <div
          className={
            "flex items-center gap-4 rounded-2xl p-4 ring-1 " +
            (solved
              ? "bg-green-50 ring-green-200"
              : "bg-red-50 ring-red-200")
          }
        >
          {figure.image && (
            <img
              src={thumb(figure.image)}
              alt={figure.name}
              className="h-20 w-20 shrink-0 rounded-lg object-cover"
              loading="lazy"
            />
          )}
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {solved ? "Correct!" : "The answer was"}
            </div>
            <div className="truncate text-xl font-bold">{figure.name}</div>
            <div className="text-sm text-gray-500">
              {fmtYear(figure.birthYear)} – {fmtYear(figure.deathYear)}
              {figure.occupation && (
                <span className="capitalize"> · {figure.occupation.toLowerCase()}</span>
              )}
            </div>
            {figure.wiki && (
              <a
                href={figure.wiki}
                target="_blank"
                rel="noreferrer"
                className="text-sm font-medium text-blue-600 hover:underline"
              >
                Wikipedia →
              </a>
            )}
          </div>
        </div>
      )}

      {/* input */}
      {!done && (
        <GuessInput pool={pool} disabled={done} onGuess={handleGuess} />
      )}

      {/* hints */}
      {!done && hints.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {hints.slice(0, hintCount).map((h) => (
            <span
              key={h.label}
              className="inline-flex items-center gap-2 rounded-lg bg-amber-100 px-3 py-1 text-sm text-amber-900"
            >
              <span className="font-semibold">{h.label}:</span>
              {h.type === "image" ? (
                <img
                  src={thumb(h.value)}
                  alt="portrait hint"
                  className="h-14 w-14 rounded object-cover"
                  loading="lazy"
                />
              ) : (
                <span>{h.value}</span>
              )}
            </span>
          ))}
          {hintCount < hints.length && (
            <button
              onClick={() => {
                setHintCount((c) => c + 1);
                setStats((s) => ({ ...s, hints: s.hints + 1 }));
              }}
              className="rounded-lg px-3 py-1 text-sm font-medium text-amber-700 hover:bg-amber-50"
            >
              💡 {hintCount === 0 ? "Hint" : "Another hint"} ({hintCount}/
              {hints.length})
            </button>
          )}
        </div>
      )}

      {/* guess history */}
      {guesses.length > 0 && (
        <ul className="flex flex-col gap-1">
          {guesses.map((g, i) => (
            <li
              key={i}
              className={
                "flex items-center justify-between rounded-lg px-3 py-2 text-sm " +
                (g.correct ? "bg-green-100" : "bg-gray-100")
              }
            >
              <span className="truncate">{g.text}</span>
              <span>{g.correct ? "✓" : "✗"}</span>
            </li>
          ))}
        </ul>
      )}

      {/* actions */}
      <div className="mt-auto flex gap-2 pt-2">
        {!done ? (
          <>
            <button
              onClick={() => nextFigure()}
              className="flex-1 rounded-xl bg-gray-200 px-4 py-3 font-semibold text-gray-700 hover:bg-gray-300"
            >
              🔀 Shuffle
            </button>
            <button
              onClick={giveUp}
              className="rounded-xl px-4 py-3 font-semibold text-gray-500 hover:text-gray-800"
            >
              Give up
            </button>
          </>
        ) : (
          <button
            onClick={() => nextFigure()}
            className="flex-1 rounded-xl bg-gray-900 px-4 py-3 font-semibold text-white hover:bg-gray-800"
          >
            Next figure →
          </button>
        )}
      </div>
    </div>
  );
}

// The Wikipedia REST API already returns a ready-sized (~330px) thumbnail, so
// use it as-is. Only Wikidata Special:FilePath URLs (full-size) need a width hint.
function thumb(url, size = 160) {
  if (!url) return url;
  if (/\/\d+px-[^/]+$/.test(url)) return url; // already a Wikimedia thumbnail
  return url.includes("?") ? `${url}&width=${size}` : `${url}?width=${size}`;
}

function fmtYear(year) {
  return year < 0 ? `${Math.abs(year)} BC` : `${year}`;
}
