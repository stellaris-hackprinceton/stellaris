"use client";
import { useId, useRef, useState } from "react";
import type { Experiment, ID } from "@/contracts/api";
import { useCreateExperiment } from "@/lib/queries";
import {
  Button, Dialog, ErrorNotice, Field, PlusIcon, Select, TextArea, TextInput, describeError, errorCode, newCommandKey,
} from "@/components/ui";
import { emptyDraft } from "./plan/draft";
import styles from "./studio.module.css";

type Props = {
  project_id: ID;
  experiments: Experiment[];
  selected: ID | null;
  onSelect: (id: ID) => void;
  hasMore: boolean;
  loadMore: () => void;
  dirty: boolean;
  archived: boolean;
};

export function ExperimentSelector({ project_id, experiments, selected, onSelect, hasMore, loadMore, dirty, archived }: Props) {
  const id = useId();
  const [creating, setCreating] = useState(false);

  function choose(next: ID) {
    if (next === selected) return;
    if (dirty && !window.confirm("This plan has unsaved changes. Switch experiments and discard them?")) return;
    onSelect(next);
  }

  return (
    <div className={styles.selector}>
      <div className={styles.varField}>
        <label htmlFor={`${id}-x`} className={styles.smallLabel}>Experiment</label>
        <select id={`${id}-x`} className={styles.input} value={selected ?? ""} onChange={(e) => choose(e.target.value)}>
          {!selected && <option value="" disabled>Choose an experiment</option>}
          {experiments.map((x) => <option key={x.id} value={x.id}>{x.title || "Untitled"} (rev {x.revision})</option>)}
        </select>
      </div>
      {hasMore && <Button onClick={loadMore}>Load more</Button>}
      <Button onClick={() => setCreating(true)} disabled={archived}><PlusIcon /> New experiment</Button>
      <CreateExperimentDialog project_id={project_id} open={creating} onClose={() => setCreating(false)}
        onCreated={(x) => { setCreating(false); onSelect(x.id); }} />
    </div>
  );
}

function CreateExperimentDialog({ project_id, open, onClose, onCreated }: {
  project_id: ID; open: boolean; onClose: () => void; onCreated: (x: Experiment) => void;
}) {
  const create = useCreateExperiment(project_id);
  const [title, setTitle] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [method, setMethod] = useState<Experiment["method"]>("physical");
  const [touched, setTouched] = useState(false);
  const key = useRef<{ key: string; body: string } | null>(null);
  const titleErr = title.trim() ? null : "Give the experiment a title.";
  const hypErr = hypothesis.trim() ? null : "State the hypothesis.";

  async function submit() {
    setTouched(true);
    if (titleErr || hypErr) return;
    const body = { ...emptyDraft(), title: title.trim(), hypothesis: hypothesis.trim(), method };
    const serialized = JSON.stringify(body);
    if (!key.current || key.current.body !== serialized) key.current = { key: newCommandKey(), body: serialized };
    try {
      const res = await create.mutateAsync({ body, idempotency_key: key.current.key });
      key.current = null;
      setTitle(""); setHypothesis(""); setTouched(false);
      onCreated(res.data);
    } catch (err) {
      if (errorCode(err) === "IDEMPOTENCY_CONFLICT") key.current = null;
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="New experiment">
      <form className={styles.stack} noValidate onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <p className={styles.muted}>Start a plan by hand. You can also ask Research Chat to design one.</p>
        <Field label="Title" error={touched ? titleErr : null}><TextInput value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <Field label="Hypothesis" error={touched ? hypErr : null}><TextArea rows={3} value={hypothesis} onChange={(e) => setHypothesis(e.target.value)} /></Field>
        <Field label="Method">
          <Select value={method} onChange={(e) => setMethod(e.target.value as Experiment["method"])}>
            <option value="physical">Physical</option><option value="computational">Computational</option><option value="hybrid">Hybrid</option>
          </Select>
        </Field>
        {create.error != null && <ErrorNotice {...describeError(create.error, "Experiment not created")} />}
        <div className={styles.row}>
          <Button type="submit" variant="primary" pending={create.isPending}>Create experiment</Button>
          <Button onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Dialog>
  );
}
