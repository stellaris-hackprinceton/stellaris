"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useProjects } from "@/lib/queries";
import { Button, ErrorNotice, PlusIcon, Skeleton, Tabs, TimestampLabel, describeError } from "@/components/ui";
import { StellarisMark } from "@/components/ui/StellarisMark";
import { hrefs } from "@/components/shell/hrefs";
import { CreateProjectDialog } from "./CreateProjectDialog";
import { ProjectPreview } from "./ProjectPreview";
import styles from "./projects.module.css";

type Filter = "active" | "archived";

export function ProjectsScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("active");
  const [creating, setCreating] = useState(false);

  return (
    <main className={styles.screen}>
      <div className={styles.masthead}>
        <div className={styles.brand}>
          <StellarisMark className={styles.brandMark} />
          <span>Stellaris</span>
        </div>
      </div>
      <header className={styles.header}>
        <div className={styles.intro}>
          <h1>Projects</h1>
        </div>
        <Button className={styles.primaryAction} variant="primary" onClick={() => setCreating(true)}><PlusIcon /> New project</Button>
      </header>
      <section className={styles.collection} aria-label="Your projects">
      <Tabs
        label="Project status"
        value={filter}
        onChange={(v) => setFilter(v as Filter)}
        items={[
          { id: "active", label: "Active", content: <ProjectList status="active" onCreate={() => setCreating(true)} /> },
          { id: "archived", label: "Archived", content: <ProjectList status="archived" /> },
        ]}
      />
      </section>
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
    return <div className={styles.statePanel}><ErrorNotice {...describeError(projects.error, "Projects could not be loaded")} action={<Button onClick={projects.refetch} pending={projects.isFetching}>Try again</Button>} /></div>;
  }
  if (projects.is_loading) {
    return <div className={styles.loading} role="status"><span className="sr-only">Loading projects…</span><Skeleton height="9rem" /><Skeleton height="9rem" /><Skeleton height="9rem" /></div>;
  }
  if (projects.items.length === 0) {
    return status === "active" ? (
      <div className={styles.statePanel}>
        <p>No projects yet.</p>
        {onCreate && <Button className={styles.primaryAction} variant="primary" onClick={onCreate}>Create project</Button>}
      </div>
    ) : (
      <div className={styles.statePanel}><h2>No archived projects</h2><p>Archived projects stay readable and can be restored from their header.</p></div>
    );
  }
  return (
    <div className={styles.stack}>
      <ul className={styles.grid}>
        {projects.items.map((p) => (
          <li key={p.id}>
            <Link href={hrefs.view(p.id, "research")} className={styles.card}>
              <ProjectPreview project={p} />
              <span className={styles.cardBody}>
                <span className={styles.cardHead}>
                  <span className={styles.cardTitle}>{p.name}</span>
                  {p.status === "archived" && <span className={styles.archivedLabel}>Archived</span>}
                </span>
                {p.research_question?.trim() && <span className={styles.cardQuestion}>{p.research_question.trim()}</span>}
                <span className={styles.cardMeta}>Updated <TimestampLabel iso={p.updated_at} /></span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {projects.error != null && <ErrorNotice {...describeError(projects.error, projects.isFetchNextPageError ? "More projects could not be loaded" : "Projects could not be refreshed")} action={<Button pending={projects.isFetching} onClick={() => projects.isFetchNextPageError ? projects.load_next_page() : projects.refetch()}>Try again</Button>} />}
      {projects.has_next_page && (
        <Button onClick={projects.load_next_page} pending={projects.is_fetching_next_page}>Load more projects</Button>
      )}
    </div>
  );
}
