"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useProjects } from "@/lib/queries";
import { Button, ErrorNotice, PlusIcon, Skeleton, Tabs, TimestampLabel, describeError } from "@/components/ui";
import { ResearchIcon } from "@/components/ui/icons";
import { StellarisMark } from "@/components/ui/StellarisMark";
import { hrefs } from "@/components/shell/hrefs";
import { CreateProjectDialog } from "./CreateProjectDialog";
import styles from "./projects.module.css";

type Filter = "active" | "archived";

function Arrow({ className }: { className?: string }) {
  return <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d="M4 12h16m-6-6 6 6-6 6" /></svg>;
}

export function ProjectsScreen() {
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("active");
  const [creating, setCreating] = useState(false);

  return (
    <main className={styles.screen}>
      <div className={styles.masthead}>
        <div className={styles.brand}>
          <StellarisMark className={styles.brandMark} />
          Stellaris
        </div>
        <span className={styles.brandNote}>A workspace for discovery</span>
      </div>
      <header className={styles.header}>
        <div className={styles.intro}>
          <h1>Your research projects</h1>
          <p>From question to discovery.</p>
        </div>
        <Button className={styles.primaryAction} variant="primary" onClick={() => setCreating(true)}><PlusIcon /> New project</Button>
      </header>
      <ol className={styles.workflow} aria-label="Research workflow">
        {["Literature", "Experiment", "Measurement", "Report"].map((step, index) => <li key={step}>{index > 0 && <Arrow className={styles.workflowArrow} />}{step}</li>)}
      </ol>
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
        <span className={styles.emptyMark}><ResearchIcon /></span>
        <h2>Start with a question</h2>
        <p>Find literature, design an experiment, and turn your measurements into a report. Keep the evidence together in a project.</p>
        <div className={styles.example}><span className={styles.exampleLabel}>Example research question</span><p>How much energy does a tennis ball keep after each bounce?</p></div>
        {onCreate && <Button className={styles.primaryAction} variant="primary" onClick={onCreate}>Create your first project</Button>}
      </div>
    ) : (
      <div className={styles.statePanel}><h2>No archived projects</h2><p>Archived projects stay readable and can be restored from their header.</p></div>
    );
  }
  return (
    <div className={styles.stack}>
      <ul className={styles.list}>
        {projects.items.map((p) => (
          <li key={p.id}>
            <Link href={hrefs.view(p.id, "research")} className={styles.card}>
              <span className={styles.cardBody}>
              <span className={styles.cardHead}>
                <span className={styles.cardTitle}>{p.name}</span>
                {p.status === "archived" && <span className={styles.archivedLabel}>Archived</span>}
              </span>
              <span className={styles.cardQuestion}>
                {p.research_question?.trim() || p.description?.trim() || "No research question yet"}
              </span>
              <span className={styles.cardMeta}>Updated <TimestampLabel iso={p.updated_at} /></span>
              </span>
              <Arrow className={styles.cardArrow} />
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
