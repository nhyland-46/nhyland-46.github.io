// Progressive hints, revealed one at a time in order (vague -> revealing). Each
// definition derives a value from the current figure, or returns null when it
// doesn't apply (then that hint is skipped). Add a new hint by appending here.
//
// A hint is { label, get(figure), type? }. `get` returns a string value, or an
// object { value, label?, type? } to override the label/type for that figure
// (used so circular "Known for" blurbs fall back to the Description), or null.
// type "image" renders the value as a picture; otherwise it's shown as text.

export const HINTS = [
  { label: "Occupation", get: (f) => capitalize(f.occupation) },
  {
    label: "Known for",
    get: (f) =>
      f.kfCircular && f.description
        ? { label: "Description", value: cleanDescription(f.description) }
        : knownFor(f),
  },
  { label: "Portrait", type: "image", get: (f) => f.image || null },
  { label: "Initials", get: (f) => initials(f.name) },
];

// The hints that actually have a value for this figure, in reveal order.
export function availableHints(figure) {
  if (!figure) return [];
  const out = [];
  for (const def of HINTS) {
    const r = def.get(figure);
    const value = r && typeof r === "object" ? r.value : r;
    if (value == null || value === "") continue;
    out.push({
      label: (r && typeof r === "object" && r.label) || def.label,
      type: (r && typeof r === "object" && r.type) || def.type || "text",
      value,
    });
  }
  return out;
}

// "First Emperor of the French (1769–1821)" -> "First Emperor of the French"
function cleanDescription(desc) {
  if (!desc) return null;
  return desc.replace(/\s*\([^)]*\d[^)]*\)\s*$/, "").trim() || null;
}

// "I. N." from "Isaac Newton" (skips short particles like "of", "de", "the").
function initials(name) {
  if (!name) return null;
  const letters = name
    .split(/\s+/)
    .filter((w) => w.length > 2 || /^[A-Z]/.test(w))
    .map((w) => w[0].toUpperCase());
  return letters.length ? letters.join(". ") + "." : null;
}

// The specific achievement from `famous_for`, with the person's name removed so
// it doesn't give the answer away. Robust to initials/suffixes ("John F.
// Kennedy", "... King Jr.") which would otherwise break naive sentence-splitting.
// "Isaac Newton is most famous for his three laws of motion. ..." ->
// "His three laws of motion"
export function knownFor(figure) {
  let s = figure.famous_for;
  if (!s) return null;
  // Drop the "<Name> is/was (most) famous for" lead-in (handles any name shape).
  const m = s.match(/\bfamous for\b/i);
  if (m) {
    s = s.slice(m.index + m[0].length);
  } else {
    s = s.replace(new RegExp("^\\W*" + escapeRegExp(figure.name) + "\\W*", "i"), "");
  }
  // First sentence only -- a boundary needs two lowercase letters or digits
  // before the period (so we split after "...1687." but not on "F." / "Jr.").
  s = s.split(/(?<=[a-z0-9][a-z0-9][.!?])\s+(?=[A-Z0-9])/)[0];
  // Redact any lingering name tokens (strip trailing dots from initials first).
  const tokens = figure.name
    .split(/\s+/)
    .map((t) => t.replace(/\.+$/, ""))
    .filter((t) => t.length > 1);
  for (const t of tokens) {
    s = s.replace(new RegExp("\\b" + escapeRegExp(t) + "(?:'s)?\\b", "gi"), "");
  }
  s = s
    .replace(/\s+/g, " ")
    .replace(/^\W+/, "")
    .replace(/^(is|was|a|an|the|being)\s+/i, "")
    .trim();
  if (s.length < 6) return null; // redaction left too little to be useful
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// "POLITICIAN" / "religious figure" -> "Politician" / "Religious figure"
function capitalize(s) {
  if (!s) return null;
  const lower = s.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}
