"use client";
import Link from "next/link";
import type { Artifact, ID } from "@/contracts/api";
import { useArtifact } from "@/lib/queries";
import { CloseIcon, IconButton, StatusBadge } from "@/components/ui";
import { hrefs } from "@/components/shell";
import { formatDuration } from "../format";
import styles from "../studio.module.css";

type Props = {
  project_id: ID;
  ids: ID[];
  inputs: Map<ID, Artifact>;
  calibrationArtifactId: ID | null;
  onRemove: (id: ID) => void;
  disabled?: boolean;
};

export function InputList({ project_id, ids, inputs, calibrationArtifactId, onRemove, disabled }: Props) {
  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.legend}>Attached inputs</legend>
      {ids.length === 0 ? (
        <p className={styles.muted}>No inputs attached. Record or import a file below, then attach it.</p>
      ) : (
        <ul className={styles.inputRows}>
          {ids.map((id) => (
            <InputRow key={id} project_id={project_id} id={id} known={inputs.get(id)} disabled={disabled}
              usedByCalibration={id === calibrationArtifactId} onRemove={() => onRemove(id)} />
          ))}
        </ul>
      )}
      {ids.length > 0 && <p className={styles.muted}>Removing an input detaches it from this plan only; the file stays in the project.</p>}
    </fieldset>
  );
}

function InputRow({ project_id, id, known, usedByCalibration, onRemove, disabled }: {
  project_id: ID; id: ID; known: Artifact | undefined; usedByCalibration: boolean; onRemove: () => void; disabled?: boolean;
}) {
  // Only fetch individually when the artifact isn't already in a loaded list.
  const fetched = useArtifact(project_id, known ? null : id);
  const a = known ?? fetched.data;
  return (
    <li className={styles.inputRow}>
      <div className={styles.inputMain}>
        {a ? <Link href={hrefs.artifact(project_id, id)} className={styles.inputName}>{a.filename}</Link>
           : <span className={styles.muted} title={id}>{fetched.error ? "Unavailable file" : "Loading file…"}</span>}
        {a && (
          <span className={styles.muted}>
            {a.kind}
            {a.metadata.duration_ms != null && ` · ${formatDuration(a.metadata.duration_ms)}`}
            {a.metadata.width_px && a.metadata.height_px && ` · ${a.metadata.width_px}×${a.metadata.height_px}px`}
          </span>
        )}
        {a?.origin === "simulated" && <StatusBadge tone="warning">Simulated</StatusBadge>}
      </div>
      <IconButton
        label={usedByCalibration ? "Used by calibration; change calibration first" : `Detach ${a?.filename ?? "file"}`}
        icon={<CloseIcon />} disabled={disabled || usedByCalibration} onClick={onRemove} />
    </li>
  );
}
