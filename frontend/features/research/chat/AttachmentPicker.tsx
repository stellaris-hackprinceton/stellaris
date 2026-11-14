"use client";
import { useState } from "react";
import type { ID } from "@/contracts/api";
import { useArtifacts } from "@/lib/queries";
import { Button, Dialog, EmptyState, ErrorNotice, IconButton, PaperclipIcon, Skeleton, describeError } from "@/components/ui";
import styles from "./chat.module.css";

type Props = {
  project_id: ID;
  selected: ID[];
  onChange: (ids: ID[]) => void;
  disabled?: boolean;
};

/** Picks existing, ready project artifacts. New media is uploaded in Studio, not here. */
export function AttachmentPicker({ project_id, selected, onChange, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<ID[]>(selected);
  const artifacts = useArtifacts(project_id, {});

  function toggle(id: ID) {
    setDraft((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));
  }

  return (
    <>
      <IconButton
        label={selected.length ? `Attachments (${selected.length} selected)` : "Attach project files"}
        icon={<PaperclipIcon />}
        disabled={disabled}
        onClick={() => { setDraft(selected); setOpen(true); }}
      />
      <Dialog open={open} onClose={() => setOpen(false)} title="Attach project files">
        <p className={styles.muted}>Only files already saved in this project can be attached. Upload new recordings in Studio.</p>
        {artifacts.error != null ? (
          <ErrorNotice {...describeError(artifacts.error, "Files could not be loaded")} action={<Button onClick={artifacts.refetch}>Try again</Button>} />
        ) : artifacts.is_loading ? (
          <Skeleton height="6rem" />
        ) : artifacts.items.length === 0 ? (
          <EmptyState title="No files yet">Files appear here after they are uploaded or produced by a run.</EmptyState>
        ) : (
          <fieldset className={styles.pickerList}>
            <legend className="sr-only">Project files</legend>
            {artifacts.items.map((a) => (
              <label key={a.id} className={styles.pickerItem}>
                <input type="checkbox" checked={draft.includes(a.id)} onChange={() => toggle(a.id)} />
                <span className={styles.pickerName}>{a.filename}</span>
                <span className={styles.muted}>{a.kind} · {a.origin}</span>
              </label>
            ))}
          </fieldset>
        )}
        {artifacts.has_next_page && (
          <Button onClick={artifacts.load_next_page} pending={artifacts.is_fetching_next_page}>Load more files</Button>
        )}
        <div className={styles.actions}>
          <Button variant="primary" onClick={() => { onChange(draft); setOpen(false); }}>Use selection</Button>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
        </div>
      </Dialog>
    </>
  );
}
