"use client";
import { useId } from "react";
import styles from "./results.module.css";

/** Picks among series found in the loaded rows. Labelled so it is not mistaken for a server-wide list. */
export function SeriesSelector({ series, value, onChange }: { series: string[]; value: string; onChange: (s: string) => void }) {
  const id = useId();
  if (series.length < 2) return null;
  return (
    <div className={styles.inline}>
      <label htmlFor={id} className={styles.smallLabel}>Series (in loaded rows)</label>
      <select id={id} className={styles.select} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All series</option>
        {series.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
    </div>
  );
}
