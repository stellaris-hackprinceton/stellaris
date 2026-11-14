import Link from "next/link";
import type { Claim, ID } from "@/contracts/api";
import { hrefs } from "@/components/shell/hrefs";
import styles from "./chat.module.css";

export const CLAIM_KIND_LABEL: Record<Claim["kind"], string> = {
  observation: "Observation",
  inference: "Inference",
  hypothesis: "Hypothesis (proposed)",
};

/** Opens the persisted claim in Research Canvas. Unresolved IDs never get a made-up label. */
export function CitationLink({ project_id, claim_id, claim }: { project_id: ID; claim_id: ID; claim: Claim | undefined }) {
  if (!claim) {
    return <span className={styles.unavailableRef} title={claim_id}>Unavailable reference</span>;
  }
  return (
    <Link href={hrefs.research(project_id, { tab: "findings", claim: claim.id })} className={styles.citation}>
      <span className={styles.citationKind}>{CLAIM_KIND_LABEL[claim.kind]}</span>
      <span className={styles.citationText}>{claim.text}</span>
    </Link>
  );
}
