"use client";
import { useCallback, useRef, useSyncExternalStore, type KeyboardEvent, type PointerEvent } from "react";
import styles from "./resize.module.css";
import { cx } from "./cx";

const listeners = new Set<() => void>();
const subscribe = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };
const read = (key: string) => { try { return localStorage.getItem(key); } catch { return null; } };

const clamp = (value: number, min: number, max: number) => Math.round(Math.min(max, Math.max(min, value)));

/**
 * A panel dimension in px, saved per browser. Invalid or missing values fall back to `initial`,
 * and every value is clamped to [min, max] so a smaller window never inherits an unusable size.
 */
export function usePanelSize(key: string, initial: number, min: number, max: number): [number, (px: number) => void, () => void] {
  const raw = useSyncExternalStore(subscribe, () => read(key), () => null);
  const parsed = raw === null ? NaN : Number(raw);
  const size = clamp(Number.isFinite(parsed) ? parsed : initial, min, Math.max(min, max));
  const set = useCallback((px: number) => {
    try { localStorage.setItem(key, String(Math.round(px))); } catch { /* storage unavailable: size lasts until reload */ }
    listeners.forEach((l) => l());
  }, [key]);
  const reset = useCallback(() => {
    try { localStorage.removeItem(key); } catch { /* storage unavailable */ }
    listeners.forEach((l) => l());
  }, [key]);
  return [size, set, reset];
}

export type ResizeHandleProps = {
  /** Accessible name, e.g. "Resize Assistant panel". */
  label: string;
  /** "x" resizes a width (vertical divider); "y" resizes a height (horizontal divider). */
  axis: "x" | "y";
  value: number;
  min: number;
  max: number;
  onChange: (px: number) => void;
  /** Double-click restores the default size. */
  onReset?: () => void;
  /** -1 when dragging toward the start (left/up) should grow the panel, e.g. a right-hand rail. */
  direction?: 1 | -1;
  className?: string;
};

/**
 * Drag, arrow-key and double-click resizing for a panel edge. Arrow keys move 16px (Shift: 64px);
 * Home and End jump to the limits. Exposes the ARIA separator value for assistive technology.
 */
export function ResizeHandle({ label, axis, value, min, max, onChange, onReset, direction = 1, className }: ResizeHandleProps) {
  const drag = useRef<{ id: number; start: number; origin: number } | null>(null);
  const limit = (v: number) => clamp(v, min, Math.max(min, max));

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { id: e.pointerId, start: axis === "x" ? e.clientX : e.clientY, origin: value };
    document.documentElement.dataset.resizing = axis;
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    const delta = (axis === "x" ? e.clientX : e.clientY) - d.start;
    onChange(limit(d.origin + delta * direction));
  };
  const end = () => { drag.current = null; delete document.documentElement.dataset.resizing; };
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 64 : 16;
    const grow = axis === "x" ? (direction === 1 ? "ArrowRight" : "ArrowLeft") : (direction === 1 ? "ArrowDown" : "ArrowUp");
    const shrink = axis === "x" ? (direction === 1 ? "ArrowLeft" : "ArrowRight") : (direction === 1 ? "ArrowUp" : "ArrowDown");
    let next: number | null = null;
    if (e.key === grow) next = value + step;
    else if (e.key === shrink) next = value - step;
    else if (e.key === "Home") next = min;
    else if (e.key === "End") next = max;
    if (next === null) return;
    e.preventDefault();
    onChange(limit(next));
  };

  return (
    <div
      role="separator"
      aria-label={label}
      aria-orientation={axis === "x" ? "vertical" : "horizontal"}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={Math.max(min, max)}
      tabIndex={0}
      title={`${label} (double-click to reset)`}
      className={cx(styles.handle, axis === "x" ? styles.x : styles.y, className)}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={end}
      onPointerCancel={end}
      onLostPointerCapture={end}
      onDoubleClick={onReset}
      onKeyDown={onKeyDown}
    />
  );
}
