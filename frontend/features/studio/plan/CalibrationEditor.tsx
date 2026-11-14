"use client";
import { useId } from "react";
import type { Artifact, Calibration, ID } from "@/contracts/api";
import { artifactContentUrl } from "@/lib/api";
import { StatusBadge } from "@/components/ui";
import { ImagePointPicker } from "./ImagePointPicker";
import { ListEditor } from "./ListEditor";
import styles from "../studio.module.css";

type Props = {
  project_id: ID;
  calibration: Calibration;
  onChange: (c: Calibration) => void;
  /** Resolved attached inputs (ready artifacts). */
  inputs: Artifact[];
  imageWorkflowEnabled: boolean;
  disabled?: boolean;
};

/**
 * Calibration modes:
 * - "none": the supported default. Measurements stay in px / native units; physical scale is never guessed.
 * - "reference_length": editable only for an attached still image (frame 0, native dimensions), when
 *   the server supports image analysis. For video there is no authoritative decoded-frame route in the
 *   contract, so interactive point selection is unavailable; an existing saved video calibration is
 *   shown read-only and can be switched back to "none".
 */
export function CalibrationEditor({ project_id, calibration: c, onChange, inputs, imageWorkflowEnabled, disabled }: Props) {
  const id = useId();
  const images = inputs.filter((a) => a.kind === "image" && a.metadata.width_px && a.metadata.height_px);
  const canEditReference = imageWorkflowEnabled && images.length > 0;
  const refArtifact = c.mode === "reference_length" ? inputs.find((a) => a.id === c.artifact_id) : undefined;
  const savedVideoReference = c.mode === "reference_length" && refArtifact?.kind !== "image";

  function setMode(mode: Calibration["mode"]) {
    if (mode === c.mode) return;
    if (mode === "none") onChange({ mode: "none", assumptions: c.assumptions });
    else {
      const img = images[0];
      if (!img) return;
      onChange({
        mode: "reference_length", artifact_id: img.id, frame_index: 0,
        point_a_px: [0, 0], point_b_px: [0, 0], reference_length_m: 0, reference_uncertainty_m: null,
        assumptions: c.assumptions,
      });
    }
  }

  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.legend}>Calibration</legend>
      <div className={styles.radioRow} role="radiogroup" aria-label="Calibration mode">
        <label className={styles.radio}>
          <input type="radio" name={`${id}-mode`} checked={c.mode === "none"} disabled={disabled} onChange={() => setMode("none")} />
          <span><strong>None</strong> — report pixels and dimensionless ratios</span>
        </label>
        <label className={styles.radio}>
          <input type="radio" name={`${id}-mode`} checked={c.mode === "reference_length"}
            disabled={disabled || (!canEditReference && c.mode !== "reference_length")}
            onChange={() => setMode("reference_length")} />
          <span><strong>Reference length</strong> — convert pixels to meters from a known distance</span>
        </label>
      </div>

      {c.mode === "none" && (
        <p className={styles.note}>
          Without calibration, distances stay in pixels. Physical units are not inferred from the camera, frame rate, or object size.
          Bounce-height ratios can still be reported under stated assumptions.
        </p>
      )}
      {c.mode !== "reference_length" && !canEditReference && (
        <p className={styles.muted}>
          {imageWorkflowEnabled
            ? "Reference-length calibration needs an attached still image of the scale."
            : "Reference-length calibration from video needs exact frame access, which the server does not provide yet. Pixel-based analysis is fully supported."}
        </p>
      )}

      {c.mode === "reference_length" && savedVideoReference && (
        <div className={styles.note}>
          <p><StatusBadge tone="warning">Read only</StatusBadge> This saved calibration refers to {refArtifact ? `“${refArtifact.filename}”` : "an input that is not loaded"}, frame {c.frame_index}.
            Video frames cannot be selected interactively yet, so it can be inspected but not edited here.</p>
          <dl className={styles.dl}>
            <dt>Point A</dt><dd className={styles.mono}>{c.point_a_px.join(", ")} px</dd>
            <dt>Point B</dt><dd className={styles.mono}>{c.point_b_px.join(", ")} px</dd>
            <dt>Length</dt><dd className={styles.mono}>{c.reference_length_m} m{c.reference_uncertainty_m != null ? ` ± ${c.reference_uncertainty_m} m` : " (uncertainty not stated)"}</dd>
          </dl>
        </div>
      )}

      {c.mode === "reference_length" && !savedVideoReference && (
        <ReferenceFields project_id={project_id} c={c} images={images} onChange={onChange} disabled={disabled} />
      )}

      <ListEditor label="Assumptions" addLabel="Add assumption" items={c.assumptions} disabled={disabled}
        hint="e.g. the ball moves in a plane parallel to the camera; the floor is the baseline."
        onChange={(assumptions) => onChange({ ...c, assumptions })} />
    </fieldset>
  );
}

type RefCal = Extract<Calibration, { mode: "reference_length" }>;

function ReferenceFields({ project_id, c, images, onChange, disabled }: {
  project_id: ID; c: RefCal; images: Artifact[]; onChange: (c: Calibration) => void; disabled?: boolean;
}) {
  const id = useId();
  const img = images.find((a) => a.id === c.artifact_id) ?? images[0];
  const w = img?.metadata.width_px ?? 0;
  const h = img?.metadata.height_px ?? 0;
  const unset = (p: [number, number]) => p[0] === 0 && p[1] === 0;
  const num = (v: string) => (v.trim() === "" ? NaN : Number(v));
  const setPt = (which: "point_a_px" | "point_b_px", axis: 0 | 1, v: string) => {
    const p: [number, number] = [...c[which]];
    p[axis] = num(v);
    onChange({ ...c, [which]: p });
  };
  const outOfFrame = [c.point_a_px, c.point_b_px].some(([x, y]) => x > w || y > h);

  return (
    <div className={styles.stack}>
      {images.length > 1 && (
        <div className={styles.varField}>
          <label htmlFor={`${id}-img`} className={styles.smallLabel}>Calibration image</label>
          <select id={`${id}-img`} className={styles.input} value={c.artifact_id} disabled={disabled}
            onChange={(e) => onChange({ ...c, artifact_id: e.target.value, frame_index: 0, point_a_px: [0, 0], point_b_px: [0, 0] })}>
            {images.map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}
          </select>
        </div>
      )}
      {img && (
        <ImagePointPicker
          src={artifactContentUrl(project_id, img.id, "inline")}
          width_px={w} height_px={h}
          a={unset(c.point_a_px) ? null : c.point_a_px}
          b={unset(c.point_b_px) ? null : c.point_b_px}
          disabled={disabled}
          onPick={(which, p) => onChange({ ...c, [which === "a" ? "point_a_px" : "point_b_px"]: p })}
        />
      )}
      <p className={styles.muted}>Image is {w} × {h} px. Origin is top-left; x right, y down.</p>
      <div className={styles.grid4}>
        {(["point_a_px", "point_b_px"] as const).map((k) => (["x", "y"] as const).map((axis, ai) => (
          <div key={`${k}${axis}`} className={styles.varField}>
            <label htmlFor={`${id}-${k}-${axis}`} className={styles.smallLabel}>{k === "point_a_px" ? "A" : "B"} {axis} (px)</label>
            <input id={`${id}-${k}-${axis}`} type="number" step="0.1" min={0} max={axis === "x" ? w : h}
              className={`${styles.input} ${styles.mono}`} disabled={disabled}
              value={Number.isFinite(c[k][ai]) ? c[k][ai] : ""} onChange={(e) => setPt(k, ai as 0 | 1, e.target.value)} />
          </div>
        )))}
      </div>
      {outOfFrame && <p className={styles.fieldError} role="alert">Points must lie inside the {w} × {h} px image.</p>}
      <div className={styles.grid2}>
        <div className={styles.varField}>
          <label htmlFor={`${id}-len`} className={styles.smallLabel}>Reference length (m)</label>
          <input id={`${id}-len`} type="number" step="any" min={0} className={`${styles.input} ${styles.mono}`} disabled={disabled}
            value={Number.isFinite(c.reference_length_m) && c.reference_length_m !== 0 ? c.reference_length_m : ""} onChange={(e) => onChange({ ...c, reference_length_m: num(e.target.value) })} />
        </div>
        <div className={styles.varField}>
          <label htmlFor={`${id}-unc`} className={styles.smallLabel}>Length uncertainty (m, optional)</label>
          <input id={`${id}-unc`} type="number" step="any" min={0} className={`${styles.input} ${styles.mono}`} disabled={disabled}
            value={c.reference_uncertainty_m != null && Number.isFinite(c.reference_uncertainty_m) ? c.reference_uncertainty_m : ""} placeholder="not stated"
            onChange={(e) => onChange({ ...c, reference_uncertainty_m: e.target.value.trim() === "" ? null : num(e.target.value) })} />
        </div>
      </div>
    </div>
  );
}
