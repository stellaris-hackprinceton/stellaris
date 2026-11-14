"use client";
import type { ID, Measurement } from "@/contracts/api";
import { ORIGIN_LABEL, STATUS_LABEL, formatValue, unitLabel } from "./format";
import styles from "./results.module.css";

type Group = { key: string; series: string; quantity: string; unit: string; rows: Measurement[] };

/** One table per series × quantity × unit, so unlike units never share a column. */
export function groupMeasurements(ms: Measurement[]): Group[] {
  const map = new Map<string, Group>();
  for (const m of ms) {
    const key = `${m.series}\u0000${m.quantity}\u0000${m.unit}`;
    let g = map.get(key);
    if (!g) { g = { key, series: m.series, quantity: m.quantity, unit: m.unit, rows: [] }; map.set(key, g); }
    g.rows.push(m);
  }
  return [...map.values()];
}

type Props = { measurements: Measurement[]; selected: ID | null; onSelect: (id: ID) => void };

export function MeasurementTable({ measurements, selected, onSelect }: Props) {
  const groups = groupMeasurements(measurements);
  return (
    <div className={styles.groups}>
      {groups.map((g) => (
        <section key={g.key} className={styles.group} aria-label={`${g.series}: ${g.quantity}`}>
          <h4 className={styles.groupTitle}>
            {g.series} · {g.quantity} <span className={styles.unit}>({unitLabel(g.unit)})</span>
          </h4>
          <div className={styles.tableWrap} role="region" aria-label={`${g.series} ${g.quantity} table`} tabIndex={0}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Time (s)</th>
                  <th scope="col" className={styles.numCol}>Value ({unitLabel(g.unit)})</th>
                  <th scope="col" className={styles.numCol}>± Uncertainty</th>
                  <th scope="col">Status</th>
                  <th scope="col">Origin</th>
                  <th scope="col"><span className="sr-only">Details</span></th>
                </tr>
              </thead>
              <tbody>
                {g.rows.map((m) => (
                  <tr key={m.id} className={m.id === selected ? styles.selectedRow : undefined}>
                    <td className="num">{m.time_s == null ? "—" : formatValue(m.time_s)}</td>
                    <td className={`num ${styles.numCol}`} title={m.value == null ? undefined : String(m.value)}>
                      {m.status === "valid" && m.value != null ? formatValue(m.value) : <span className={styles.unavailable}>Unavailable</span>}
                    </td>
                    <td className={`num ${styles.numCol}`}>
                      {m.uncertainty.absolute == null ? <span className={styles.muted}>Not estimated</span> : formatValue(m.uncertainty.absolute)}
                    </td>
                    <td>
                      <span className={styles.status} data-status={m.status}>{STATUS_LABEL[m.status]}</span>
                      {m.status !== "valid" && m.assumptions[0] && <span className={styles.reason}>{m.assumptions[0]}</span>}
                    </td>
                    <td>{ORIGIN_LABEL[m.data_origin]}</td>
                    <td><button type="button" className={styles.linkButton} aria-pressed={m.id === selected} onClick={() => onSelect(m.id)}>Evidence</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
