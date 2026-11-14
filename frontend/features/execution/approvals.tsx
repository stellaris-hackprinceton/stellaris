'use client'

import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { Approval } from '@/contracts/api'
import { ApiError, commandKey } from '@/lib/api'
import { keys, useApprovals, useDecideApproval, useWorkspace } from '@/lib/queries'
import { ErrorNotice, PageMore } from './feedback'
import styles from './sol.module.css'

function ApprovalCard({ approval, project_id }: { approval: Approval, project_id: string }) {
  const mutation = useDecideApproval(), client = useQueryClient()
  const [decision, setDecision] = useState<'approve' | 'reject' | null>(null)
  const command = useRef<string | null>(null)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => { const timer = setTimeout(() => setNow(Date.now()), Math.max(0, Date.parse(approval.expires_at) - Date.now())); return () => clearTimeout(timer) }, [approval.expires_at])
  const expired = now >= Date.parse(approval.expires_at)
  async function decide(next: 'approve' | 'reject') {
    if (Date.now() >= Date.parse(approval.expires_at)) { setNow(Date.now()); return }
    if (decision && decision !== next && mutation.error) return
    setDecision(next)
    command.current ??= commandKey()
    try { await mutation.mutateAsync({ project_id, approval_id: approval.id, body: { decision: next, action_sha256: approval.action_sha256 }, command: { idempotency_key: command.current } }) }
    catch (error) { if (error instanceof ApiError && [409, 410].includes(error.status)) { command.current = null; setDecision(null); void client.invalidateQueries({ queryKey: ['project', project_id, `approvals:${approval.run_id}`] }); void client.invalidateQueries({ queryKey: keys.detail(project_id, 'runs', approval.run_id) }) } }
  }
  return <section className={`${styles.screen} ${styles.approval}`} aria-label="Execution approval"><h2>Approval required</h2><p>{approval.summary}</p><p>Action: {approval.action_type}</p><pre>{JSON.stringify(approval.action_snapshot, null, 2)}</pre><p>Action hash: <code>{approval.action_sha256}</code></p><p>Estimated cost: {approval.estimated_cost ? `${approval.estimated_cost.amount} ${approval.estimated_cost.currency}` : 'Unknown. Review the action before approving.'}</p><p>Expires: <time dateTime={approval.expires_at}>{new Date(approval.expires_at).toLocaleString()}</time></p><ErrorNotice error={mutation.error} /><div className={styles.actions}><button disabled={expired || mutation.isPending || (!!decision && decision !== 'approve')} onClick={() => void decide('approve')}>{mutation.isPending && decision === 'approve' ? 'Submitting approval…' : decision === 'approve' && mutation.error ? 'Retry same approval' : 'Approve this action'}</button><button disabled={expired || mutation.isPending || (!!decision && decision !== 'reject')} onClick={() => void decide('reject')}>Reject this action</button></div>{expired && <p>This approval has expired. Refresh execution state.</p>}</section>
}
function RunApprovals({ project_id, run_id }: { project_id: string, run_id: string }) {
  const approvals = useApprovals(project_id, run_id)
  return <><ErrorNotice error={approvals.error} />{approvals.items.filter(a => a.status === 'pending').map(a => <ApprovalCard key={`${a.id}:${a.action_sha256}`} approval={a} project_id={project_id} />)}<PageMore has_more={approvals.has_next_page} loading={approvals.isFetchingNextPage} load={approvals.load_next_page} /></>
}
export function ProjectApprovals({ project_id }: { project_id: string }) {
  const workspace = useWorkspace(project_id)
  return <>{workspace.data?.active_run_ids.map(run => <RunApprovals key={run} project_id={project_id} run_id={run} />)}</>
}
