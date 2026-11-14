"use client";
import { useState } from "react";
import type { ID } from "@/contracts/api";
import { useCapabilities, useProject, useSource } from "@/lib/queries";
import { useCatalogView, type ViewFile } from "@/lib/queries/views";
import { Button, StatusBadge } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import { AddSourceDialog } from "../canvas/AddSourceDialog";
import { PROVIDER_LABEL, RETRIEVAL_LABEL } from "../canvas/labels";
import { ArxivIngestDialog, IngestRunStatus, PdfIngestDialog, type IngestRetry } from "./PaperIngest";
import { ARCHIVED_NOTE, AddTile, CardError, CardSkeleton, ListState, Widget, WidgetFooter, dateLabel, listHasBlockingState, useDisclosure } from "./Widget";
import styles from "./desk.module.css";

export type OpenSource = (source_id: ID, opener: HTMLElement | null) => void;
export const CHAT_PROMPT_EVENT = "stellaris:chat-prompt";

export function LiteratureWidget({ project_id, onOpenSource, selected }: { project_id: ID; onOpenSource: OpenSource; selected: ID | null }) {
  const disclosure = useDisclosure(3, 9);
  const list = useCatalogView(project_id, { origin_type: "source", sort: "created_at", order: "desc" }, disclosure.limit);
  const visible = list.items.slice(0, disclosure.shown);
  const blocked = listHasBlockingState(list);

  return (
    <Widget id="desk-sources" title="Sources"
      footer={<WidgetFooter label="sources" canExpand={list.has_next_page || list.items.length > disclosure.preview} expanded={disclosure.expanded} onToggle={disclosure.toggle} viewAll={hrefs.materialsView(project_id, "literature")} />}>
      {blocked ? <ListState list={list} what="Sources" skeletons={3} /> : list.items.length === 0 && <p className={styles.empty}>No sources saved yet.</p>}
      <ul className={styles.cards}>
        {!blocked && visible.map((file) => <li key={file.id}><SourceDeskCard project_id={project_id} file={file} onOpen={onOpenSource} selected={selected === file.origin?.id} /></li>)}
        {!blocked && list.error && list.items.length > 0 && <li><CardError what={list.is_next_page_error ? "More sources" : "Sources refresh"} error={list.error} retry={list.is_next_page_error ? list.load_next_page : list.refetch} /></li>}
        <li><LiteratureActions project_id={project_id} onOpenSource={onOpenSource} tile /></li>
      </ul>
    </Widget>
  );
}

/** Shared source actions for the Research desk and Materials literature view. */
export function LiteratureActions({ project_id, onOpenSource, tile = false }: { project_id: ID; onOpenSource: OpenSource; tile?: boolean }) {
  const project = useProject(project_id), capabilities = useCapabilities();
  const [menu, setMenu] = useState(false);
  const [dialog, setDialog] = useState<"reference" | "pdf" | "arxiv" | null>(null);
  const [retry, setRetry] = useState<{ key: number; value: IngestRetry | null }>({ key: 0, value: null });
  const [runs, setRuns] = useState<ID[]>([]);
  const [chatNote, setChatNote] = useState(false);
  const archived = project.data?.status === "archived";
  const fullText = capabilities.data?.features.full_text_papers === true;
  const accepted = (id: ID) => { setRuns((r) => [id, ...r.filter((x) => x !== id)]); setDialog(null); setRetry((r) => ({ key: r.key + 1, value: null })); };
  function choose(next: "reference" | "pdf" | "arxiv") { setMenu(false); setRetry((r) => ({ key: r.key + 1, value: null })); setDialog(next); }
  function askChat() {
    setMenu(false);
    window.dispatchEvent(new CustomEvent(CHAT_PROMPT_EVENT, { detail: "Find public arXiv literature relevant to this project's research question. Summarize what the retrieved abstracts support and what they do not." }));
    setChatNote(true);
  }

  return <div className={styles.stack}>
    {runs.length > 0 && <ul className={styles.strip} style={{ listStyle: "none" }} aria-label="Paper ingestion">
      {runs.map((id) => <IngestRunStatus key={id} project_id={project_id} run_id={id}
        onOpenSource={(sid) => onOpenSource(sid, null)}
        onDismiss={() => setRuns((r) => r.filter((x) => x !== id))}
        onRetry={(value) => { setRetry((r) => ({ key: r.key + 1, value })); setDialog(value.mode); }} />)}
    </ul>}
    {tile
      ? <AddTile label="Add source" disabled={archived} expanded={menu} controls="desk-add-source-menu" onClick={() => setMenu((m) => !m)} />
      : <Button disabled={archived} aria-expanded={menu} aria-controls="desk-add-source-menu" onClick={() => setMenu((m) => !m)}>Add source</Button>}
    {archived && <p className={styles.meta}>{ARCHIVED_NOTE}</p>}
    {menu && !archived && <div id="desk-add-source-menu" className={styles.menu}>
      <Button onClick={() => choose("reference")}>Add reference</Button>
      {fullText && <Button onClick={() => choose("pdf")}>Upload PDF</Button>}
      {fullText && <Button onClick={() => choose("arxiv")}>Retrieve arXiv full text</Button>}
      <Button onClick={askChat}>Find literature in Chat</Button>
    </div>}
    {chatNote && <p role="status" className={styles.meta}>A prompt was placed in Assistant. Open Assistant to edit and send it. Nothing was sent.</p>}
    <AddSourceDialog project_id={project_id} open={dialog === "reference"} onClose={() => setDialog(null)} onCreated={() => setDialog(null)} />
    {fullText && <PdfIngestDialog key={`pdf-${retry.key}`} project_id={project_id} open={dialog === "pdf"} onClose={() => setDialog(null)} onAccepted={(run) => accepted(run.id)}
      retry={retry.value?.mode === "pdf" ? retry.value : null} />}
    {fullText && <ArxivIngestDialog key={`arxiv-${retry.key}`} project_id={project_id} open={dialog === "arxiv"} onClose={() => setDialog(null)} onAccepted={(run) => accepted(run.id)}
      initialId={retry.value?.mode === "arxiv" ? retry.value.arxiv_id : undefined} />}
  </div>;
}

function authorsLine(authors: string[]) {
  if (!authors.length) return null;
  return authors.length > 2 ? `${authors.slice(0, 2).join(", ")} et al.` : authors.join(", ");
}

function SourceDeskCard({ project_id, file, onOpen, selected }: { project_id: ID; file: ViewFile; onOpen: OpenSource; selected: boolean }) {
  const query = useSource(project_id, file.origin?.id);
  const s = query.data;
  if (!file.origin) return <div className={styles.card}><p className={styles.unavailable}>Source record unavailable.</p></div>;
  if (query.error && !s) return <CardError what="Source" error={query.error} retry={query.refetch} />;
  if (!s) return <CardSkeleton />;
  const retrieval = RETRIEVAL_LABEL[s.retrieval_status];
  const byline = [authorsLine(s.authors), s.published_at?.slice(0, 4)].filter(Boolean).join(" · ");
  return (
    <article className={styles.card} data-selected={selected}>
      <button type="button" className={styles.title} onClick={(e) => onOpen(s.id, e.currentTarget)}>{s.title}</button>
      {byline && <p className={styles.meta}>{byline}</p>}
      <p className={styles.meta}><strong>Abstract</strong></p>
      <p className={styles.clamp3}>{s.abstract || <span className={styles.unavailable}>No abstract saved.</span>}</p>
      <div className={styles.badges}>
        <StatusBadge tone={retrieval.tone}>{retrieval.text}</StatusBadge>
        {s.full_text?.truncated && <StatusBadge tone="warning">Partial extraction</StatusBadge>}
      </div>
      <p className={styles.meta}>Added {dateLabel(s.created_at)} · {PROVIDER_LABEL[s.provider]}</p>
    </article>
  );
}
