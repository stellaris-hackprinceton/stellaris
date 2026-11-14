"use client";
import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import styles from "./ui.module.css";
import { cx } from "./cx";
import { IconButton } from "./Button";
import { CloseIcon } from "./icons";

type OverlayProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  variant: "dialog" | "sheet";
  /** Keep children mounted while closed (e.g. to preserve a draft). The closed <dialog> is not rendered visibly. */
  keepMounted?: boolean;
  className?: string;
};

/** Native <dialog> modal: focus trap, Esc handling and focus restoration come from the platform. */
function Overlay({ open, onClose, title, children, variant, keepMounted = false, className }: OverlayProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      className={cx(variant === "dialog" ? styles.dialog : styles.sheet, className)}
      // Only report closes the user initiated (Esc); a parent-driven close already knows.
      onClose={() => { if (open) onClose(); }}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}
    >
      {(open || keepMounted) && (
        <div className={styles.overlayBody}>
          <div className={styles.overlayHeader}>
            <h2 id={titleId}>{title}</h2>
            <IconButton label="Close" icon={<CloseIcon />} onClick={onClose} />
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

export type DialogProps = Omit<OverlayProps, "variant">;
export const Dialog = (p: DialogProps) => <Overlay {...p} variant="dialog" />;
export const Sheet = (p: DialogProps) => <Overlay {...p} variant="sheet" />;
