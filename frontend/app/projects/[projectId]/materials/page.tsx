import { Suspense } from 'react'
import { MaterialsScreen } from '@/features/materials'
import LoadingProjectView from '../loading'

type Props = { params: Promise<{ projectId: string }> }

export default function MaterialsPage({ params }: Props) {
  return <Suspense fallback={<LoadingProjectView />}><MaterialsPageContent params={params} /></Suspense>
}

async function MaterialsPageContent({ params }: Props) {
  const { projectId } = await params
  return <MaterialsScreen project_id={projectId} />
}
