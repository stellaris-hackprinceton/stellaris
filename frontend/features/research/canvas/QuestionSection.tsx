"use client";
import { useState } from "react";
import type { ID, Project } from "@/contracts/api";
import { useEditProject, useProject } from "@/lib/queries";
import { Button, EmptyState, ErrorNotice, Field, Skeleton, TextArea, TextInput, describeError, errorCode } from "@/components/ui";
import styles from "./canvas.module.css";

export function QuestionSection({ project_id }: { project_id: ID }) {
  const project = useProject(project_id);
  const [editing, setEditing] = useState(false);

  if (project.error != null && !project.data) {
    return <ErrorNotice {...describeError(project.error, "The project could not be loaded")} action={<Button onClick={project.refetch}>Try again</Button>} />;
  }
  if (!project.data) return <Skeleton height="6rem" />;
  const p = project.data;
  const archived = p.status === "archived";

  if (editing) {
    return <QuestionForm project={p} etag={project.etag} onDone={() => setEditing(false)} refetch={project.refetch} />;
  }
  return (
    <div className={styles.stack}>
      {p.research_question ? (
        <blockquote className={styles.question}>{p.research_question}</blockquote>
      ) : (
        <EmptyState title="No research question yet">State the question this project should answer. Stellaris uses it to guide literature search and experiment design.</EmptyState>
      )}
      {p.description && <p className="prose">{p.description}</p>}
      <div>
        <Button onClick={() => setEditing(true)} disabled={archived}>
          {p.research_question ? "Edit question" : "Add a research question"}
        </Button>
        {archived && <p className={styles.muted}>Restore the project to edit it.</p>}
      </div>
    </div>
  );
}

type FormProps = { project: Project; etag: string | null; onDone: () => void; refetch: () => void };

/** PATCH with the loaded ETag. On a 412 the draft is kept and the newer saved version is shown for comparison. */
function QuestionForm({ project, etag, onDone, refetch }: FormProps) {
  const edit = useEditProject(project.id);
  const [question, setQuestion] = useState(project.research_question ?? "");
  const [description, setDescription] = useState(project.description);
  const [name, setName] = useState(project.name);
  const [baseRevision, setBaseRevision] = useState(project.revision);
  const conflict = errorCode(edit.error) === "REVISION_CONFLICT" || project.revision !== baseRevision;
  const nameValid = name.trim().length > 0 && name.trim().length <= 120;

  async function save() {
    if (!etag || !nameValid) return;
    try {
      await edit.mutateAsync({
        body: { name: name.trim(), description, research_question: question.trim() ? question.trim() : null },
        etag,
      });
      onDone();
    } catch (err) {
      if (errorCode(err) === "REVISION_CONFLICT") refetch();
    }
  }

  return (
    <form className={styles.stack} onSubmit={(e) => { e.preventDefault(); void save(); }}>
      <Field label="Project name" error={nameValid ? null : "Enter 1–120 characters."}>
        <TextInput value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required />
      </Field>
      <Field label="Research question">
        <TextArea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} />
      </Field>
      <Field label="Description" hint="Background, constraints, or context for this research.">
        <TextArea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </Field>
      {conflict && (
        <div className={styles.conflict} role="alert">
          <p><strong>This project was changed elsewhere.</strong> Your edits are kept below. The latest saved version is:</p>
          <dl className={styles.dl}>
            <dt>Name</dt><dd>{project.name}</dd>
            <dt>Research question</dt><dd>{project.research_question ?? "None"}</dd>
            <dt>Description</dt><dd>{project.description || "None"}</dd>
          </dl>
          <div className={styles.row}>
            <Button onClick={() => { setBaseRevision(project.revision); edit.reset(); }}>Review my edits</Button>
            <Button onClick={() => {
              setName(project.name); setQuestion(project.research_question ?? ""); setDescription(project.description);
              setBaseRevision(project.revision); edit.reset();
            }}>Use the saved version</Button>
          </div>
        </div>
      )}
      {edit.error != null && !conflict && <ErrorNotice {...describeError(edit.error, "Changes not saved")} />}
      <div className={styles.row}>
        <Button type="submit" variant="primary" pending={edit.isPending} disabled={!nameValid || conflict || !etag}>Save project details</Button>
        <Button onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}
