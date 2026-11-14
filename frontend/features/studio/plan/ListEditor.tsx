"use client";
import { useId } from "react";
import { Button, CloseIcon, IconButton, PlusIcon } from "@/components/ui";
import styles from "../studio.module.css";

type Props = {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  addLabel: string;
  disabled?: boolean;
  hint?: string;
};

/** Edits a string[] field. Empty lines are kept while editing and stripped on save by the caller. */
export function ListEditor({ label, items, onChange, addLabel, disabled, hint }: Props) {
  const id = useId();
  return (
    <fieldset className={styles.fieldset} aria-describedby={hint ? `${id}-hint` : undefined}>
      <legend className={styles.legend}>{label}</legend>
      {hint && <p id={`${id}-hint`} className={styles.muted}>{hint}</p>}
      {items.length === 0 && <p className={styles.muted}>None yet.</p>}
      <ol className={styles.listRows}>
        {items.map((item, i) => (
          <li key={i} className={styles.listRow}>
            <label className="sr-only" htmlFor={`${id}-${i}`}>{`${label} ${i + 1}`}</label>
            <input
              id={`${id}-${i}`}
              className={styles.input}
              value={item}
              disabled={disabled}
              onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))}
            />
            <IconButton label={`Remove ${label.toLowerCase()} ${i + 1}`} icon={<CloseIcon />} disabled={disabled}
              onClick={() => onChange(items.filter((_, j) => j !== i))} />
          </li>
        ))}
      </ol>
      <div><Button onClick={() => onChange([...items, ""])} disabled={disabled}><PlusIcon /> {addLabel}</Button></div>
    </fieldset>
  );
}
