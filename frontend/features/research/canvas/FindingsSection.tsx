"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Claim, ID } from "@/contracts/api";
import { useClaims, useSources } from "@/lib/queries";
import { Button, EmptyState, ErrorNotice, Field, Select, Skeleton, describeError } from "@/components/ui";
import { CLAIM_KIND_LABEL } from "../chat";
import { ClaimCard } from "./ClaimCard";
import styles from "./canvas.module.css";

type Props = { project_id: ID; selected: ID | null; onSelectSource: (id: ID) => void };

export function FindingsSection({ project_id, selected, onSelectSource }: Props) {
  const claims = useClaims(project_id, {});
  const sources = useSources(project_id, {});
  const [kind, setKind] = useState<Claim["kind"] | "">("");
  const sourceMap = useMemo(() => new Map(sources.items.map((s) => [s.id, s])), [sources.items]);
  // A linked claim stays visible even when the kind filter would hide it.
  const shown = kind ? claims.items.filter((c) => c.kind === kind || c.id === selected) : claims.items;
  const selectedRef = useRef<HTMLElement>(null);
  const selectedLoaded = selected != null && claims.items.some((c) => c.id === selected);

  // Selected claim may sit on a later page: keep loading until found or exhausted.
  const { has_next_page, is_fetching_next_page, load_next_page } = claims;
  useEffect(() => {
    if (selected && !selectedLoaded && has_next_page && !is_fetching_next_page) load_next_page();
  }, [selected, selectedLoaded, has_next_page, is_fetching_next_page, load_next_page]);

  useEffect(() => {
    if (selectedLoaded) {
      selectedRef.current?.scrollIntoView({ block: "center" });
      selectedRef.current?.focus({ preventScroll: true });
    }
  }, [selectedLoaded, selected]);

  if (claims.error != null && claims.items.length === 0) {
    return <ErrorNotice {...describeError(claims.error, "Findings could not be loaded")} action={<Button onClick={claims.refetch}>Try again</Button>} />;
  }
  if (claims.is_loading) return <><Skeleton height="6rem" /><Skeleton height="6rem" /></>;

  return (
    <div className={styles.stack}>
      <p className={styles.muted}>
        Observations are backed by measurements or evidence. Inferences add stated assumptions or citations. Hypotheses are proposals, not results.
      </p>
      {claims.items.length > 0 && (
        <div className={styles.toolbar}>
          <Field label="Show">
            <Select value={kind} onChange={(e) => setKind(e.target.value as Claim["kind"] | "")}>
              <option value="">All findings</option>
              {Object.entries(CLAIM_KIND_LABEL).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </Select>
          </Field>
        </div>
      )}
      {selected && !selectedLoaded && !has_next_page && (
        <EmptyState title="Finding unavailable">The linked finding is not in this project.</EmptyState>
      )}
      {claims.items.length === 0 ? (
        <EmptyState title="No findings yet">Ask a research question in chat or run an analysis. Saved observations, inferences, and hypotheses appear here.</EmptyState>
      ) : shown.length === 0 ? (
        <EmptyState title="No matching findings" />
      ) : (
        <ul className={styles.list} aria-label="Findings">
          {shown.map((c) => (
            <li key={c.id}>
              <ClaimCard
                ref={c.id === selected ? selectedRef : undefined}
                project_id={project_id}
                claim={c}
                sources={sourceMap}
                selected={c.id === selected}
                onSelectSource={onSelectSource}
              />
            </li>
          ))}
        </ul>
      )}
      {has_next_page && <Button onClick={load_next_page} pending={is_fetching_next_page}>Load more findings</Button>}
    </div>
  );
}
