import Link from "next/link";
import { forwardRef } from "react";
import type { Claim, EvidenceRef, ID, Source } from "@/contracts/api";
import { hrefs } from "@/components/shell/hrefs";
import { CLAIM_KIND_LABEL } from "../chat";
import styles from "./canvas.module.css";

type Props = {
  project_id: ID;
  claim: Claim;
  sources: Map<ID, Source>;
  selected: boolean;
  onSelectSource: (id: ID) => void;
};

function evidenceLabel(ev: EvidenceRef): string {
  const parts = [
    ev.frame_index != null && `frame ${ev.frame_index}`,
    ev.time_s != null && `${ev.time_s} s`,
    ev.row_index != null && `row ${ev.row_index}`,
  ].filter(Boolean);
  return parts.length ? `Evidence (${parts.join(", ")})` : "Evidence file";
}

export const ClaimCard = forwardRef<HTMLElement, Props>(function ClaimCard(
  { project_id, claim, sources, selected, onSelectSource }, ref,
) {
  return (
    <article ref={ref} className={styles.claim} data-kind={claim.kind} aria-current={selected || undefined} tabIndex={-1}>
      <p className={styles.claimKind}>{CLAIM_KIND_LABEL[claim.kind]}</p>
      <p className={styles.claimText}>{claim.text}</p>

      {(claim.measurement_ids.length > 0 || claim.evidence.length > 0) && (
        <div className={styles.row}>
          {claim.measurement_ids.length > 0 && (
            <Link href={hrefs.run(project_id, claim.run_id)}>
              {claim.measurement_ids.length} linked measurement{claim.measurement_ids.length === 1 ? "" : "s"}
            </Link>
          )}
          {claim.evidence.map((ev, i) => (
            <Link key={i} href={hrefs.artifact(project_id, ev.artifact_id)}>{evidenceLabel(ev)}</Link>
          ))}
        </div>
      )}

      {claim.citations.length > 0 && (
        <div className={styles.stack}>
          <h4 className={styles.subhead}>Citations</h4>
          <ul className={styles.list}>
            {claim.citations.map((ct, i) => {
              const s = sources.get(ct.source_id);
              return (
                <li key={i} className={styles.excerpt}>
                  {s ? (
                    <button type="button" className={styles.linkButton} onClick={() => onSelectSource(s.id)}>{s.title}</button>
                  ) : (
                    <span className={styles.unavailable} title={ct.source_id}>Unavailable reference</span>
                  )}
                  {ct.locator && <span className={styles.muted}> · {ct.locator}</span>}
                  {ct.excerpt && <blockquote>{ct.excerpt}</blockquote>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {claim.assumptions.length > 0 && (
        <div className={styles.stack}>
          <h4 className={styles.subhead}>Assumptions</h4>
          <ul className={styles.bullets}>{claim.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}
      {claim.limitations.length > 0 && (
        <div className={styles.stack}>
          <h4 className={styles.subhead}>Limitations</h4>
          <ul className={styles.bullets}>{claim.limitations.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}
      <p className={styles.muted}><Link href={hrefs.run(project_id, claim.run_id)}>From this run</Link></p>
    </article>
  );
});
