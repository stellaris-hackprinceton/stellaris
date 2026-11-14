"use client";
import { useRef, useState } from "react";
import type { MouseEvent } from "react";
import styles from "../studio.module.css";

type Pt = [number, number];
type Props = {
  src: string;
  /** Native decoded dimensions reported by the backend (after orientation). */
  width_px: number;
  height_px: number;
  a: Pt | null;
  b: Pt | null;
  onPick: (which: "a" | "b", p: Pt) => void;
  disabled?: boolean;
};

/**
 * Click-to-place reference points on a still image. The image is shown at its native aspect ratio
 * (no crop, no mirror, no letterbox), so the mapping is a single scale factor:
 *   native = (client - rect.origin) * (native_size / rendered_size)
 * Points are rounded to 0.1 px. Numeric inputs remain the authoritative way to adjust them.
 */
export function ImagePointPicker({ src, width_px, height_px, a, b, onPick, disabled }: Props) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [next, setNext] = useState<"a" | "b">(a ? (b ? "a" : "b") : "a");
  const [mismatch, setMismatch] = useState(false);

  function toNative(e: MouseEvent<HTMLElement>): Pt | null {
    const el = imgRef.current;
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const x = ((e.clientX - r.left) * width_px) / r.width;
    const y = ((e.clientY - r.top) * height_px) / r.height;
    if (x < 0 || y < 0 || x > width_px || y > height_px) return null;
    return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
  }

  function onClick(e: MouseEvent<HTMLElement>) {
    if (disabled || mismatch) return;
    const p = toNative(e);
    if (!p) return;
    onPick(next, p);
    setNext(next === "a" ? "b" : "a");
  }

  const r = Math.max(width_px, height_px) / 120;
  return (
    <div className={styles.picker}>
      <p className={styles.muted} aria-live="polite">
        {mismatch
          ? "The displayed image size does not match the server's reported dimensions, so clicking is disabled. Enter the points numerically."
          : `Click the image to place point ${next.toUpperCase()}.`}
      </p>
      {/* Pointer placement is a convenience; the numeric fields below are the accessible path. */}
      <div className={styles.pickerFrame} onClick={onClick} style={{ aspectRatio: `${width_px} / ${height_px}` }}>
        {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API content, not a static asset */}
        <img
          ref={imgRef}
          src={src}
          alt="Calibration image"
          className={styles.pickerImg}
          draggable={false}
          onLoad={(e) => {
            const im = e.currentTarget;
            setMismatch(im.naturalWidth !== width_px || im.naturalHeight !== height_px);
          }}
        />
        <svg className={styles.pickerOverlay} viewBox={`0 0 ${width_px} ${height_px}`} aria-hidden="true">
          {a && b && <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} className={styles.pickerLine} strokeWidth={r / 3} />}
          {a && <circle cx={a[0]} cy={a[1]} r={r} className={styles.pickerPoint} strokeWidth={r / 3} />}
          {b && <circle cx={b[0]} cy={b[1]} r={r} className={styles.pickerPoint} strokeWidth={r / 3} />}
          {a && <text x={a[0] + r * 1.5} y={a[1] - r} className={styles.pickerText} fontSize={r * 2.5}>A</text>}
          {b && <text x={b[0] + r * 1.5} y={b[1] - r} className={styles.pickerText} fontSize={r * 2.5}>B</text>}
        </svg>
      </div>
    </div>
  );
}
