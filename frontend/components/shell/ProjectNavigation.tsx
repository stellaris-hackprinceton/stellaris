"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ID } from "@/contracts/api";
import { hrefs } from "./hrefs";
import type { ProjectView } from "./hrefs";
import { ResearchIcon, MaterialsIcon, ExperimentIcon, GraphIcon, TrackerIcon } from "@/components/ui/icons";
import type { ComponentType } from "react";
import styles from "./shell.module.css";

// Decorative; the visible label names the destination.
const ReportsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    <path d="M6 3h9l4 4v14H6V3Z" /><path d="M14 3v5h5M9 12h7M9 16h7" />
  </svg>
);

export const VIEWS: { id: ProjectView; label: string; icon: ComponentType }[] = [
  { id: "research", label: "Research", icon: ResearchIcon },
  { id: "materials", label: "Materials", icon: MaterialsIcon },
  { id: "studio", label: "Experiments", icon: ExperimentIcon },
  { id: "reports", label: "Reports", icon: ReportsIcon },
  { id: "graph", label: "Knowledge graph", icon: GraphIcon },
  { id: "runs", label: "Tracker", icon: TrackerIcon },
];

/** The library and every `/reports/:artifact_id` reader keep Reports selected. */
export function currentView(pathname: string, project_id: ID): ProjectView | null {
  const base = hrefs.project(project_id);
  if (!pathname.startsWith(base)) return null;
  const seg = pathname.slice(base.length).split("/")[1];
  return VIEWS.some((v) => v.id === seg) ? (seg as ProjectView) : null;
}

export function ProjectNavigation({ project_id, onNavigate }: { project_id: ID; onNavigate?: () => void }) {
  const view = currentView(usePathname() ?? "", project_id);
  return (
    <nav aria-label="Project" className={styles.navigation}>
      <Link href={hrefs.projects()} className={styles.brand} onClick={onNavigate}>Stellaris<span>Research desk</span></Link>
      <ul className={styles.navList}>
        {VIEWS.map((v) => (
          <li key={v.id}>
            <Link
              href={hrefs.view(project_id, v.id)}
              aria-current={view === v.id ? "page" : undefined}
              className={styles.navLink}
              onClick={onNavigate}
            >
              <v.icon /><span>{v.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
