"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ID } from "@/contracts/api";
import { hrefs } from "./hrefs";
import type { ProjectView } from "./hrefs";
import styles from "./shell.module.css";

export const VIEWS: { id: ProjectView; label: string }[] = [
  { id: "research", label: "Research" },
  { id: "studio", label: "Studio" },
  { id: "runs", label: "Runs" },
  { id: "workspace", label: "Workspace" },
];

export function currentView(pathname: string, project_id: ID): ProjectView | "report" | null {
  const base = hrefs.project(project_id);
  if (!pathname.startsWith(base)) return null;
  const seg = pathname.slice(base.length).split("/")[1];
  if (seg === "reports") return "report";
  return VIEWS.some((v) => v.id === seg) ? (seg as ProjectView) : null;
}

export function ProjectNavigation({ project_id, onNavigate }: { project_id: ID; onNavigate?: () => void }) {
  const view = currentView(usePathname() ?? "", project_id);
  return (
    <nav aria-label="Project">
      <ul className={styles.navList}>
        {VIEWS.map((v) => (
          <li key={v.id}>
            <Link
              href={hrefs.view(project_id, v.id)}
              aria-current={view === v.id ? "page" : undefined}
              className={styles.navLink}
              onClick={onNavigate}
            >
              {v.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
