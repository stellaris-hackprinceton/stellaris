"use client";
import { useRef, useState } from "react";
import type { ID, Source } from "@/contracts/api";
import { useCreateSource } from "@/lib/queries";
import { Button, Dialog, ErrorNotice, Field, TextArea, TextInput, describeError, errorCode, newCommandKey } from "@/components/ui";
import { safeHref } from "./labels";
import styles from "./canvas.module.css";

type Props = { project_id: ID; open: boolean; onClose: () => void; onCreated: (s: Source) => void };

/** Manual reference entry via the documented source-creation route. Saved as metadata only. */
export function AddSourceDialog({ project_id, open, onClose, onCreated }: Props) {
  const create = useCreateSource(project_id);
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [authors, setAuthors] = useState("");
  const [doi, setDoi] = useState("");
  const [published, setPublished] = useState("");
  const [abstract, setAbstract] = useState("");
  const key = useRef<{ key: string; body: string } | null>(null);
  const [touched, setTouched] = useState(false);

  const titleErr = title.trim() ? null : "A title is required.";
  const urlErr = safeHref(url.trim()) ? null : "Enter a full http(s) link.";
  const body = {
    title: title.trim(),
    url: url.trim(),
    authors: authors.split("\n").map((a) => a.trim()).filter(Boolean),
    doi: doi.trim() || null,
    published_at: published.trim() || null,
    abstract: abstract.trim() || null,
  };

  function reset() {
    setTitle(""); setUrl(""); setAuthors(""); setDoi(""); setPublished(""); setAbstract("");
    setTouched(false); key.current = null; create.reset();
  }

  async function submit() {
    setTouched(true);
    if (titleErr || urlErr) return;
    const serialized = JSON.stringify(body);
    if (!key.current || key.current.body !== serialized) key.current = { key: newCommandKey(), body: serialized };
    try {
      const res = await create.mutateAsync({ body, idempotency_key: key.current.key });
      reset();
      onCreated(res.data);
    } catch (err) {
      if (errorCode(err) === "IDEMPOTENCY_CONFLICT") key.current = null;
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Add a reference">
      <form className={styles.stack} onSubmit={(e) => { e.preventDefault(); void submit(); }} noValidate>
        <p className={styles.muted}>Manual references are saved as metadata only. To search for papers, ask in Research Chat.</p>
        <Field label="Title" error={touched ? titleErr : null}><TextInput value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <Field label="Link" error={touched ? urlErr : null}><TextInput type="url" inputMode="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" /></Field>
        <Field label="Authors" hint="One per line. Optional."><TextArea rows={3} value={authors} onChange={(e) => setAuthors(e.target.value)} /></Field>
        <div className={styles.grid2}>
          <Field label="DOI" hint="Optional."><TextInput value={doi} onChange={(e) => setDoi(e.target.value)} /></Field>
          <Field label="Published" hint="e.g. 2024 or 2024-06-01. Optional."><TextInput value={published} onChange={(e) => setPublished(e.target.value)} /></Field>
        </div>
        <Field label="Abstract" hint="Optional."><TextArea rows={4} value={abstract} onChange={(e) => setAbstract(e.target.value)} /></Field>
        {create.error != null && (
          <ErrorNotice {...describeError(create.error, "Reference not saved")}
            message={errorCode(create.error) === "PROJECT_ARCHIVED" ? "This project is archived. Restore it to add references." : describeError(create.error).message} />
        )}
        <div className={styles.row}>
          <Button type="submit" variant="primary" pending={create.isPending}>Save reference</Button>
          <Button onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Dialog>
  );
}
