/**
 * Deterministic force-directed layout for the Connections graph. Linked files pull together,
 * every file repels its neighbours, and a weak pull keeps unlinked files near the centre, so
 * clusters reflect recorded relations instead of file type or load order. The same files and
 * links always produce the same picture (seeded start, fixed iteration count).
 */
export type LayoutPoint = { x: number; y: number };
export type LayoutLink = { source: string; target: string };

function hash(text: string) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967295;
}

/** Returns positions in an abstract unit space centred on (0, 0); callers fit them to the viewport. */
export function forceLayout(ids: string[], links: LayoutLink[], radius: (id: string) => number): Map<string, LayoutPoint> {
  const n = ids.length;
  const index = new Map(ids.map((id, i) => [id, i]));
  const xs = new Float64Array(n), ys = new Float64Array(n), dx = new Float64Array(n), dy = new Float64Array(n);
  const degree = new Uint16Array(n);
  const pairs: [number, number][] = [];
  for (const link of links) {
    const a = index.get(link.source), b = index.get(link.target);
    if (a === undefined || b === undefined || a === b) continue;
    pairs.push([a, b]); degree[a]++; degree[b]++;
  }
  const ideal = 46; // preferred link length in layout units
  const spread = ideal * Math.sqrt(n) * 0.9;
  ids.forEach((id, i) => {
    // Seeded golden-angle start keeps the result stable and avoids coincident points.
    const angle = i * 2.399963 + hash(id) * 0.5, r = spread * Math.sqrt((i + 0.5) / Math.max(1, n));
    xs[i] = Math.cos(angle) * r; ys[i] = Math.sin(angle) * r;
  });
  const radii = ids.map(radius);
  const iterations = n > 120 ? 220 : 300;
  let temperature = spread * 0.12;
  const cooling = Math.pow(0.02, 1 / iterations);
  for (let step = 0; step < iterations; step++) {
    dx.fill(0); dy.fill(0);
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      let ex = xs[i] - xs[j], ey = ys[i] - ys[j];
      let d2 = ex * ex + ey * ey;
      if (d2 < 0.01) { ex = 0.1 * (hash(ids[i] + ids[j]) - 0.5); ey = 0.1; d2 = ex * ex + ey * ey; }
      const d = Math.sqrt(d2);
      const minimum = radii[i] + radii[j] + 10;
      // Repulsion (ideal²/d), plus a hard push when two nodes would overlap.
      const force = (ideal * ideal) / d + (d < minimum ? (minimum - d) * 2 : 0);
      const fx = (ex / d) * force, fy = (ey / d) * force;
      dx[i] += fx; dy[i] += fy; dx[j] -= fx; dy[j] -= fy;
    }
    for (const [a, b] of pairs) {
      const ex = xs[a] - xs[b], ey = ys[a] - ys[b];
      const d = Math.sqrt(ex * ex + ey * ey) || 0.01;
      const force = (d * d) / ideal;
      const fx = (ex / d) * force, fy = (ey / d) * force;
      dx[a] -= fx; dy[a] -= fy; dx[b] += fx; dy[b] += fy;
    }
    for (let i = 0; i < n; i++) {
      // Gravity: unlinked files get a stronger pull so they ring the clusters instead of drifting away.
      const g = degree[i] === 0 ? 0.09 : 0.03;
      dx[i] -= xs[i] * g * ideal * 0.1; dy[i] -= ys[i] * g * ideal * 0.1;
      const d = Math.sqrt(dx[i] * dx[i] + dy[i] * dy[i]);
      if (d > 0) { const move = Math.min(d, temperature); xs[i] += (dx[i] / d) * move; ys[i] += (dy[i] / d) * move; }
    }
    temperature *= cooling;
  }
  return new Map(ids.map((id, i) => [id, { x: xs[i], y: ys[i] }]));
}

/** Scales abstract positions into a viewport with padding, preserving aspect ratio and centring. */
export function fitToViewport(points: Map<string, LayoutPoint>, width: number, height: number, padding: number) {
  const fitted = new Map<string, LayoutPoint>();
  if (points.size === 0) return fitted;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of points.values()) { minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x); minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y); }
  const spanX = Math.max(maxX - minX, 1), spanY = Math.max(maxY - minY, 1);
  // Never enlarge a small graph beyond its natural spacing; only shrink a large one to fit.
  const scale = Math.min((width - 2 * padding) / spanX, (height - 2 * padding) / spanY, 1.6);
  const ox = width / 2 - ((minX + maxX) / 2) * scale, oy = height / 2 - ((minY + maxY) / 2) * scale;
  for (const [id, p] of points) fitted.set(id, { x: p.x * scale + ox, y: p.y * scale + oy });
  return fitted;
}
