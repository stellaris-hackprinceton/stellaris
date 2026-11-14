"use client";
import { useSyncExternalStore } from "react";
import { THEME_STORAGE_KEY } from "./themeScript";

/** "system" follows the OS; "light"/"dark" are explicit choices saved in this browser. */
export type ThemePreference = "system" | "light" | "dark";

const listeners = new Set<() => void>();

function read(): ThemePreference {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

export function setThemePreference(next: ThemePreference) {
  const root = document.documentElement;
  if (next === "system") delete root.dataset.theme; else root.dataset.theme = next;
  try {
    if (next === "system") localStorage.removeItem(THEME_STORAGE_KEY); else localStorage.setItem(THEME_STORAGE_KEY, next);
  } catch { /* Storage blocked: the choice still applies to this page. */ }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => {
    if (e.key !== THEME_STORAGE_KEY) return;
    const value = read();
    if (value === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = value;
    listener();
  };
  window.addEventListener("storage", onStorage);
  return () => { listeners.delete(listener); window.removeEventListener("storage", onStorage); };
}

export function useThemePreference(): ThemePreference {
  return useSyncExternalStore(subscribe, read, () => "system");
}
