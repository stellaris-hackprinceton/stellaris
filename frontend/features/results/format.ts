import type { Measurement } from "@/contracts/api";

const nf = new Intl.NumberFormat("en-US", { maximumSignificantDigits: 6 });

/** Display only. Stored precision is untouched; callers put the raw value in a title. */
export function formatValue(v: number): string {
  return nf.format(v);
}

export const STATUS_LABEL: Record<Measurement["status"], string> = { valid: "Valid", missing: "Missing", rejected: "Rejected" };
export const ORIGIN_LABEL: Record<Measurement["data_origin"], string> = { observed: "Observed", derived: "Derived", simulated: "Simulated" };

export function unitLabel(u: string): string {
  return u === "1" ? "dimensionless" : u;
}
