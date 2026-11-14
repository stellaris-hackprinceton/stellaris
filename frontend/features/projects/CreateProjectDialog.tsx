"use client";
import { useRef, useState } from "react";
import type { Project } from "@/contracts/api";
import { useCreateProject } from "@/lib/queries";
import { Button, Dialog, ErrorNotice, Field, TextArea, TextInput, describeError, errorCode, newCommandKey } from "@/components/ui";
import styles from "./projects.module.css";

type Props = { open: boolean; onClose: () => void; onCreated: (p: Project) => void };

export function CreateProjectDialog({ open, onClose, onCreated }: Props) {
  const create = useCreateProject();
  const [name, setName] = useState("");
  const [question, setQuestion] = useState("");
  const [description, setDescription] = useState("");
  const [touched, setTouched] = useState(false);
  const key = useRef<{ key: string; body: string } | null>(null);

  const trimmed = name.trim();
  const nameErr = !trimmed ? "Give the project a name." : trimmed.length > 120 ? "Use 120 characters or fewer." : null;

  async function submit() {
    setTouched(true);
    if (nameErr) return;
    const body = { name: trimmed, description: description.trim(), research_question: question.trim() || null };
    const serialized = JSON.stringify(body);
    if (!key.current || key.current.body !== serialized) key.current = { key: newCommandKey(), body: serialized };
    try {
      const res = await create.mutateAsync({ body, idempotency_key: key.current.key });
      key.current = null;
      onCreated(res.data);
    } catch (err) {
      if (errorCode(err) === "IDEMPOTENCY_CONFLICT") key.current = null;
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="New research project">
      <form className={styles.form} onSubmit={(e) => { e.preventDefault(); void submit(); }} noValidate>
        <Field label="Project name" error={touched ? nameErr : null}>
          <TextInput value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoFocus />
        </Field>
        <Field label="Research question" hint="Optional. You can refine it later.">
          <TextArea rows={3} value={question} onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. How much energy does a tennis ball keep after each bounce?" />
        </Field>
        <Field label="Description" hint="Optional.">
          <TextArea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        {create.error != null && (
          <ErrorNotice {...describeError(create.error, "Project not created")}
            action={<Button onClick={() => void submit()} pending={create.isPending}>Retry submission</Button>} />
        )}
        <div className={styles.actions}>
          <Button type="submit" variant="primary" pending={create.isPending}>Create project</Button>
          <Button onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Dialog>
  );
}
