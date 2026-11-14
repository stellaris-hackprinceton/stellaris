"use client";
/* eslint-disable @next/next/no-img-element -- authenticated artifact content cannot use the image optimizer. */
import Link from "next/link";
import type { Citation, Claim, EvidenceRef, ID } from "@/contracts/api";
import { artifactContentUrl } from "@/lib/api";
import { useArtifact, useClaim, useMeasurements, useRunResults, useSource } from "@/lib/queries";
import { useCatalogView, type ViewFile } from "@/lib/queries/views";
import { Button, ErrorNotice, Skeleton, describeError } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import type { CitationFocus } from "./SourceInspector";
import { CardError, CardSkeleton, ListState, MediaPreview, Widget, WidgetFooter, dateLabel, listHasBlockingState, useDisclosure } from "./Widget";
import styles from "./desk.module.css";

export type OpenClaim = (claim_id: ID, opener: HTMLElement | null) => void;
export type OpenCitation = (source_id: ID, opener: HTMLElement | null, citation: CitationFocus) => void;

const KIND_LABEL: Record<Claim["kind"], string> = { observation: "Observation", inference: "Inference", hypothesis: "Hypothesis · proposed" };

export function FindingsWidget({ project_id, onOpenClaim, onOpenCitation, selected }: { project_id: ID; onOpenClaim: OpenClaim; onOpenCitation: OpenCitation; selected: ID | null }) {
  const disclosure = useDisclosure(3, 6);
  const list = useCatalogView(project_id, { origin_type: "claim", sort: "created_at", order: "desc" }, disclosure.limit);
  const blocked = listHasBlockingState(list);
  return (
    <Widget id="desk-findings" title="Findings"
      footer={<WidgetFooter label="findings" canExpand={list.has_next_page || list.items.length > disclosure.preview} expanded={disclosure.expanded} onToggle={disclosure.toggle} viewAll={hrefs.materialsView(project_id, "findings")} />}>
      {blocked ? <ListState list={list} what="Findings" skeletons={3} /> : list.items.length === 0 && <p className={styles.empty}>Findings appear when research or analysis saves a claim.</p>}
      {!blocked && list.items.length > 0 && <ul className={styles.cards}>
        {list.items.slice(0, disclosure.shown).map((file) => <li key={file.id}><FindingCard project_id={project_id} file={file} onOpenClaim={onOpenClaim} onOpenCitation={onOpenCitation} selected={selected === file.origin?.id} /></li>)}
        {list.error && list.items.length > 0 && <li><CardError what={list.is_next_page_error ? "More findings" : "Findings refresh"} error={list.error} retry={list.is_next_page_error ? list.load_next_page : list.refetch} /></li>}
      </ul>}
    </Widget>
  );
}

function FindingCard({ project_id, file, onOpenClaim, onOpenCitation, selected }: { project_id: ID; file: ViewFile; onOpenClaim: OpenClaim; onOpenCitation: OpenCitation; selected: boolean }) {
  const query = useClaim(project_id, file.origin?.id);
  const c = query.data;
  if (!file.origin) return <div className={styles.card}><p className={styles.unavailable}>Finding record unavailable.</p></div>;
  if (query.error && !c) return <CardError what="Finding" error={query.error} retry={query.refetch} />;
  if (!c) return <CardSkeleton />;
  return (
    <article className={styles.card} data-selected={selected}>
      <p className={styles.meta}><strong>{KIND_LABEL[c.kind]}</strong></p>
      <button type="button" className={styles.title} style={{ fontWeight: 500 }} onClick={(e) => onOpenClaim(c.id, e.currentTarget)}>{c.text}</button>
      {c.limitations[0] && <p className={`${styles.clamp2} ${styles.meta}`}>Limitation: {c.limitations[0]}</p>}
      {(c.limitations.length > 0 || c.assumptions.length > 0) && <button type="button" className={styles.linkButton} onClick={(e) => onOpenClaim(c.id, e.currentTarget)}>More qualifications</button>}
      <p className={styles.meta}>{c.citations.length} citation{c.citations.length === 1 ? "" : "s"} · {c.measurement_ids.length} measurement reference{c.measurement_ids.length === 1 ? "" : "s"} · saved {dateLabel(c.created_at)}</p>
      <details className={styles.details}>
        <summary>Evidence</summary>
        <ClaimEvidence project_id={project_id} claim={c} onOpenCitation={onOpenCitation} />
      </details>
    </article>
  );
}

/** Citations, measurement and artifact references, assumptions, limitations, and related (not supporting) run output. */
export function ClaimEvidence({ project_id, claim, onOpenCitation }: { project_id: ID; claim: Claim; onOpenCitation: OpenCitation }) {
  return (
    <div>
      <h4>Citations</h4>
      {claim.citations.length ? <ul>{claim.citations.map((c, i) => <CitationItem key={`${c.source_id}:${i}`} project_id={project_id} citation={c} onOpen={onOpenCitation} />)}</ul> : <p className={styles.meta}>No citations recorded.</p>}
      <h4>Measurements</h4>
      {claim.measurement_ids.length ? <MeasurementReferences project_id={project_id} run_id={claim.run_id} ids={claim.measurement_ids} /> : <p className={styles.meta}>No measurement references recorded.</p>}
      <h4>Evidence references</h4>
      {claim.evidence.length ? <ul>{claim.evidence.map((ref, i) => <EvidenceItem key={`${ref.artifact_id}:${i}`} project_id={project_id} evidence={ref} />)}</ul> : <p className={styles.meta}>No artifact evidence references recorded.</p>}
      {claim.assumptions.length > 0 && <><h4>Assumptions</h4><ul>{claim.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul></>}
      {claim.limitations.length > 0 && <><h4>Limitations</h4><ul>{claim.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul></>}
      <RelatedRunOutput project_id={project_id} run_id={claim.run_id} />
    </div>
  );
}

function MeasurementReferences({ project_id, run_id, ids }: { project_id: ID; run_id: ID; ids: ID[] }) {
  const rows = useMeasurements(project_id, run_id, { limit: 100 });
  const byId = new Map(rows.items.map((measurement) => [measurement.id, measurement]));
  return <ul>{ids.map((id) => {
    const measurement = byId.get(id);
    if (measurement) return <li key={id}>
      <Link href={hrefs.run(project_id, run_id)}>{measurement.quantity}: {measurement.status === "missing" ? "Missing" : measurement.status === "rejected" ? "Rejected" : measurement.value ?? "Missing"} {measurement.unit}</Link>
      <span className={styles.meta}> · {measurement.data_origin} · calibration {measurement.calibration_mode} · {measurement.uncertainty.absolute == null ? "uncertainty not recorded" : `uncertainty ±${measurement.uncertainty.absolute} ${measurement.unit}`}</span>
    </li>;
    return <li key={id}>
      <Link href={hrefs.run(project_id, run_id)}>Measurement …{id.slice(-8)} in run results</Link>
      <span className={styles.unavailable}> · Reference unavailable in the loaded saved rows; inspect the run to resolve it.</span>
      {rows.error && <span className={styles.unavailable}> The measurement list could not be loaded.</span>}
    </li>;
  })}</ul>;
}

function CitationItem({ project_id, citation, onOpen }: { project_id: ID; citation: Citation; onOpen: OpenCitation }) {
  const source = useSource(project_id, citation.source_id);
  const label = source.data && source.data.project_id === project_id ? source.data.title : null;
  return (
    <li>
      {label ? <button type="button" className={styles.linkButton} onClick={(e) => onOpen(citation.source_id, e.currentTarget, { locator: citation.locator, excerpt: citation.excerpt })}>{label}</button>
        : source.error ? <span className={styles.unavailable}>Unavailable source (the cited record could not be loaded; this is not evidence against the claim)</span>
          : <Skeleton width="50%" />}
      {citation.locator && <span className={styles.meta}> · {citation.locator}</span>}
      {citation.excerpt && <blockquote className={styles.quote}>{citation.excerpt}</blockquote>}
    </li>
  );
}

/** An image appears only because it is an explicit evidence reference. */
function EvidenceItem({ project_id, evidence }: { project_id: ID; evidence: EvidenceRef }) {
  const artifact = useArtifact(project_id, evidence.artifact_id);
  const a = artifact.data;
  const where = [evidence.frame_index != null && `frame ${evidence.frame_index}`, evidence.time_s != null && `${evidence.time_s} s`, evidence.row_index != null && `row ${evidence.row_index}`].filter(Boolean).join(" · ");
  if (artifact.error && !a) return <li><span className={styles.unavailable}>Unavailable artifact …{evidence.artifact_id.slice(-8)}</span>{where && ` · ${where}`}</li>;
  return (
    <li>
      <Link href={hrefs.artifact(project_id, evidence.artifact_id)}>{a?.filename ?? `Artifact …${evidence.artifact_id.slice(-8)}`}</Link>{where && <span className={styles.meta}> · {where}</span>}
      {a && a.project_id === project_id && a.mime_type.startsWith("image/") && a.mime_type !== "image/svg+xml" && <figure className={styles.media}><img src={artifactContentUrl(project_id, a.id, "inline")} alt={`Evidence: ${a.filename}`} loading="lazy" /></figure>}
    </li>
  );
}

function RelatedRunOutput({ project_id, run_id }: { project_id: ID; run_id: ID }) {
  const results = useRunResults(project_id, run_id);
  if (results.error) return <ErrorNotice {...describeError(results.error, "Related run output unavailable")} action={<Button onClick={() => void results.refetch()}>Retry</Button>} />;
  const chart = results.data?.chart_artifact_ids[0];
  if (!chart) return null;
  return (
    <>
      <h4>Related run output</h4>
      <p className={styles.meta}>A chart saved by the same run. This association is not labelled as supporting proof.</p>
      <MediaPreview project_id={project_id} artifact_id={chart} />
    </>
  );
}

export function ClaimInspector({ project_id, claim_id, onOpenCitation }: { project_id: ID; claim_id: ID; onOpenCitation: OpenCitation }) {
  const query = useClaim(project_id, claim_id);
  const c = query.data;
  if (query.error && !c) return <ErrorNotice {...describeError(query.error, "Finding unavailable")} action={<Button onClick={() => void query.refetch()}>Retry</Button>} />;
  if (!c) return <Skeleton height="6rem" />;
  if (c.project_id !== project_id) return <p role="alert">This finding is unavailable in this project.</p>;
  return (
    <div className={styles.stack}>
      <p className={styles.meta}><strong>{KIND_LABEL[c.kind]}</strong> · saved {new Date(c.created_at).toLocaleString()}</p>
      <p style={{ margin: 0, overflowWrap: "anywhere" }}>{c.text}</p>
      <p className={styles.meta}>Recorded by <Link href={hrefs.run(project_id, c.run_id)}>run …{c.run_id.slice(-8)}</Link>. Execution state does not establish confidence or confirmation.</p>
      <div className={styles.details}><ClaimEvidence project_id={project_id} claim={c} onOpenCitation={onOpenCitation} /></div>
    </div>
  );
}
