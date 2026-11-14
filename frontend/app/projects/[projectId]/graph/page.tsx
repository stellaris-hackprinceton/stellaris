import { Suspense } from "react";
import { KnowledgeGraph } from "@/features/graph/KnowledgeGraph";

export default async function GraphPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <Suspense fallback={<p>Opening project graph…</p>}><KnowledgeGraph project_id={projectId} /></Suspense>;
}
