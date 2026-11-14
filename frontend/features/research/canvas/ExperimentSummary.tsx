import Link from "next/link";
import type { Experiment, ID } from "@/contracts/api";
import { MarkdownView, TimestampLabel } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import { METHOD_LABEL, ROLE_LABEL } from "./labels";
import styles from "./canvas.module.css";

/** Read-only plan summary. Editing belongs to Studio (Agent B). A plan is not an execution status. */
export function ExperimentSummary({ project_id, experiment: x }: { project_id: ID; experiment: Experiment }) {
  return (
    <article className={styles.experiment} aria-labelledby={`exp-${x.id}`}>
      <header className={styles.experimentHead}>
        <h3 id={`exp-${x.id}`}>{x.title}</h3>
        <p className={styles.muted}>
          Revision {x.revision} · {METHOD_LABEL[x.method]} · saved <TimestampLabel iso={x.updated_at} />
        </p>
      </header>
      <section className={styles.stack}>
        <h4 className={styles.subhead}>Hypothesis</h4>
        <p className="prose">{x.hypothesis}</p>
      </section>
      {x.variables.length > 0 && (
        <section className={styles.stack}>
          <h4 className={styles.subhead}>Variables</h4>
          <div className={styles.tableWrap} role="region" aria-label="Variables" tabIndex={0}>
            <table className={styles.table}>
              <thead><tr><th scope="col">Role</th><th scope="col">Name</th><th scope="col">Unit</th><th scope="col">Description</th></tr></thead>
              <tbody>
                {x.variables.map((v, i) => (
                  <tr key={i}>
                    <td>{ROLE_LABEL[v.role]}</td>
                    <td>{v.name}</td>
                    <td className={styles.mono}>{v.unit ?? "—"}</td>
                    <td>{v.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {x.success_criteria.length > 0 && (
        <section className={styles.stack}>
          <h4 className={styles.subhead}>Success criteria</h4>
          <ul className={styles.bullets}>{x.success_criteria.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </section>
      )}
      <section className={styles.stack}>
        <h4 className={styles.subhead}>Calibration</h4>
        <p>{x.calibration.mode === "none"
          ? "None. Measurements stay in pixels or other native units; physical scale is not inferred."
          : `Reference length of ${x.calibration.reference_length_m} m${x.calibration.reference_uncertainty_m != null ? ` ± ${x.calibration.reference_uncertainty_m} m` : ""}.`}</p>
      </section>
      {x.limitations.length > 0 && (
        <section className={styles.stack}>
          <h4 className={styles.subhead}>Limitations</h4>
          <ul className={styles.bullets}>{x.limitations.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </section>
      )}
      <details className={styles.disclosure}>
        <summary>Protocol</summary>
        <MarkdownView markdown={x.protocol_markdown} />
      </details>
      <p className={styles.muted}>
        {x.input_artifact_ids.length} attached input{x.input_artifact_ids.length === 1 ? "" : "s"} ·{" "}
        <Link href={hrefs.studio(project_id, x.id)}>Open in Studio</Link>
      </p>
    </article>
  );
}
