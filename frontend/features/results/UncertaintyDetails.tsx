import type { ID, Measurement } from "@/contracts/api";
import { humanizeName } from "@/components/ui";
import { Button } from "@/components/ui";
import { EvidenceViewer } from "./EvidenceViewer";
import { ORIGIN_LABEL, STATUS_LABEL, unitLabel } from "./format";
import styles from "./results.module.css";

/** Full-precision values, uncertainty method, assumptions and evidence for one measurement. */
export function UncertaintyDetails({ project_id, m, onClose }: { project_id: ID; m: Measurement; onClose: () => void }) {
  return (
    <section className={styles.details} aria-labelledby={`m-${m.id}`}>
      <div className={styles.detailsHead}>
        <h4 id={`m-${m.id}`}>{humanizeName(m.quantity)} · {humanizeName(m.series)}{m.time_s != null && ` at ${m.time_s} s`}</h4>
        <Button onClick={onClose}>Close</Button>
      </div>
      <dl className={styles.dl}>
        <dt>Value</dt>
        <dd className={styles.mono}>{m.status === "valid" && m.value != null ? `${m.value} ${unitLabel(m.unit)}` : `Unavailable (${STATUS_LABEL[m.status].toLowerCase()})`}</dd>
        <dt>Uncertainty</dt>
        <dd>{m.uncertainty.absolute == null
          ? "Not estimated. This does not mean zero error."
          : <span className={styles.mono}>± {m.uncertainty.absolute} {unitLabel(m.unit)}</span>}
          {m.uncertainty.method && <span className={styles.muted}> · {m.uncertainty.method}</span>}
        </dd>
        <dt>Origin</dt><dd>{ORIGIN_LABEL[m.data_origin]}</dd>
        <dt>Calibration</dt><dd>{m.calibration_mode === "none" ? "None (native units)" : "Reference length"}</dd>
      </dl>
      {m.assumptions.length > 0 && (
        <>
          <h5 className={styles.smallLabel}>{m.status === "valid" ? "Assumptions" : "Explanation and assumptions"}</h5>
          <ul className={styles.bullets}>{m.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </>
      )}
      <h5 className={styles.smallLabel}>Evidence</h5>
      {m.evidence.length === 0
        ? <p className={styles.unavailable}>No evidence is linked to this row.</p>
        : m.evidence.map((ev, i) => <EvidenceViewer key={i} project_id={project_id} evidence={ev} />)}
    </section>
  );
}
