"use client";
import { Button } from "@/components/ui";
import { FIELD_LABEL, describeValue } from "./draft";
import type { PlanDraftController } from "./usePlanDraft";
import styles from "../studio.module.css";

/** Shown when a newer revision was saved elsewhere while this form had unsaved edits. */
export function ConflictPanel({ plan, savedRevision }: { plan: PlanDraftController; savedRevision: number }) {
  const { draft, saved, conflicting } = plan;
  if (!draft || !saved) return null;
  return (
    <div className={styles.conflict} role="alert">
      <p><strong>Revision {savedRevision} was saved elsewhere.</strong> Your unsaved edits are kept. Nothing is overwritten until you choose.</p>
      {conflicting.length > 0 ? (
        <>
          <p className={styles.muted}>Both versions changed these fields:</p>
          <ul className={styles.conflictList}>
            {conflicting.map((f) => (
              <li key={f} className={styles.conflictItem}>
                <p className={styles.smallLabel}>{FIELD_LABEL[f]}</p>
                <div className={styles.grid2}>
                  <div><p className={styles.muted}>Saved</p><p className={styles.conflictValue}>{describeValue(f, saved)}</p></div>
                  <div><p className={styles.muted}>Yours</p><p className={styles.conflictValue}>{describeValue(f, draft)}</p></div>
                </div>
                <Button onClick={() => plan.useSaved(f)}>Use saved {FIELD_LABEL[f].toLowerCase()}</Button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className={styles.muted}>The other changes touch different fields than yours.</p>
      )}
      <div className={styles.row}>
        <Button variant="primary" onClick={plan.rebase}>Continue from revision {savedRevision} with my edits</Button>
        <Button onClick={plan.discard}>Discard my edits</Button>
      </div>
    </div>
  );
}
