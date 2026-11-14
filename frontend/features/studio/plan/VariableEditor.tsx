"use client";
import { useId } from "react";
import type { Variable } from "@/contracts/api";
import { Button, CloseIcon, IconButton, PlusIcon } from "@/components/ui";
import styles from "../studio.module.css";

type Props = { variables: Variable[]; onChange: (v: Variable[]) => void; disabled?: boolean };

const ROLES: { id: Variable["role"]; label: string }[] = [
  { id: "independent", label: "Independent" },
  { id: "dependent", label: "Dependent" },
  { id: "controlled", label: "Controlled" },
];

export function VariableEditor({ variables, onChange, disabled }: Props) {
  const id = useId();
  const set = (i: number, patch: Partial<Variable>) => onChange(variables.map((v, j) => (j === i ? { ...v, ...patch } : v)));

  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.legend}>Variables</legend>
      <p className={styles.muted}>Leave the unit empty when it is not yet known. Use px for pixel measurements and 1 for ratios.</p>
      {variables.length === 0 && <p className={styles.muted}>No variables yet.</p>}
      <ol className={styles.variableRows}>
        {variables.map((v, i) => (
          <li key={i} className={styles.variableRow}>
            <div className={styles.varField}>
              <label htmlFor={`${id}-n${i}`} className={styles.smallLabel}>Name</label>
              <input id={`${id}-n${i}`} className={styles.input} value={v.name} disabled={disabled} onChange={(e) => set(i, { name: e.target.value })} />
            </div>
            <div className={styles.varField}>
              <label htmlFor={`${id}-r${i}`} className={styles.smallLabel}>Role</label>
              <select id={`${id}-r${i}`} className={styles.input} value={v.role} disabled={disabled}
                onChange={(e) => set(i, { role: e.target.value as Variable["role"] })}>
                {ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
              </select>
            </div>
            <div className={styles.varField}>
              <label htmlFor={`${id}-u${i}`} className={styles.smallLabel}>Unit</label>
              <input id={`${id}-u${i}`} className={`${styles.input} ${styles.mono}`} value={v.unit ?? ""} disabled={disabled}
                placeholder="unknown" onChange={(e) => set(i, { unit: e.target.value.trim() ? e.target.value : null })} />
            </div>
            <div className={`${styles.varField} ${styles.varDesc}`}>
              <label htmlFor={`${id}-d${i}`} className={styles.smallLabel}>Description</label>
              <input id={`${id}-d${i}`} className={styles.input} value={v.description} disabled={disabled} onChange={(e) => set(i, { description: e.target.value })} />
            </div>
            <IconButton label={`Remove variable ${v.name || i + 1}`} icon={<CloseIcon />} disabled={disabled}
              onClick={() => onChange(variables.filter((_, j) => j !== i))} className={styles.varRemove} />
          </li>
        ))}
      </ol>
      <div>
        <Button disabled={disabled} onClick={() => onChange([...variables, { name: "", role: "independent", description: "", unit: null }])}>
          <PlusIcon /> Add variable
        </Button>
      </div>
    </fieldset>
  );
}
