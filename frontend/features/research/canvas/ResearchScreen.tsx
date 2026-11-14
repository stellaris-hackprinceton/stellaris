"use client";

import type { ID } from "@/contracts/api";
import { ResearchDesk } from "../desk/ResearchDesk";

/** Public Research route entry point; the desk keeps the project context in view. */
export function ResearchScreen({ project_id }: { project_id: ID }) {
  return <ResearchDesk project_id={project_id} />;
}
