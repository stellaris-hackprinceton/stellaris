import { Suspense } from 'react'
import { ReportsScreen } from '@/features/reports'
import LoadingProjectView from '../loading'

type Search = { [key: string]: string | string[] | undefined }
const one = (value: string | string[] | undefined) => typeof value === 'string' && value ? value : undefined
type Props = { params: Promise<{ projectId: string }>, searchParams: Promise<Search> }

export default function ReportsPage({ params, searchParams }: Props) {
  return <Suspense fallback={<LoadingProjectView />}><ReportsPageContent params={params} searchParams={searchParams} /></Suspense>
}

async function ReportsPageContent({ params, searchParams }: Props) {
  const { projectId } = await params
  const search = await searchParams
  // A new contextual entry starts a new draft; context is never applied to an existing draft.
  const key = [one(search.compose), one(search.experiment), one(search.evidence_run)].join('|')
  return <ReportsScreen key={key} project_id={projectId} compose={one(search.compose) === '1'} experiment={one(search.experiment)} evidence_run={one(search.evidence_run)} />
}
