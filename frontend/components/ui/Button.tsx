import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./ui.module.css";
import { cx } from "./cx";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "danger";
  pending?: boolean;
  children: ReactNode;
};

export function Button({ variant = "default", pending = false, disabled, className, type = "button", children, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      className={cx(styles.button, variant === "primary" && styles.primary, variant === "danger" && styles.danger, className)}
    >
      {children}
    </button>
  );
}

export type IconButtonProps = Omit<ButtonProps, "children"> & {
  /** Required accessible name; icon buttons have no visible text. */
  label: string;
  icon: ReactNode;
};

export function IconButton({ label, icon, className, ...rest }: IconButtonProps) {
  return (
    <Button {...rest} aria-label={label} title={label} className={cx(styles.iconButton, className)}>
      <span aria-hidden="true">{icon}</span>
    </Button>
  );
}
