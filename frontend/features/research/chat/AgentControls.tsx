'use client'
import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { AgentSettings, OrganizationRequest } from '@/contracts/api'
import { agentControlsApi, applyChatClear, requestsKey, settingsKey, useAgentSettings, useOrganizationRequests } from '@/lib/agent-controls'
import { useCapabilities } from '@/lib/queries'
import { Button, Dialog, ErrorNotice, describeError, newCommandKey } from '@/components/ui'
import styles from './chat.module.css'

const MODES: AgentSettings['organization_permission'][] = ['off', 'ask', 'allow']
const LABEL = { off: 'Off', ask: 'Ask', allow: 'Allow' }
function describeOperation(operation: OrganizationRequest['operation']) {
  const tags = Array.isArray(operation.tags) ? operation.tags.join(', ') : ''
  switch (operation.operation) {
    case 'assign_tags': return `Add tags: ${tags}`
    case 'remove_tags': return `Remove tags: ${tags}`
    case 'create_collection': return `Create collection: ${operation.name}`
    case 'add_collection_members': return 'Add selected materials to a collection'
    case 'remove_collection_members': return 'Remove selected materials from a collection'
    default: return 'Organize project materials'
  }
}
export function AgentControls({ project_id, archived, busy }: { project_id: string, archived: boolean, busy: boolean }) {
  const client = useQueryClient(), caps = useCapabilities(), settings = useAgentSettings(project_id), pending = useOrganizationRequests(project_id)
  const [changing, setChanging] = useState(false), [confirming, setConfirming] = useState(false), [clearing, setClearing] = useState(false)
  const [error, setError] = useState<unknown>(null), [deciding, setDeciding] = useState<string | null>(null)
  const clearKey = useRef<string | null>(null), decisionKeys = useRef(new Map<string, string>())
  if (caps.data?.features.agent_controls !== true) return null
  const mode = settings.data?.data.organization_permission
  async function cycle() {
    if (!mode || !settings.data?.etag) return
    setChanging(true); setError(null)
    try {
      const next = MODES[(MODES.indexOf(mode) + 1) % MODES.length]
      client.setQueryData(settingsKey(project_id), await agentControlsApi.permission(project_id, next, settings.data.etag))
    } catch (e) { setError(e); void settings.refetch() } finally { setChanging(false) }
  }
  async function clear() {
    clearKey.current ??= newCommandKey()
    setClearing(true); setError(null)
    try {
      const result = await agentControlsApi.clear(project_id, clearKey.current)
      await applyChatClear(client, result.data); clearKey.current = null; setConfirming(false)
    } catch (e) { setError(e) } finally { setClearing(false) }
  }
  async function decide(id: string, decision: 'approve' | 'reject') {
    const identity = `${id}:${decision}`
    if (!decisionKeys.current.has(identity)) decisionKeys.current.set(identity, newCommandKey())
    setDeciding(id); setError(null)
    try {
      const result = await agentControlsApi.decide(project_id, id, decision, decisionKeys.current.get(identity)!)
      decisionKeys.current.delete(identity)
      await client.invalidateQueries({ queryKey: requestsKey(project_id) })
      if (result.data.status === 'failed') throw new Error(result.data.error?.message ?? 'The organization change could not be applied.')
    } catch (e) { setError(e) } finally { setDeciding(null) }
  }
  return <div className={styles.agentControls}>
    <div className={styles.controlRow}>
      <Button disabled={archived || changing || !settings.data} onClick={() => void cycle()} title={`${mode === 'ask' ? 'Review organization changes before they are applied.' : mode === 'allow' ? 'The agent may organize this project’s tags and collections. Originals are preserved.' : 'Agent organization is disabled.'} Click to cycle Off → Ask → Allow.`}>
        Organization: {mode ? LABEL[mode] : 'Loading…'}
      </Button>
      <Button disabled={archived || busy} onClick={() => { setError(null); setConfirming(true) }} title={busy ? 'Wait for the current response to finish.' : 'Start a fresh conversation; keep all project evidence.'}>Clear chat</Button>
    </div>
    {(error || settings.error || pending.error) != null && <ErrorNotice {...describeError(error ?? settings.error ?? pending.error)} action={<Button onClick={() => { void settings.refetch(); void pending.refetch() }}>Reload controls</Button>} />}
    {!!pending.data?.data.items.length && <details className={styles.pendingRequests}><summary>Organization requests ({pending.data.data.items.length})</summary>
      {pending.data.data.items.map(item => <section key={item.id}>
        <p>{describeOperation(item.operation)}</p>
        <details><summary>View affected materials</summary><pre>{JSON.stringify(item.operation, null, 2)}</pre></details>
        <div className={styles.controlRow}>
          <Button disabled={archived || mode === 'off' || deciding !== null} onClick={() => void decide(item.id, 'approve')}>{deciding === item.id ? 'Applying…' : 'Approve'}</Button>
          <Button disabled={archived || deciding !== null} onClick={() => void decide(item.id, 'reject')}>Reject</Button>
        </div>
      </section>)}
      {pending.data.data.next_cursor && <p>More requests are pending; process these to load the next page.</p>}
    </details>}
    <Dialog open={confirming} onClose={() => { if (!clearing) setConfirming(false) }} title="Clear this chat?">
      <p>This archives the conversation and starts fresh agent context. Files, experiments, results and reports stay in the project.</p>
      {error != null && <ErrorNotice {...describeError(error, 'Chat could not be cleared')} />}
      <div className={styles.controlRow}><Button variant="danger" pending={clearing} disabled={busy} onClick={() => void clear()}>Clear conversation</Button><Button disabled={clearing} onClick={() => setConfirming(false)}>Keep chat</Button></div>
    </Dialog>
  </div>
}
