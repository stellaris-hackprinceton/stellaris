"use client";
import { useEffect, useRef, useState } from "react";
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
  const form = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (open) form.current?.querySelector("input")?.focus();
  }, [open]);

  const trimmed = name.trim();
  const nameErr = !trimmed ? "Give the project a name." : trimmed.length > 120 ? "Use 120 characters or fewer." : null;

  async function submit() {
    if (create.isPending) return;
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
    <Dialog className={styles.createDialog} open={open} onClose={onClose} title="New research project">
      <form ref={form} className={styles.form} onSubmit={(e) => { e.preventDefault(); void submit(); }} noValidate>
        <p className={styles.formIntro}>Give your investigation a home. Your question, experiments, and evidence stay together here.</p>
        <Field label="Project name" hint="Required. Choose a name you’ll recognize later." error={touched ? nameErr : null}>
          <TextInput value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required autoFocus placeholder="e.g. Energy loss in a bouncing ball" />
        </Field>
        <Field label="Research question" hint="Optional. You can refine it later.">
          <TextArea rows={4} value={question} onChange={(e) => setQuestion(e.target.value)}
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
          <Button className={styles.primaryAction} type="submit" variant="primary" pending={create.isPending}>{create.isPending ? "Creating project…" : "Create project"}</Button>
          <Button onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Dialog>
  );
}
