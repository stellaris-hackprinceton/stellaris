"use client";
import { useId, useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import styles from "./ui.module.css";

export type TabItem = { id: string; label: string; content: ReactNode };
export type TabsProps = {
  items: TabItem[];
  /** Controlled selection, so callers can mirror it in the URL. */
  value: string;
  onChange: (id: string) => void;
  label: string;
};

export function Tabs({ items, value, onChange, label }: TabsProps) {
  const base = useId();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const current = items.find((i) => i.id === value) ?? items[0];

  function onKey(e: KeyboardEvent, index: number) {
    const last = items.length - 1;
    const next = e.key === "ArrowRight" ? (index === last ? 0 : index + 1)
      : e.key === "ArrowLeft" ? (index === 0 ? last : index - 1)
      : e.key === "Home" ? 0 : e.key === "End" ? last : null;
    if (next === null) return;
    e.preventDefault();
    onChange(items[next].id);
    refs.current[next]?.focus();
  }

  return (
    <div>
      <div role="tablist" aria-label={label} className={styles.tabList}>
        {items.map((item, i) => (
          <button
            key={item.id}
            ref={(el) => { refs.current[i] = el; }}
            role="tab"
            type="button"
            id={`${base}-t-${item.id}`}
            aria-selected={item.id === current?.id}
            aria-controls={`${base}-p-${item.id}`}
            tabIndex={item.id === current?.id ? 0 : -1}
            className={styles.tab}
            onClick={() => onChange(item.id)}
            onKeyDown={(e) => onKey(e, i)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {current && (
        <div role="tabpanel" tabIndex={0} id={`${base}-p-${current.id}`} aria-labelledby={`${base}-t-${current.id}`} className={styles.tabPanel}>
          {current.content}
        </div>
      )}
    </div>
  );
}
