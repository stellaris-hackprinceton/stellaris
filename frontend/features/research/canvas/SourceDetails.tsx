import Link from "next/link";
import type { Claim, ID, Source } from "@/contracts/api";
import { ExternalIcon, StatusBadge, TimestampLabel } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import { PROVIDER_LABEL, RETRIEVAL_LABEL, authorLine, safeHref } from "./labels";
import styles from "./canvas.module.css";

type Props = { project_id: ID; source: Source; claims: Claim[] };

/** Retrieved material only. Excerpts come from persisted claim citations, never generated here. */
export function SourceDetails({ project_id, source, claims }: Props) {
  const r = RETRIEVAL_LABEL[source.retrieval_status];
  const link = safeHref(source.url);
  const doi = source.doi ? safeHref(`https://doi.org/${source.doi}`) : null;
  const excerpts = claims.flatMap((c) => c.citations.filter((ct) => ct.source_id === source.id).map((ct) => ({ claim: c, ct })));

  return (
    <article className={styles.details} aria-labelledby={`src-${source.id}`}>
      <h3 id={`src-${source.id}`} className={styles.detailsTitle}>{source.title}</h3>
      <p className={styles.muted}>{authorLine(source.authors, 12)}</p>
      <div className={styles.row}>
        <StatusBadge tone={r.tone}>{r.text}</StatusBadge>
        <span className={styles.muted}>{PROVIDER_LABEL[source.provider]}</span>
      </div>
      {source.retrieval_status !== "full_text_retrieved" && (
        <p className={styles.qualification}>
          {source.retrieval_status === "abstract_retrieved"
            ? "Only the abstract was retrieved. Claims citing this source did not inspect the full paper."
            : source.retrieval_status === "failed"
              ? "Retrieval failed. Only the listed metadata is known."
              : "Only bibliographic metadata is available. The paper's content has not been inspected."}
        </p>
      )}
      <dl className={styles.dl}>
        <dt>Published</dt><dd>{source.published_at ?? "Unknown"}</dd>
        {source.doi && <><dt>DOI</dt><dd className={styles.mono}>{doi ? <a href={doi} target="_blank" rel="noopener noreferrer">{source.doi}</a> : source.doi}</dd></>}
        <dt>Retrieved</dt><dd><TimestampLabel iso={source.retrieved_at} /></dd>
      </dl>
      <div className={styles.row}>
        {link && <a href={link} target="_blank" rel="noopener noreferrer" className={styles.extLink}>Open source <ExternalIcon /><span className="sr-only">(opens in a new tab)</span></a>}
        {source.document_artifact_id && <Link href={hrefs.artifact(project_id, source.document_artifact_id)}>Retrieved document</Link>}
      </div>
      <section className={styles.stack}>
        <h4>Abstract</h4>
        {source.abstract ? <p className="prose">{source.abstract}</p> : <p className={styles.muted}>No abstract retrieved.</p>}
      </section>
      <section className={styles.stack}>
        <h4>Cited excerpts</h4>
        {excerpts.length === 0 ? (
          <p className={styles.muted}>No loaded finding cites this source yet.</p>
        ) : (
          <ul className={styles.list}>
            {excerpts.map(({ claim, ct }, i) => (
              <li key={`${claim.id}-${i}`} className={styles.excerpt}>
                {ct.excerpt ? <blockquote>{ct.excerpt}</blockquote> : <p className={styles.muted}>Cited without an excerpt.</p>}
                <p className={styles.muted}>
                  {ct.locator && <>{ct.locator} · </>}
                  <Link href={hrefs.research(project_id, { tab: "findings", claim: claim.id })}>See finding</Link>
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
