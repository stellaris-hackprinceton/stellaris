"use client";
import { useMemo, useState } from "react";
import type { ID, Source } from "@/contracts/api";
import { useCapabilities, useClaims, useProject, useSources } from "@/lib/queries";
import { Button, EmptyState, ErrorNotice, Field, PlusIcon, Select, Skeleton, describeError } from "@/components/ui";
import { AddSourceDialog } from "./AddSourceDialog";
import { SourceCard } from "./SourceCard";
import { SourceDetails } from "./SourceDetails";
import { PROVIDER_LABEL } from "./labels";
import styles from "./canvas.module.css";

type Props = { project_id: ID; selected: ID | null; onSelect: (id: ID | null) => void };

export function SourcesSection({ project_id, selected, onSelect }: Props) {
  const [provider, setProvider] = useState<Source["provider"] | "">("");
  const sources = useSources(project_id, provider ? { provider } : {});
  const claims = useClaims(project_id, {});
  const project = useProject(project_id);
  const caps = useCapabilities();
  const [adding, setAdding] = useState(false);
  const archived = project.data?.status === "archived";

  const current = useMemo(() => sources.items.find((s) => s.id === selected), [sources.items, selected]);
  const selectionMissing = selected && !current && !sources.is_loading && !sources.has_next_page;

  return (
    <div className={styles.split}>
      <div className={styles.stack}>
        <div className={styles.toolbar}>
          <Field label="Provider">
            <Select value={provider} onChange={(e) => setProvider(e.target.value as Source["provider"] | "")}>
              <option value="">All providers</option>
              {Object.entries(PROVIDER_LABEL).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </Select>
          </Field>
          <Button onClick={() => setAdding(true)} disabled={archived}><PlusIcon /> Add reference</Button>
        </div>
        {sources.error != null && sources.items.length === 0 ? (
          <ErrorNotice {...describeError(sources.error, "Sources could not be loaded")} action={<Button onClick={sources.refetch}>Try again</Button>} />
        ) : sources.is_loading ? (
          <><Skeleton height="5rem" /><Skeleton height="5rem" /></>
        ) : sources.items.length === 0 ? (
          <EmptyState title={provider ? "No sources from this provider" : "No sources yet"}>
            {caps.data?.features.literature_search
              ? "Ask Assistant to search the literature, or add a reference manually."
              : "Add a reference manually. Literature search is not enabled on this server."}
          </EmptyState>
        ) : (
          <ul className={styles.list} aria-label="Sources">
            {sources.items.map((s) => (
              <li key={s.id}><SourceCard source={s} selected={s.id === selected} onSelect={() => onSelect(s.id)} /></li>
            ))}
          </ul>
        )}
        {sources.has_next_page && <Button onClick={sources.load_next_page} pending={sources.is_fetching_next_page}>Load more sources</Button>}
      </div>
      <div className={styles.detailPane}>
        {current ? (
          <>
            <Button onClick={() => onSelect(null)} className={styles.closeDetails}>Close details</Button>
            <SourceDetails project_id={project_id} source={current} claims={claims.items} />
          </>
        ) : selectionMissing ? (
          <EmptyState title="Source unavailable" action={<Button onClick={() => onSelect(null)}>Clear selection</Button>}>
            This source is not in this project, or it does not match the current filter.
          </EmptyState>
        ) : selected ? (
          <Skeleton height="10rem" />
        ) : (
          <p className={styles.muted}>Select a source to see its abstract, links and cited excerpts.</p>
        )}
      </div>
      <AddSourceDialog project_id={project_id} open={adding} onClose={() => setAdding(false)}
        onCreated={(s) => { setAdding(false); setProvider(""); onSelect(s.id); }} />
    </div>
  );
}
