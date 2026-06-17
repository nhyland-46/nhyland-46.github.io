import { useEffect, useMemo, useRef, useState } from "react";
import { buildSearch, suggest } from "../lib/match.js";

export default function GuessInput({ pool, disabled, onGuess }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef(null);

  const fuse = useMemo(() => buildSearch(pool), [pool]);
  const options = useMemo(
    () => (open ? suggest(fuse, pool, query) : []),
    [fuse, pool, query, open]
  );

  // close the dropdown on outside click
  useEffect(() => {
    function onDocClick(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  useEffect(() => setActive(0), [query]);

  function submit(value) {
    const v = (value ?? query).trim();
    if (!v) return;
    onGuess(v);
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(e) {
    if (!open || options.length === 0) {
      if (e.key === "Enter") submit();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      submit(options[active]?.name);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div ref={boxRef} className="relative">
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          disabled={disabled}
          autoComplete="off"
          spellCheck={false}
          placeholder="Name the historical figure…"
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className="flex-1 rounded-xl border border-gray-300 bg-white px-4 py-3 text-base outline-none focus:border-gray-500 disabled:bg-gray-100 disabled:text-gray-400"
        />
        <button
          type="button"
          disabled={disabled || !query.trim()}
          onClick={() => submit()}
          className="rounded-xl bg-gray-900 px-5 py-3 font-semibold text-white disabled:bg-gray-300"
        >
          Guess
        </button>
      </div>

      {open && options.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg">
          {options.map((opt, i) => (
            <li key={opt.name + opt.birthYear}>
              <button
                type="button"
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => {
                  e.preventDefault(); // keep focus, fire before blur
                  submit(opt.name);
                }}
                className={
                  "flex w-full items-center justify-between px-4 py-2 text-left " +
                  (i === active ? "bg-gray-100" : "bg-white")
                }
              >
                <span className="truncate">{opt.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
