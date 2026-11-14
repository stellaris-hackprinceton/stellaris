import { MaterialsScreen } from '@/features/materials'

export default async function MaterialsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <MaterialsScreen project_id={projectId} />
}
