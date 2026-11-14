import { ReportsScreen } from '@/features/reports'

type Search = { [key: string]: string | string[] | undefined }
const one = (value: string | string[] | undefined) => typeof value === 'string' && value ? value : undefined

export default async function ReportsPage({ params, searchParams }: { params: Promise<{ projectId: string }>, searchParams: Promise<Search> }) {
  const { projectId } = await params
  const search = await searchParams
  // A new contextual entry starts a new draft; context is never applied to an existing draft.
  const key = [one(search.compose), one(search.experiment), one(search.evidence_run)].join('|')
  return <ReportsScreen key={key} project_id={projectId} compose={one(search.compose) === '1'} experiment={one(search.experiment)} evidence_run={one(search.evidence_run)} />
}
