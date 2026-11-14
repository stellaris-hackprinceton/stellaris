"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { ID } from "@/contracts/api";
import { Button, Sheet } from "@/components/ui";
import { useProject } from "@/lib/queries";
import { QuestionSection } from "../canvas/QuestionSection";
import { ActiveWork } from "./ActiveWork";
import { LiteratureWidget, type OpenSource } from "./LiteratureWidget";
import { ExperimentsWidget } from "./ExperimentsWidget";
import { FindingsWidget, ClaimInspector, type OpenClaim, type OpenCitation } from "./FindingsWidget";
import { MeasurementsWidget } from "./MeasurementsWidget";
import { WritingWidget } from "./WritingWidget";
import { SourceInspector, type CitationFocus } from "./SourceInspector";
import styles from "./desk.module.css";

type Inspector = { kind: "source"; id: ID; citation?: CitationFocus } | { kind: "claim"; id: ID };

/** Five evidence-backed widgets, with one shared inspector that preserves the desk context. */
export function ResearchDesk({ project_id }: { project_id: ID }) {
  const project = useProject(project_id);
  const search = useSearchParams();
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const [wide, setWide] = useState(false);
  const [localInspector, setLocalInspector] = useState<Inspector | null>(null);

  const linkedSource = search.get("source");
  const linkedClaim = search.get("claim");
  const inspector = linkedSource ? { kind: "source" as const, id: linkedSource }
    : linkedClaim ? { kind: "claim" as const, id: linkedClaim } : localInspector;

  useEffect(() => {
    const node = root.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWide(entry.contentRect.width >= 1100));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const openSource: OpenSource = useCallback((id, element) => {
    opener.current = element;
    setLocalInspector({ kind: "source", id });
  }, []);
  const openClaim: OpenClaim = useCallback((id, element) => {
    opener.current = element;
    setLocalInspector({ kind: "claim", id });
  }, []);
  const openCitation: OpenCitation = useCallback((id, element, citation) => {
    opener.current = element;
    setLocalInspector({ kind: "source", id, citation });
  }, []);
  const closeInspector = () => {
    setLocalInspector(null);
    if (linkedSource || linkedClaim) {
      const next = new URLSearchParams(search.toString());
      next.delete("source");
      next.delete("claim");
      router.replace(`/projects/${encodeURIComponent(project_id)}/research${next.size ? `?${next}` : ""}`, { scroll: false });
    }
    requestAnimationFrame(() => opener.current?.focus());
  };

  return (
    <div ref={root} className={styles.root}>
      <div className={styles.layout} data-inspector={inspector && wide ? "side" : undefined}>
        <div className={styles.screen}>
          <header className={styles.header}>
            <h1>Research</h1>
            {project.data?.description && <p>{project.data.description}</p>}
          </header>
          <section aria-label="Research question" className={styles.question}>
            <strong>Question</strong>
            <QuestionSection project_id={project_id} compact />
          </section>
          <ActiveWork project_id={project_id} />
          <div className={styles.grid}>
            <LiteratureWidget project_id={project_id} onOpenSource={openSource} selected={inspector?.kind === "source" ? inspector.id : null} />
            <ExperimentsWidget project_id={project_id} />
            <FindingsWidget project_id={project_id} onOpenClaim={openClaim} onOpenCitation={openCitation} selected={inspector?.kind === "claim" ? inspector.id : null} />
            <MeasurementsWidget project_id={project_id} />
            <WritingWidget project_id={project_id} />
          </div>
        </div>
        {inspector && wide && <aside className={styles.inspector} aria-label="Research inspector">
          <div className={styles.inspectorHead}>
            <h2>{inspector.kind === "source" ? "Literature source" : "Finding"}</h2>
            <Button onClick={closeInspector}>Close</Button>
          </div>
          {inspector.kind === "source"
            ? <SourceInspector project_id={project_id} source_id={inspector.id} citation={inspector.citation} />
            : <ClaimInspector project_id={project_id} claim_id={inspector.id} onOpenCitation={openCitation} />}
        </aside>}
      </div>
      {!wide && <Sheet open={!!inspector} onClose={closeInspector} title={inspector?.kind === "source" ? "Literature source" : "Finding"}>
        {inspector?.kind === "source" && <SourceInspector project_id={project_id} source_id={inspector.id} citation={inspector.citation} />}
        {inspector?.kind === "claim" && <ClaimInspector project_id={project_id} claim_id={inspector.id} onOpenCitation={openCitation} />}
      </Sheet>}
    </div>
  );
}
