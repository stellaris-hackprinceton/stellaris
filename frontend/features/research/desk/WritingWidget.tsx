"use client";

import type { ID } from "@/contracts/api";
import { ReportCard } from "@/features/reports/ReportCard";
import { useCapabilities, useProject } from "@/lib/queries";
import { useCatalogView } from "@/lib/queries/views";
import { hrefs } from "@/components/shell/hrefs";
import { ARCHIVED_NOTE, AddTile, CardError, ListState, Widget, WidgetFooter, listHasBlockingState, useDisclosure } from "./Widget";
import styles from "./desk.module.css";

export function WritingWidget({ project_id }: { project_id: ID }) {
  const project = useProject(project_id);
  const capabilities = useCapabilities();
  const disclosure = useDisclosure(2, 6);
  const list = useCatalogView(project_id, { artifact_kinds: ["report"], sort: "created_at", order: "desc" }, disclosure.limit);
  const archived = project.data?.status === "archived";
  const allowed = project.data?.status === "active" && capabilities.data?.features.markdown_reports === true;
  const composeHref = hrefs.reports(project_id, { compose: true });
  const blocked = listHasBlockingState(list);

  return <Widget id="desk-writing" title="Writing"
    footer={<WidgetFooter label="reports" canExpand={list.has_next_page || list.items.length > disclosure.preview} expanded={disclosure.expanded} onToggle={disclosure.toggle} viewAll={hrefs.view(project_id, "reports")} />}>
    {blocked ? <ListState list={list} what="Reports" skeletons={2} /> : list.items.length === 0 && <p className={styles.empty}>Generate a report from recorded analysis.</p>}
    <ul className={styles.cards}>
      {!blocked && list.items.slice(0, disclosure.shown).map((file) => <li key={file.id}>
        {file.origin?.id ? <ReportCard project_id={project_id} artifact_id={file.origin.id} /> : <div className={styles.card}><p className={styles.unavailable}>Report artifact unavailable.</p></div>}
      </li>)}
      {!blocked && list.error && list.items.length > 0 && <li><CardError what={list.is_next_page_error ? "More reports" : "Reports refresh"} error={list.error} retry={list.is_next_page_error ? list.load_next_page : list.refetch} /></li>}
      <li>
        <AddTile label="Generate report" href={allowed ? composeHref : undefined} disabled={!allowed} />
        {archived && <p className={styles.meta}>{ARCHIVED_NOTE}</p>}
        {!archived && !capabilities.is_loading && capabilities.data?.features.markdown_reports === false && <p className={styles.meta}>Report generation is not available on this backend.</p>}
      </li>
    </ul>
  </Widget>;
}
