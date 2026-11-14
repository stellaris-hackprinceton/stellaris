"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Artifact, ID, Run } from "@/contracts/api";
import { Button, ErrorNotice, Select, Sheet, Skeleton, StatusBadge, describeError } from "@/components/ui";
import { GraphIcon, MaterialsIcon, ResearchIcon, TrackerIcon } from "@/components/ui/icons";
import { hrefs } from "@/components/shell/hrefs";
import { useArtifact, useCapabilities, useClaims, useExperiments, useMeasurements, useProject, useRun, useRunResults, useSources, useWorkspace } from "@/lib/queries";
import { useCatalog, useFiles } from "@/lib/catalog";
import { MaterialInspector } from "@/features/materials/MaterialInspector";
import { ChartGallery } from "@/features/results/ChartGallery";
import { ReportComposer } from "@/features/reports";
import { AddSourceDialog } from "./AddSourceDialog";
import { QuestionSection } from "./QuestionSection";
import reportStyles from "@/features/execution/sol.module.css";
import styles from "./overview.module.css";

export function ResearchScreen({ project_id }: { project_id: ID }) {
  const project = useProject(project_id), workspace = useWorkspace(project_id), capabilities = useCapabilities();
  const sources = useSources(project_id), claims = useClaims(project_id), experiments = useExperiments(project_id);
  const catalog = useCatalog(project_id);
  const [addingSource, setAddingSource] = useState(false), [experimentId, setExperimentId] = useState("");
  const experiment = experiments.items.find(row => row.id === experimentId) ?? experiments.items[0];
  const search = useSearchParams(), router = useRouter();
  const sourceId = search.get("source"), claimId = search.get("claim");
  const linkedFiles = useFiles(project_id, sourceId ? { origin_type: "source" } : claimId ? { origin_type: "claim" } : { limit: 1 });
  const linkedFile = linkedFiles.items.find(file => file.origin?.id === (sourceId ?? claimId));
  useEffect(() => {
    if ((sourceId || claimId) && !linkedFile && linkedFiles.has_next_page && !linkedFiles.is_fetching_next_page && !linkedFiles.error) void linkedFiles.load_next_page();
  }, [sourceId, claimId, linkedFile, linkedFiles]);
  const reportQuery = useArtifact(project_id, workspace.data?.latest_report_artifact_id);
  const recentRuns = useFiles(project_id, { origin_type: "run", sort: "created_at", order: "desc", limit: 1 });
  const recentCharts = useFiles(project_id, { tags: ["charts"], sort: "created_at", order: "desc", limit: 1 });
  const chart = useArtifact(project_id, recentCharts.items[0]?.origin?.id);
  const latestRun = useRun(project_id, chart.data?.run_id ?? recentRuns.items[0]?.origin?.id);
  const closeLinkedRecord = () => { const next = new URLSearchParams(search.toString()); next.delete("source"); next.delete("claim"); router.replace(`/projects/${encodeURIComponent(project_id)}/research${next.size ? `?${next}` : ""}`, { scroll: false }); };

  return <div className={styles.screen}>
    <header className={styles.header}><h1>Research</h1><p className={styles.lede}>{project.data?.description || "Your question, connected evidence, experiments, and saved results."}</p></header>
    <section className={styles.question} aria-labelledby="research-question-heading"><div className={styles.sectionHead}><h2 id="research-question-heading">Research question</h2></div><QuestionSection project_id={project_id} /></section>
    <div className={styles.columns}>
      <section className={styles.evidence} aria-labelledby="evidence-heading">
        <div className={styles.sectionHead}><h2 id="evidence-heading">Evidence and sources</h2><Link href={hrefs.view(project_id, "graph")}>View connections →</Link></div>
        <ul className={styles.evidenceRoles}>
          <li><ResearchIcon /><div><strong>Literature</strong><p>{workspace.data?.counts.sources === 0 ? "No sources saved yet." : `${workspace.data?.counts.sources ?? sources.items.length} saved sources.`}</p>
            {sources.items.slice(0, 2).map(source => <Link key={source.id} href={`${hrefs.view(project_id, "materials")}?source=${encodeURIComponent(source.id)}`}>{source.title}</Link>)}
            <Button disabled={project.data?.status === "archived"} onClick={() => setAddingSource(true)}>Add a source</Button></div></li>
          <li><GraphIcon /><div><strong>Findings</strong><p>{claims.items.length ? `${claims.items.length} findings loaded${claims.has_next_page ? "; more available" : ""}.` : "No recorded findings yet."}</p>
            {claims.items.slice(0, 2).map(claim => <Link key={claim.id} href={`${hrefs.view(project_id, "materials")}?claim=${encodeURIComponent(claim.id)}`}>{claim.text.length > 100 ? `${claim.text.slice(0, 97)}…` : claim.text}</Link>)}
            {!!claims.items.length && <Link href={`${hrefs.view(project_id, "materials")}?tag=results`}>Browse saved findings →</Link>}</div></li>
          <li><TrackerIcon /><div><strong>Measurements</strong><p>{catalog.data ? `${catalog.data.projected.run_measurements} saved measurement sets.` : "Inspect recorded measurements in experiment results."}</p><Link href={hrefs.view(project_id, "runs")}>Inspect analysis history →</Link></div></li>
          <li><MaterialsIcon /><div><strong>Report</strong>{reportQuery.data ? <Link href={hrefs.report(project_id, reportQuery.data.id)}>{reportQuery.data.filename}</Link> : <p>No report saved yet. Generate one from recorded analysis below.</p>}</div></li>
        </ul>
        {(sources.error || claims.error) && <ErrorNotice {...describeError(sources.error ?? claims.error, "Research records could not be loaded")} action={<Button onClick={() => { void sources.refetch(); void claims.refetch() }}>Retry records</Button>} />}
        {!capabilities.is_loading && !capabilities.data?.features.workspace_files && <p className={styles.note}>The catalog is unavailable on this backend. Scientific records remain accessible through Materials and the existing tools.</p>}
      </section>
      <section className={styles.readiness} aria-labelledby="readiness-heading">
        <div className={styles.sectionHead}><h2 id="readiness-heading">Experiment plan</h2></div>
        {experiments.error && <ErrorNotice {...describeError(experiments.error, "Experiment plans could not be loaded")} action={<Button onClick={experiments.refetch}>Retry plans</Button>} />}
        {experiments.is_loading ? <Skeleton height="5rem" /> : experiment ? <>
          {experiments.items.length > 1 && <Select aria-label="Overview experiment" value={experiment.id} onChange={event => setExperimentId(event.target.value)}>{experiments.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</Select>}
          <p className={styles.callout}>{experiment.title}</p><p className={styles.note}>Saved plan · revision {experiment.revision}. Review its prerequisites before launching.</p>
          <dl className={styles.readinessList}>
            <div><dt>Hypothesis</dt><dd>{experiment.hypothesis.trim() ? "Recorded" : "Needs definition"}</dd></div>
            <div><dt>Protocol</dt><dd>{experiment.protocol_markdown.trim() ? "Recorded" : "Needs definition"}</dd></div>
            <div><dt>Input materials</dt><dd>{experiment.input_artifact_ids.length} attached</dd></div>
            <div><dt>Calibration</dt><dd>{experiment.calibration.mode === "none" ? experiment.method === "computational" ? "Not specified" : "No physical scale" : "Reference length saved"}</dd></div>
          </dl>
          <Link className={styles.action} href={hrefs.studio(project_id, experiment.id)}>{!experiment.hypothesis.trim() || !experiment.protocol_markdown.trim() ? "Complete the plan" : !experiment.input_artifact_ids.length ? "Add experiment inputs" : "Review in Experiment Studio"} →</Link>
        </> : <><p className={styles.note}>No experiment plan has been saved.</p><Link className={styles.action} href={hrefs.studio(project_id)}>Design an experiment →</Link></>}
        {experiments.has_next_page && <Button onClick={() => void experiments.load_next_page()} pending={experiments.is_fetching_next_page}>Load more plans</Button>}
      </section>
    </div>
    <section className={styles.work} aria-labelledby="work-heading"><div className={styles.sectionHead}><h2 id="work-heading">Active work and blockers</h2><Link href={hrefs.view(project_id, "runs")}>Open Tracker →</Link></div>
      {workspace.data?.active_run_ids.length ? <ul className={styles.runList}>{workspace.data.active_run_ids.map(id => <ActiveRunRow key={id} project_id={project_id} run_id={id} />)}</ul> : <p className={styles.note}>No runs are active. Inspect past work in Tracker or direct the next investigation in Chat.</p>}
    </section>
    <ResultsPreview project_id={project_id} run={latestRun.data} report={reportQuery.data} pending={!!workspace.data?.latest_report_artifact_id && reportQuery.is_loading} />
    <details className={styles.reportTools}><summary>Generate a Markdown report</summary><div className={reportStyles.screen}><ReportComposer project_id={project_id} /></div></details>
    <AddSourceDialog project_id={project_id} open={addingSource} onClose={() => setAddingSource(false)} onCreated={() => setAddingSource(false)} />
    <Sheet open={!!(sourceId || claimId)} onClose={closeLinkedRecord} title="Linked research material">{linkedFile ? <MaterialInspector project_id={project_id} file_id={linkedFile.id} /> : linkedFiles.error ? <ErrorNotice {...describeError(linkedFiles.error, "Linked record could not be loaded")} /> : linkedFiles.is_loading || linkedFiles.has_next_page ? <p>Finding the linked record…</p> : <p>This record is not available in the project catalog.</p>}</Sheet>
  </div>;
}

function ActiveRunRow({ project_id, run_id }: { project_id: ID; run_id: ID }) {
  const query = useRun(project_id, run_id);
  if (query.error) return <li><ErrorNotice {...describeError(query.error, "Run could not be loaded")} action={<Button onClick={query.refetch}>Retry run</Button>} /></li>;
  if (!query.data) return <li><Skeleton height="3rem" /></li>;
  const run = query.data;
  return <li><div><StatusBadge tone={run.status === "awaiting_approval" ? "warning" : run.status === "failed" ? "error" : "info"}>{run.status.replaceAll("_", " ")}</StatusBadge><span>{run.input.kind === "analysis" ? "Experiment analysis" : run.input.kind === "report" ? "Report generation" : "Research run"}</span></div><p>{run.progress.message || run.phase}</p>{run.error && <p>{run.error.message}</p>}<Link href={hrefs.run(project_id, run.id)}>Inspect run →</Link></li>;
}

function ResultsPreview({ project_id, run, report, pending }: { project_id: ID; run?: Run; report?: Artifact; pending: boolean }) {
  return <section className={styles.results}><div className={styles.sectionHead}><h2>Latest report and results</h2>{run && <Link href={hrefs.run(project_id, run.id)}>Open run →</Link>}</div>
    {run ? <><p className={styles.callout}>{run.result_summary ?? `Run ${run.status.replaceAll("_", " ")}. No result summary was saved.`}</p><p className={styles.note}>Run {run.id.slice(-8)} · saved {new Date(run.created_at).toLocaleString()} · {run.status}. Execution state does not establish a scientific conclusion.</p>{run.input.kind === "analysis" && <SavedRunVisuals project_id={project_id} run={run} />}{run.provenance_artifact_id && <Link href={hrefs.artifact(project_id, run.provenance_artifact_id)}>Inspect provenance →</Link>}</> : <p className={styles.note}>Saved outputs appear here when available. Browse Materials or Tracker for the full project history.</p>}
    {pending ? <Skeleton height="2rem" /> : report && <p className={styles.report}><Link href={hrefs.report(project_id, report.id)}>{report.filename}</Link><span>{report.origin} · saved report</span></p>}
  </section>;
}

function SavedRunVisuals({ project_id, run }: { project_id: ID; run: Run }) {
  const results = useRunResults(project_id, run.id), measurements = useMeasurements(project_id, run.id);
  if (!results.data) return null;
  const first = measurements.items[0];
  return <div className={styles.savedVisuals}><ChartGallery project_id={project_id} chart_ids={results.data.chart_artifact_ids.slice(0, 1)} media_ids={[]} />
    {results.data.measurement_count > 0 && <p className={styles.note}>{results.data.measurement_count} saved measurements. {first ? `First loaded ${first.quantity} measurement: ${first.data_origin}, calibration ${first.calibration_mode}${first.uncertainty.absolute != null ? `, uncertainty ±${first.uncertainty.absolute} ${first.unit}` : ", uncertainty not recorded"}. Inspect the run for each measurement's qualifications.` : "Inspect the run for individual origins, calibration, and uncertainty."}</p>}
    {results.data.warnings.map((warning, index) => <p key={`${warning.code}:${index}`} className={styles.note}>{warning.message}</p>)}
  </div>;
}
