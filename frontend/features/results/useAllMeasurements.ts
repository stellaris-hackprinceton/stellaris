"use client";
import { useEffect } from "react";
import type { ID } from "@/contracts/api";
import { useMeasurements } from "@/lib/queries";

/** Rows loaded automatically before asking the user to continue. Keeps the DOM bounded. */
export const AUTO_LOAD_ROWS = 2000;

/** Loads the run's measurement pages (no per-measurement route exists, so this is also how IDs resolve). */
export function useAllMeasurements(project_id: ID, run_id: ID) {
  const q = useMeasurements(project_id, run_id, {});
  const { has_next_page, is_fetching_next_page, load_next_page, items } = q;
  const auto = items.length < AUTO_LOAD_ROWS;
  useEffect(() => {
    if (auto && has_next_page && !is_fetching_next_page) load_next_page();
  }, [auto, has_next_page, is_fetching_next_page, load_next_page]);
  return q;
}
