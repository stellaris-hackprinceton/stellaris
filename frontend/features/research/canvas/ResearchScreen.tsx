"use client";
import type { ID } from "@/contracts/api";
import { Tabs } from "@/components/ui";
import { ExperimentsSection } from "./ExperimentsSection";
import { FindingsSection } from "./FindingsSection";
import { QuestionSection } from "./QuestionSection";
import { SourcesSection } from "./SourcesSection";
import { useCanvasParams } from "./useCanvasParams";
import type { CanvasTab } from "./useCanvasParams";
import styles from "./canvas.module.css";

/**
 * Structured research view (not a freeform canvas). Tab, selected source and selected claim are in
 * the URL. Uses useSearchParams, so the route must render it inside <Suspense> (Agent C).
 */
export function ResearchScreen({ project_id }: { project_id: ID }) {
  const { tab, source, claim, update } = useCanvasParams();

  return (
    <div className={styles.screen}>
      <h2 className="sr-only">Research</h2>
      <Tabs
        label="Research sections"
        value={tab}
        onChange={(t) => update({ tab: t as CanvasTab })}
        items={[
          { id: "question", label: "Research question", content: <QuestionSection project_id={project_id} /> },
          {
            id: "sources", label: "Sources",
            content: <SourcesSection project_id={project_id} selected={source} onSelect={(id) => update({ tab: "sources", source: id })} />,
          },
          {
            id: "findings", label: "Findings",
            content: <FindingsSection project_id={project_id} selected={claim} onSelectSource={(id) => update({ tab: "sources", source: id })} />,
          },
          { id: "experiments", label: "Experiment plans", content: <ExperimentsSection project_id={project_id} /> },
        ]}
      />
    </div>
  );
}
