import { useEffect, useMemo, useRef, useState } from "react";
import { geoNaturalEarth1, geoPath, geoGraticule10 } from "d3-geo";
import { feature, mesh } from "topojson-client";
import worldData from "world-atlas/countries-110m.json";
import usData from "us-atlas/states-10m.json";

const WIDTH = 800;
const HEIGHT = 420;
const ASPECT = WIDTH / HEIGHT;

// Adaptive-zoom tuning.
const MAX_ZOOM = 8; // never zoom past this -> always keep regional context
const MIN_VW = WIDTH / MAX_ZOOM; // smallest viewBox width allowed
const PAD = 2.4; // frame padding: how much empty space around the two markers
const TWEEN_MS = 460; // camera glide duration

const FULL_WORLD = { x: 0, y: 0, w: WIDTH, h: HEIGHT };

// Pre-compute land features once at module load.
const land = feature(worldData, worldData.objects.countries);
// Interior US state borders only (mesh with a !== b drops the outer coastline,
// which the country layer already draws).
const usStateBorders = mesh(usData, usData.objects.states, (a, b) => a !== b);

// The projection fits the whole world and never changes with the figure, so
// build it and the static layer paths once instead of on every render.
const projection = geoNaturalEarth1().fitExtent(
  [
    [8, 8],
    [WIDTH - 8, HEIGHT - 8],
  ],
  land
);
const staticPath = geoPath(projection);
const LAND_D = staticPath(land);
const GRATICULE_D = staticPath(geoGraticule10());
const US_STATES_D = staticPath(usStateBorders);

// A single marker: ringed circle + filled dot + year label.
// Every dimension is multiplied by `s` so the marker keeps a constant ON-SCREEN
// size as the camera zooms (the viewBox magnifies everything we draw).
function Marker({ x, y, color, year, place, s }) {
  let dx = 0;
  let dy = 0;
  let anchor = "start";
  let baseline = "central";
  if (place === "left") {
    dx = -14 * s;
    anchor = "end";
  } else if (place === "right") {
    dx = 14 * s;
    anchor = "start";
  } else if (place === "above") {
    dy = -15 * s;
    anchor = "middle";
    baseline = "auto";
  } else if (place === "below") {
    dy = 16 * s;
    anchor = "middle";
    baseline = "hanging";
  }
  return (
    <g>
      <circle cx={x} cy={y} r={9 * s} fill={color} fillOpacity={0.18} />
      <circle cx={x} cy={y} r={9 * s} fill="none" stroke={color} strokeWidth={2 * s} />
      <circle cx={x} cy={y} r={3.5 * s} fill={color} />
      <text
        x={x + dx}
        y={y + dy}
        textAnchor={anchor}
        dominantBaseline={baseline}
        className="select-none"
        style={{
          fontSize: 17 * s,
          fontWeight: 700,
          fill: "#111827",
          paintOrder: "stroke",
          stroke: "#ffffff",
          strokeWidth: 4 * s,
          strokeLinejoin: "round",
        }}
      >
        {year}
      </text>
    </g>
  );
}

// Frame the two points: padded bounding box, clamped so we never zoom past
// MAX_ZOOM and never pan outside the rendered world.
function frameFor(b, d) {
  const cx = (b.x + d.x) / 2;
  const cy = (b.y + d.y) / 2;
  const spanX = Math.abs(b.x - d.x);
  const spanY = Math.abs(b.y - d.y);
  let vw = Math.max(spanX, spanY * ASPECT) * PAD;
  vw = Math.min(Math.max(vw, MIN_VW), WIDTH);
  const vh = vw / ASPECT;
  const x = Math.min(Math.max(cx - vw / 2, 0), WIDTH - vw);
  const y = Math.min(Math.max(cy - vh / 2, 0), HEIGHT - vh);
  return { x, y, w: vw, h: vh };
}

const lerp = (a, b, t) => a + (b - a) * t;
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

export default function WorldMap({ figure }) {
  const scene = useMemo(() => {
    const base = {
      birth: null,
      death: null,
      coincident: false,
      birthPlace: "right",
      deathPlace: "right",
      target: FULL_WORLD,
    };
    if (!figure) return base;

    const b = projection([figure.birthLng, figure.birthLat]);
    const d = projection([figure.deathLng, figure.deathLat]);
    if (!b || !d) return base;

    const trueB = { x: b[0], y: b[1] };
    const trueD = { x: d[0], y: d[1] };

    // Frame from the TRUE positions, then derive the zoom scale so the label
    // layout below reasons in the same on-screen terms the camera will show.
    const target = frameFor(trueB, trueD);
    const s = target.w / WIDTH; // <= 1 when zoomed in

    const dist = Math.hypot(trueB.x - trueD.x, trueB.y - trueD.y);
    let birthPt = trueB;
    let deathPt = trueD;
    let coincident = false;
    let birthPlace = "right";
    let deathPlace = "right";

    // Thresholds scale with zoom: what counts as "overlapping" is relative to
    // the markers' constant on-screen footprint, not raw base-pixel distance.
    if (dist < 4 * s) {
      // genuinely the same coordinates -> split the dots symmetrically
      coincident = true;
      birthPt = { x: trueB.x - 9 * s, y: trueB.y };
      deathPt = { x: trueD.x + 9 * s, y: trueD.y };
      birthPlace = "above";
      deathPlace = "below";
    } else if (dist < 40 * s) {
      // close but distinct -> dots stay truthful, labels separate vertically
      if (trueB.y <= trueD.y) {
        birthPlace = "above";
        deathPlace = "below";
      } else {
        birthPlace = "below";
        deathPlace = "above";
      }
    } else {
      birthPlace = trueB.x > WIDTH - 80 ? "left" : "right";
      deathPlace = trueD.x > WIDTH - 80 ? "left" : "right";
    }

    return {
      ...base,
      birth: birthPt,
      death: deathPt,
      coincident,
      birthPlace,
      deathPlace,
      target,
    };
  }, [figure]);

  // Animated camera. `vb` is the live viewBox; we tween it toward scene.target
  // whenever the figure (and thus the target frame) changes.
  const [vb, setVb] = useState(FULL_WORLD);
  const vbRef = useRef(FULL_WORLD);
  const { target } = scene;

  useEffect(() => {
    const from = vbRef.current;
    const to = target;
    let raf;
    const start = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start) / TWEEN_MS);
      const e = easeOutCubic(t);
      const cur = {
        x: lerp(from.x, to.x, e),
        y: lerp(from.y, to.y, e),
        w: lerp(from.w, to.w, e),
        h: lerp(from.h, to.h, e),
      };
      vbRef.current = cur;
      setVb(cur);
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.x, target.y, target.w, target.h]);

  const s = vb.w / WIDTH; // live render scale for counter-scaling strokes/markers
  const { birth, death, coincident, birthPlace, deathPlace } = scene;

  return (
    <svg
      viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
      className="w-full h-auto rounded-2xl"
      role="img"
      aria-label="World map with birthplace and death place markers"
    >
      {/* ocean fills the whole world so panning never reveals blank canvas */}
      <rect x="0" y="0" width={WIDTH} height={HEIGHT} fill="#dce6ef" />
      <path d={GRATICULE_D} fill="none" stroke="#c6d4e2" strokeWidth={0.5 * s} />
      <path d={LAND_D} fill="#f4f1ea" stroke="#bcae93" strokeWidth={0.6 * s} />
      {/* US state borders, lighter/thinner than country borders */}
      <path d={US_STATES_D} fill="none" stroke="#cdbfa3" strokeWidth={0.35 * s} />

      {coincident && birth && death && (
        <line
          x1={birth.x}
          y1={birth.y}
          x2={death.x}
          y2={death.y}
          stroke="#9ca3af"
          strokeWidth={1.5 * s}
          strokeDasharray={`${3 * s} ${3 * s}`}
        />
      )}

      {birth && figure && (
        <Marker
          x={birth.x}
          y={birth.y}
          color="#22c55e"
          year={fmtYear(figure.birthYear)}
          place={birthPlace}
          s={s}
        />
      )}
      {death && figure && (
        <Marker
          x={death.x}
          y={death.y}
          color="#ef4444"
          year={fmtYear(figure.deathYear)}
          place={deathPlace}
          s={s}
        />
      )}
    </svg>
  );
}

// Show BCE years as e.g. "44 BC".
function fmtYear(year) {
  if (year === "" || year == null) return "";
  return year < 0 ? `${Math.abs(year)} BC` : `${year}`;
}
