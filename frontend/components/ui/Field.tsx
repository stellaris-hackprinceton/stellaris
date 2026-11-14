"use client";
import { createContext, useContext, useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import styles from "./ui.module.css";
import { cx } from "./cx";

type FieldCtx = { id: string; describedBy?: string; invalid: boolean };
const Ctx = createContext<FieldCtx | null>(null);

export type FieldProps = {
  label: string;
  hint?: string;
  error?: string | null;
  children: ReactNode;
};

/** Wraps one control with a visible label, hint and error. Controls read ids from context. */
export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId();
  const describedBy = [hint && `${id}-hint`, error && `${id}-err`].filter(Boolean).join(" ") || undefined;
  return (
    <Ctx.Provider value={{ id, describedBy, invalid: Boolean(error) }}>
      <div className={styles.field}>
        <label htmlFor={id} className={styles.label}>{label}</label>
        {children}
        {hint && <span id={`${id}-hint`} className={styles.hint}>{hint}</span>}
        {error && <span id={`${id}-err`} role="alert" className={styles.fieldError}>{error}</span>}
      </div>
    </Ctx.Provider>
  );
}

function useFieldProps() {
  const c = useContext(Ctx);
  return c ? { id: c.id, "aria-describedby": c.describedBy, "aria-invalid": c.invalid || undefined } : {};
}

export function TextInput({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input type="text" {...useFieldProps()} {...rest} className={cx(styles.input, className)} />;
}

export function TextArea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...useFieldProps()} {...rest} className={cx(styles.input, className)} />;
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...useFieldProps()} {...rest} className={cx(styles.input, className)}>{children}</select>;
}
