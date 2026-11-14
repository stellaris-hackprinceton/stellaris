'use client'
import Link from 'next/link'

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError, api, isAuthError } from '@/lib/api'
import { keys, useProject, useWorkspace } from '@/lib/queries'
import { applyProjectEvent, cachedActiveRuns } from '@/lib/events/cache'
import { consumeEvents } from '@/lib/events/stream'
import { ProjectShellSlot } from './feature-bridge'
import { ProjectApprovals } from '@/features/execution/approvals'
import styles from '@/features/execution/sol.module.css'

export type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'offline'
type ProjectContextValue = { project_id: string, connection: ConnectionState, reconnect: () => void }
const ProjectContext = createContext<ProjectContextValue | null>(null)
export function useProjectRuntime() { const value = useContext(ProjectContext); if (!value) throw new Error('A project runtime is required.'); return value }
function delay(ms: number, signal: AbortSignal) {
  return new Promise<void>(resolve => { const timer = setTimeout(done, ms); function done() { clearTimeout(timer); signal.removeEventListener('abort', done); resolve() } signal.addEventListener('abort', done, { once: true }); if (signal.aborted) done() })
}
export function ProjectRuntime({ project_id, children }: { project_id: string, children: ReactNode }) {
  const client = useQueryClient(), project = useProject(project_id), workspace = useWorkspace(project_id)
  const [connection, setConnection] = useState<ConnectionState>('connecting'), [generation, setGeneration] = useState(0)
  const reconnect = useCallback(() => setGeneration(value => value + 1), [])
  const ready = !!project.data && !!workspace.data
  useEffect(() => {
    if (!ready) return
    const controller = new AbortController(), signal = controller.signal
    let connected = false, disconnectedAt = 0, cursor = '', stopped = false, openedAt = 0
    const seen = new Set<string>()
    let fallbackTimer: ReturnType<typeof setTimeout> | undefined
    async function fallback() {
      if (stopped || signal.aborted || connected || !disconnectedAt || Date.now() - disconnectedAt >= 300000) return
      const ids = cachedActiveRuns(client, project_id)
      await Promise.allSettled(ids.map(async id => {
        const run = await api.runs.get(project_id, id, signal)
        // Use the same revision-aware application path as stream events.
        await applyProjectEvent(client, { cursor: 'rest-refresh', project_id, type: 'run.updated', occurred_at: new Date().toISOString(), run_id: id, payload: { run: run.data } }, signal)
        const results = await api.runs.results(project_id, id, signal)
        client.setQueryData(keys.detail(project_id, 'results', id), results)
      }))
      if (ids.length && !signal.aborted && !connected) fallbackTimer = setTimeout(() => void fallback(), 10000)
    }
    async function snapshot() {
      const snapshot = await api.projects.workspace(project_id, signal)
      client.setQueryData(keys.detail(project_id, 'workspace', project_id), snapshot)
      // Refetch active route resources before replaying events after this snapshot.
      await client.refetchQueries({ queryKey: keys.project(project_id), type: 'active' })
      cursor = snapshot.data.event_cursor
      seen.clear()
    }
    async function run() {
      setConnection('connecting')
      let attempts = 0
      while (!signal.aborted) {
        try {
          if (!cursor) await snapshot()
          await consumeEvents(project_id, cursor, signal, async event => {
            if (seen.has(event.cursor)) return
            await applyProjectEvent(client, event, signal)
            cursor = event.cursor; seen.add(cursor)
            if (seen.size > 2048) seen.delete(seen.values().next().value!)
          }, () => { connected = true; openedAt = Date.now(); disconnectedAt = 0; if (fallbackTimer) clearTimeout(fallbackTimer); setConnection('connected') })
        } catch (error) {
          if (signal.aborted) return
          connected = false
          if (openedAt && Date.now() - openedAt > 30000) attempts = 0
          if (isAuthError(error)) return
          if (error instanceof ApiError && error.status === 410) {
            cursor = ''; attempts++
            setConnection(attempts > 6 ? 'offline' : 'reconnecting')
            if (attempts > 6) return
            await delay(Math.min(1000 * 2 ** (attempts - 1), 30000), signal)
            continue
          }
          if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 429) { setConnection('offline'); return }
          if (!disconnectedAt) { disconnectedAt = Date.now(); fallbackTimer = setTimeout(() => void fallback(), 10000) }
          attempts++
          setConnection(attempts > 6 ? 'offline' : 'reconnecting')
          if (attempts > 6) return
          await delay(Math.min(1000 * 2 ** (attempts - 1), 30000), signal)
        }
      }
    }
    void run()
    return () => { stopped = true; controller.abort(); if (fallbackTimer) clearTimeout(fallbackTimer); void client.cancelQueries({ queryKey: keys.project(project_id) }) }
  }, [client, project_id, ready, generation])
  if (project.error || workspace.error) return <main className={styles.screen}><h1>Project unavailable</h1><p role="alert">{(project.error ?? workspace.error)?.message}</p><button onClick={() => { void project.refetch(); void workspace.refetch() }}>Reload project</button><Link href="/projects">Back to projects</Link></main>
  if (!ready) return <main className={styles.screen} aria-busy="true">Loading project…</main>
  return <ProjectContext.Provider value={{ project_id, connection, reconnect }}><ProjectShellSlot project_id={project_id}><div className={styles.connection} role="status">{connection === 'connected' ? 'Live updates connected' : connection === 'connecting' ? 'Connecting live updates…' : 'Live updates interrupted. Execution status is preserved.'}{connection !== 'connected' && <button onClick={reconnect}>Reconnect and refresh</button>}</div>{project.data?.status === 'archived' && <p className={styles.notice}>This project is archived. New work is disabled.</p>}<ProjectApprovals project_id={project_id} />{children}</ProjectShellSlot></ProjectContext.Provider>
}
