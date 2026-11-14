"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { PlusIcon } from "./icons";
import styles from "./desk.module.css";

/** A stable section of the research desk, shared with dedicated libraries. */
export function DeskShelf({ title, headingId, action, children, footer }: {
  title: string; headingId: string; action?: ReactNode; children: ReactNode; footer?: ReactNode;
}) {
  return <section className={styles.shelf} aria-labelledby={headingId}>
    <header className={styles.heading}><h2 id={headingId}>{title}</h2>{action}</header>
    {children}
    {footer}
  </section>;
}

export function DeskGrid({ children }: { children: ReactNode }) {
  return <ul className={styles.grid}>{children}</ul>;
}

export function DeskAddTile({ label, onClick, href, disabled, expanded, controls }: {
  label: string; onClick?: () => void; href?: string; disabled?: boolean; expanded?: boolean; controls?: string;
}) {
  const body = <><PlusIcon /><span>{label}</span></>;
  return href && !disabled
    ? <Link className={styles.addTile} href={href}>{body}</Link>
    : <button type="button" className={styles.addTile} onClick={onClick} disabled={disabled} aria-expanded={expanded} aria-controls={controls}>{body}</button>;
}
