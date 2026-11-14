"use client";

import { useState } from "react";
import Link from "next/link";
import type { Experiment, ID } from "@/contracts/api";
import { Button } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import { useArtifact } from "@/lib/queries";
import styles from "../studio.module.css";

type Props = {
  project_id: ID;
  experiment: Experiment;
  archived: boolean;
  dirty: boolean;
  remoteNewer: boolean;
  enabled: boolean;
};

export function ExperimentImplementation({ project_id, experiment, archived, dirty, remoteNewer, enabled }: Props) {
  const implementation = experiment.implementation ?? null;
  const artifact = useArtifact(project_id, implementation?.code_artifact_id);
  const [prepared, setPrepared] = useState(false);
  const disabled = archived || dirty || remoteNewer || !enabled;

  function askAgent() {
    const prompt = [
      `${implementation ? "Revise" : "Generate"} a script for the existing experiment below.`,
      `Experiment ID: ${experiment.id}`,
      `Current experiment revision: ${experiment.revision}`,
      `Title: ${experiment.title}`,
      "Use save_experiment_implementation to attach the script to this exact experiment.",
      "Use a runtime supported by this project's execution capabilities.",
      "Do not create a replacement experiment and do not execute the script.",
      "Be honest about missing dependencies or inputs; do not invent data or claim execution results.",
    ].join("\n");
    window.dispatchEvent(new CustomEvent("stellaris:chat-prompt", { detail: prompt }));
    setPrepared(true);
  }

  const reason = archived ? "Archived projects are read-only."
    : dirty ? "Save the experiment plan before asking for script changes."
      : remoteNewer ? "Resolve the newer plan revision before asking for script changes."
        : !enabled ? "Script requests are unavailable for this project right now."
          : null;

  return (
    <div>
      <div className={styles.row} aria-label="Experiment script">
        <strong>{implementation ? "Script attached" : "No script attached"}</strong>
        {implementation && <>
          <span className={styles.muted}>{implementation.runtime}</span>
          {artifact.data?.project_id === project_id
            ? <><span className={styles.muted}>{artifact.data.filename}</span>
              <Link href={hrefs.artifact(project_id, implementation.code_artifact_id)}>View script</Link></>
            : <span className={styles.muted}>{artifact.is_loading ? "Loading filename…" : "Filename unavailable"}</span>}
        </>}
        <Button disabled={disabled} onClick={askAgent}>{implementation ? "Ask agent to revise script" : "Ask agent for script"}</Button>
      </div>
      {reason && <p className={styles.muted} role="note">{reason}</p>}
      {prepared && <p className={styles.note} role="status">Request prepared in chat. Review and send it when ready.</p>}
    </div>
  );
}
