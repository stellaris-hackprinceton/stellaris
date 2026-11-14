"use client";
import Link from "next/link";
import type { Experiment, ID } from "@/contracts/api";
import { useExperiment, useProject } from "@/lib/queries";
import { useCatalogView, type ViewFile } from "@/lib/queries/views";
import { hrefs } from "@/components/shell/hrefs";
import { METHOD_LABEL } from "../canvas/labels";
import { ARCHIVED_NOTE, AddTile, CardError, CardSkeleton, ListState, MediaPreview, Widget, WidgetFooter, dateLabel, listHasBlockingState, useDisclosure } from "./Widget";
import styles from "./desk.module.css";

/** Helpful prompts in a fixed order, not backend readiness certification. */
function nextAction(e: Experiment) {
  if (!e.hypothesis.trim()) return "Define hypothesis";
  if (!e.protocol_markdown.trim()) return "Write protocol";
  if (!e.input_artifact_ids.length) return "Add inputs";
  return "Review experiment";
}

export function ExperimentsWidget({ project_id }: { project_id: ID }) {
  const project = useProject(project_id);
  const disclosure = useDisclosure(3, 9);
  const list = useCatalogView(project_id, { origin_type: "experiment", sort: "updated_at", order: "desc" }, disclosure.limit);
  const archived = project.data?.status === "archived";
  const blocked = listHasBlockingState(list);
  return (
    <Widget id="desk-experiments" title="Experiments"
      footer={<WidgetFooter label="experiments" canExpand={list.has_next_page || list.items.length > disclosure.preview} expanded={disclosure.expanded} onToggle={disclosure.toggle} viewAll={hrefs.view(project_id, "studio")} />}>
      {blocked ? <ListState list={list} what="Experiments" skeletons={3} /> : list.items.length === 0 && <p className={styles.empty}>No experiments planned yet. Design one in Experiments.</p>}
      <ul className={styles.cards}>
        {!blocked && list.items.slice(0, disclosure.shown).map((file) => <li key={file.id}><ExperimentDeskCard project_id={project_id} file={file} /></li>)}
        {!blocked && list.error && list.items.length > 0 && <li><CardError what={list.is_next_page_error ? "More experiments" : "Experiments refresh"} error={list.error} retry={list.is_next_page_error ? list.load_next_page : list.refetch} /></li>}
        <li>
          {/* Opens Studio's creation flow; nothing is created on click. */}
          <AddTile label="New experiment" href={hrefs.studio(project_id)} disabled={archived} />
          {archived && <p className={styles.meta}>{ARCHIVED_NOTE}</p>}
        </li>
      </ul>
    </Widget>
  );
}

function ExperimentDeskCard({ project_id, file }: { project_id: ID; file: ViewFile }) {
  const query = useExperiment(project_id, file.origin?.id);
  const e = query.data;
  if (!file.origin) return <div className={styles.card}><p className={styles.unavailable}>Experiment record unavailable.</p></div>;
  if (query.error && !e) return <CardError what="Experiment" error={query.error} retry={query.refetch} />;
  if (!e) return <CardSkeleton />;
  return (
    <article className={styles.card}>
      <Link className={styles.title} href={hrefs.studio(project_id, e.id)}>{e.title}</Link>
      <p className={styles.meta}>{METHOD_LABEL[e.method]} · revision {e.revision} · {e.input_artifact_ids.length} input{e.input_artifact_ids.length === 1 ? "" : "s"} attached</p>
      <p className={styles.clamp2}>{e.hypothesis.trim() || <span className={styles.unavailable}>Hypothesis not recorded</span>}</p>
      {e.input_artifact_ids[0] && <MediaPreview project_id={project_id} artifact_id={e.input_artifact_ids[0]} />}
      <p className={styles.meta}>Last saved {dateLabel(e.updated_at)}</p>
      <div className={styles.links}><Link href={hrefs.studio(project_id, e.id)}>{nextAction(e)}</Link></div>
    </article>
  );
}
