"use client";
import { useState } from "react";
import type { Artifact, Experiment, ID } from "@/contracts/api";
import { useCapabilities, useEditExperiment } from "@/lib/queries";
import {
  Button, ErrorNotice, Field, MarkdownView, Select, StatusBadge, TextArea, TextInput, describeError, errorCode,
} from "@/components/ui";
import { CalibrationEditor } from "./CalibrationEditor";
import { ConflictPanel } from "./ConflictPanel";
import { InputList } from "./InputList";
import { ListEditor } from "./ListEditor";
import { VariableEditor } from "./VariableEditor";
import { patchBody, validateDraft } from "./draft";
import type { PlanDraft } from "./draft";
import type { PlanDraftController } from "./usePlanDraft";
import styles from "../studio.module.css";

type Props = {
  project_id: ID;
  experiment: Experiment;
  etag: string | null;
  plan: PlanDraftController;
  inputs: Map<ID, Artifact>;
  archived: boolean;
  refetch: () => void;
};

/** Strip blank list rows before saving; the editor keeps them while typing. */
function clean(d: Partial<PlanDraft>): Partial<PlanDraft> {
  const out = { ...d };
  if (out.success_criteria) out.success_criteria = out.success_criteria.map((x) => x.trim()).filter(Boolean);
  if (out.limitations) out.limitations = out.limitations.map((x) => x.trim()).filter(Boolean);
  if (out.calibration) out.calibration = { ...out.calibration, assumptions: out.calibration.assumptions.map((x) => x.trim()).filter(Boolean) };
  if (out.title !== undefined) out.title = out.title.trim();
  return out;
}

export function ExperimentEditor({ project_id, experiment, etag, plan, inputs, archived, refetch }: Props) {
  const edit = useEditExperiment(project_id, experiment.id);
  const caps = useCapabilities();
  const [preview, setPreview] = useState(false);
  const [showIssues, setShowIssues] = useState(false);
  const d = plan.draft;
  if (!d || !plan.base) return null;

  const issues = validateDraft(d);
  const issueFor = (f: string) => (showIssues ? issues.find((i) => i.field === f)?.message ?? null : null);
  const set = <K extends keyof PlanDraft>(k: K, v: PlanDraft[K]) => plan.setDraft((x) => ({ ...x, [k]: v }));
  const locked = archived || edit.isPending;
  const resolvedInputs = d.input_artifact_ids.map((id) => inputs.get(id)).filter((a): a is Artifact => Boolean(a));

  async function save() {
    setShowIssues(true);
    if (!etag || !d || !plan.base || issues.length || plan.remoteNewer) return;
    const body = clean(patchBody(plan.base, d));
    if (Object.keys(body).length === 0) return;
    try {
      const res = await edit.mutateAsync({ body, etag });
      plan.markSaved(res.data);
      setShowIssues(false);
    } catch (err) {
      if (errorCode(err) === "REVISION_CONFLICT") refetch();
    }
  }

  return (
    <form className={styles.editor} onSubmit={(e) => { e.preventDefault(); void save(); }} noValidate aria-label="Experiment plan">
      <div className={styles.saveBar}>
        <span className={styles.saveState} role="status">
          {plan.dirty
            ? <StatusBadge tone="warning">Unsaved changes</StatusBadge>
            : <StatusBadge tone="neutral">Saved · revision {experiment.revision}</StatusBadge>}
        </span>
        <Button onClick={plan.discard} disabled={!plan.dirty || locked}>Discard changes</Button>
        <Button type="submit" variant="primary" pending={edit.isPending} disabled={!plan.dirty || archived || plan.remoteNewer || !etag}>
          Save plan
        </Button>
      </div>
      {archived && <p className={styles.note}>This project is archived. The plan is read-only until the project is restored.</p>}

      {plan.remoteNewer && <ConflictPanel plan={plan} savedRevision={experiment.revision} />}
      {edit.error != null && errorCode(edit.error) !== "REVISION_CONFLICT" && (
        <ErrorNotice {...describeError(edit.error, "Plan not saved")} />
      )}
      {showIssues && issues.length > 0 && (
        <div role="alert" className={styles.issues}>
          <p><strong>Fix these before saving:</strong></p>
          <ul>{issues.map((i, k) => <li key={k}>{i.message}</li>)}</ul>
        </div>
      )}

      <section className={styles.section} aria-labelledby="plan-protocol">
        <h3 id="plan-protocol">Protocol</h3>
        <Field label="Title" error={issueFor("title")}>
          <TextInput value={d.title} disabled={locked} onChange={(e) => set("title", e.target.value)} />
        </Field>
        <Field label="Hypothesis" error={issueFor("hypothesis")}>
          <TextArea rows={3} value={d.hypothesis} disabled={locked} onChange={(e) => set("hypothesis", e.target.value)} />
        </Field>
        <Field label="Method">
          <Select value={d.method} disabled={locked} onChange={(e) => set("method", e.target.value as PlanDraft["method"])}>
            <option value="physical">Physical</option>
            <option value="computational">Computational</option>
            <option value="hybrid">Hybrid</option>
          </Select>
        </Field>
        <div className={styles.protocolHead}>
          <span className={styles.smallLabel}>Steps (Markdown)</span>
          <Button onClick={() => setPreview(!preview)} aria-pressed={preview}>{preview ? "Edit" : "Preview"}</Button>
        </div>
        {preview
          ? <div className={styles.previewBox}><MarkdownView markdown={d.protocol_markdown || "_No protocol yet._"} /></div>
          : <TextArea aria-label="Protocol steps" rows={10} className={styles.mono} value={d.protocol_markdown} disabled={locked}
              onChange={(e) => set("protocol_markdown", e.target.value)} />}
      </section>

      <section className={styles.section}>
        <VariableEditor variables={d.variables} disabled={locked} onChange={(v) => set("variables", v)} />
        <ListEditor label="Success criteria" addLabel="Add criterion" items={d.success_criteria} disabled={locked}
          onChange={(v) => set("success_criteria", v)} />
      </section>

      <section className={styles.section}>
        <InputList project_id={project_id} ids={d.input_artifact_ids} inputs={inputs} disabled={locked}
          calibrationArtifactId={d.calibration.mode === "reference_length" ? d.calibration.artifact_id : null}
          onRemove={(id) => set("input_artifact_ids", d.input_artifact_ids.filter((x) => x !== id))} />
      </section>

      <section className={styles.section}>
        <CalibrationEditor project_id={project_id} calibration={d.calibration} inputs={resolvedInputs} disabled={locked}
          imageWorkflowEnabled={Boolean(caps.data?.features.image_analysis)}
          onChange={(c) => set("calibration", c)} />
        {issueFor("calibration") && <p className={styles.fieldError}>{issueFor("calibration")}</p>}
      </section>

      <section className={styles.section}>
        <ListEditor label="Limitations" addLabel="Add limitation" items={d.limitations} disabled={locked}
          onChange={(v) => set("limitations", v)} />
      </section>
    </form>
  );
}
