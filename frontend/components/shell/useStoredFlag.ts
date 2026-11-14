"use client";
import { useCallback, useSyncExternalStore } from "react";

const listeners = new Set<() => void>();

function read(key: string): string | null {
  try { return window.localStorage.getItem(key); } catch { return null; }
}

/** A UI preference persisted in localStorage (spec §5 allows this). Storage failures are ignored. */
export function useStoredFlag(key: string, initial: boolean): [boolean, (v: boolean) => void] {
  const raw = useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => { listeners.delete(cb); }; },
    () => read(key),
    () => null,
  );
  const value = raw === "1" ? true : raw === "0" ? false : initial;
  const set = useCallback((v: boolean) => {
    try { window.localStorage.setItem(key, v ? "1" : "0"); } catch { /* storage unavailable */ }
    listeners.forEach((l) => l());
  }, [key]);
  return [value, set];
}
