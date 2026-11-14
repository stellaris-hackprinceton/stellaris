import { Suspense } from "react";
import { KnowledgeGraph } from "@/features/graph/KnowledgeGraph";
import LoadingProjectView from '../loading'

type Props = { params: Promise<{ projectId: string }> }

export default function GraphPage({ params }: Props) {
  return <Suspense fallback={<LoadingProjectView />}><GraphPageContent params={params} /></Suspense>
}

async function GraphPageContent({ params }: Props) {
  const { projectId } = await params;
  return <KnowledgeGraph project_id={projectId} />;
}
