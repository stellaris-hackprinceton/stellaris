/**
 * Reader-facing names for stored scientific identifiers (HX-01). Display only: the saved record,
 * downloads and API values keep the original names, which callers expose through a title.
 */
const KNOWN: Record<string, string> = {
  // bouncing_ball_v1 series
  tracking: "Tracking",
  apex_height_px: "Peak heights (px)",
  apex_height_m: "Peak heights (m)",
  flight_fit: "Flight fits",
  height_ratio: "Bounce height ratios",
  energy_retention: "Energy retained",
  summary: "Summary",
  // bouncing_ball_v1 quantities
  detected_frame_fraction: "Frames with the ball detected",
  apex_height: "Peak height",
  vertical_acceleration: "Vertical acceleration",
  apex_height_ratio: "Peak height ratio",
  vertical_energy_retention_fraction: "Energy kept per bounce",
  mean_apex_height_ratio: "Mean peak height ratio",
};

const UNIT_SUFFIX: Record<string, string> = { px: "px", m: "m", s: "s" };

/** True when the name has a curated reader-facing label. */
export function isKnownName(text: string): boolean {
  return Object.hasOwn(KNOWN, text);
}

/** True for stored machine names such as `apex_height_px` (lowercase words joined by underscores). */
export function isMachineName(text: string): boolean {
  return /^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/.test(text);
}

export function humanizeName(name: string): string {
  const known = KNOWN[name];
  if (known) return known;
  if (!isMachineName(name)) return name;
  const words = name.split("_");
  const last = words[words.length - 1];
  const unit = UNIT_SUFFIX[last] && words.length > 1 ? words.pop() : undefined;
  const phrase = words.join(" ");
  const sentence = phrase.charAt(0).toUpperCase() + phrase.slice(1);
  return unit ? `${sentence} (${unit})` : sentence;
}

const ID_KIND: Record<string, string> = {
  art: "File", run: "Run", exp: "Experiment", src: "Source", clm: "Finding", msg: "Message", rel: "Link", fil: "File",
};

/** Resource IDs like `art_26791ddb…`; returns a short human label, or null when the text is not an ID. */
export function describeResourceId(text: string): { prefix: string; label: string } | null {
  const match = /^([a-z]{3})_([0-9a-f]{12,})$/.exec(text);
  if (!match || !ID_KIND[match[1]]) return null;
  const hex = match[2];
  return { prefix: match[1], label: `${ID_KIND[match[1]]} ${hex.slice(0, 4)}…${hex.slice(-4)}` };
}
