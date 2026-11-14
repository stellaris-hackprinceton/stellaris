import { ReportScreen } from '@/features/reports'
export default async function ReportPage({ params }: { params: Promise<{ projectId: string, artifactId: string }> }) {
  const { projectId, artifactId } = await params
  return <ReportScreen project_id={projectId} artifact_id={artifactId} />
}
