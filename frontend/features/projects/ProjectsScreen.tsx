"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useProjects } from "@/lib/queries";
import { Button, EmptyState, ErrorNotice, PlusIcon, Skeleton, StatusBadge, Tabs, TimestampLabel, describeError } from "@/components/ui";
import { hrefs } from "@/components/shell/hrefs";
import { CreateProjectDialog } from "./CreateProjectDialog";
import styles from "./projects.module.css";

type Filter = "active" | "archived";

export function ProjectsScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("active");
  const [creating, setCreating] = useState(false);

  return (
    <main className={styles.screen}>
      <header className={styles.header}>
        <div>
          <h1>Projects</h1>
          <p className={styles.muted}>Your research questions, experiments, evidence, and reports. Each project keeps its own history.</p>
        </div>
        <Button variant="primary" onClick={() => setCreating(true)}><PlusIcon /> New project</Button>
      </header>
      <Tabs
        label="Project status"
        value={filter}
        onChange={(v) => setFilter(v as Filter)}
        items={[
          { id: "active", label: "Active", content: <ProjectList status="active" onCreate={() => setCreating(true)} /> },
          { id: "archived", label: "Archived", content: <ProjectList status="archived" /> },
        ]}
      />
      <CreateProjectDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(p) => { setCreating(false); router.push(hrefs.view(p.id, "research")); }}
      />
    </main>
  );
}

function ProjectList({ status, onCreate }: { status: Filter; onCreate?: () => void }) {
  const projects = useProjects({ status });

  if (projects.error != null && projects.items.length === 0) {
    return <ErrorNotice {...describeError(projects.error, "Projects could not be loaded")} action={<Button onClick={projects.refetch}>Try again</Button>} />;
  }
  if (projects.is_loading) {
    return <div className={styles.list}><Skeleton height="5rem" /><Skeleton height="5rem" /><Skeleton height="5rem" /></div>;
  }
  if (projects.items.length === 0) {
    return status === "active" ? (
      <EmptyState title="No projects yet" action={onCreate && <Button variant="primary" onClick={onCreate}>Create your first project</Button>}>
        Start with a question. Stellaris helps you find literature, design an experiment, and measure the result.
      </EmptyState>
    ) : (
      <EmptyState title="No archived projects">Archived projects stay readable and can be restored from their header.</EmptyState>
    );
  }
  return (
    <div className={styles.stack}>
      <ul className={styles.list}>
        {projects.items.map((p) => (
          <li key={p.id}>
            <Link href={hrefs.view(p.id, "research")} className={styles.card}>
              <span className={styles.cardHead}>
                <span className={styles.cardTitle}>{p.name}</span>
                {p.status === "archived" && <StatusBadge tone="warning">Archived</StatusBadge>}
              </span>
              <span className={p.research_question ? styles.cardQuestion : styles.muted}>
                {p.research_question ?? "No research question yet"}
              </span>
              <span className={styles.muted}>Updated <TimestampLabel iso={p.updated_at} /></span>
            </Link>
          </li>
        ))}
      </ul>
      {projects.has_next_page && (
        <Button onClick={projects.load_next_page} pending={projects.is_fetching_next_page}>Load more projects</Button>
      )}
    </div>
  );
}
