import { Suspense } from 'react'
import { ReportScreen } from '@/features/reports'
import LoadingProjectView from '../../loading'

type Props = { params: Promise<{ projectId: string, artifactId: string }> }

export default function ReportPage({ params }: Props) {
  return <Suspense fallback={<LoadingProjectView />}><ReportPageContent params={params} /></Suspense>
}

async function ReportPageContent({ params }: Props) {
  const { projectId, artifactId } = await params
  return <ReportScreen project_id={projectId} artifact_id={artifactId} />
}
