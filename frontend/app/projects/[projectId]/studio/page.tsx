import { StudioSlot } from '@/providers/feature-bridge'
export default async function StudioPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <StudioSlot project_id={projectId} />
}
