// Typed client for docs/terminal-contract.md plus SSE integration over the existing project stream.
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import type { Page } from '@/contracts/api'
import {
  ACTIVE_TERMINAL_STATUSES, TERMINAL_LIMITS,
  type TerminalOutputChunk, type TerminalSession, type TerminalSize, type TerminalStatus,
} from '@/contracts/terminal'
import { apiUrl, encode, request } from '@/lib/api/http'

const base = (p: string) => `/projects/${encode(p)}/terminals`
const one = (p: string, id: string) => `${base(p)}/${encode(id)}`

export const terminalApi = {
  list: (p: string, cursor: string | null, signal?: AbortSignal) =>
    request<Page<TerminalSession>>(`${base(p)}?limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, { signal }),
  get: (p: string, id: string, signal?: AbortSignal) => request<TerminalSession>(one(p, id), { signal }),
  start: (p: string, size: TerminalSize, idempotency_key: string) =>
    request<TerminalSession>(base(p), { method: 'POST', body: clampSize(size), command: { idempotency_key } }),
  input: (p: string, id: string, sequence: number, data_base64: string) =>
    request<TerminalSession>(`${one(p, id)}/input/${sequence}`, { method: 'PUT', body: { data_base64 } }),
  resize: (p: string, id: string, size: TerminalSize) =>
    request<TerminalSession>(`${one(p, id)}/size`, { method: 'PUT', body: clampSize(size) }),
  close: (p: string, id: string, idempotency_key: string) =>
    request<TerminalSession>(`${one(p, id)}/close`, { method: 'POST', body: {}, command: { idempotency_key } }),
  /** First page uses after_sequence; later pages pass only the opaque cursor (it carries the filter). */
  output: (p: string, id: string, after_sequence: number, cursor: string | null, signal?: AbortSignal) =>
    request<Page<TerminalOutputChunk>>(`${one(p, id)}/output?limit=100&${cursor ? `cursor=${encodeURIComponent(cursor)}` : `after_sequence=${after_sequence}`}`, { signal }),
  transcriptUrl: (p: string, id: string) => apiUrl(`${one(p, id)}/transcript`),
}

export const isActiveTerminal = (session: { status: TerminalStatus } | null | undefined) =>
  !!session && ACTIVE_TERMINAL_STATUSES.includes(session.status)

export function clampSize({ rows, cols }: TerminalSize): TerminalSize {
  const clamp = (value: number, min: number, max: number, fallback: number) =>
    Number.isFinite(value) ? Math.min(max, Math.max(min, Math.floor(value))) : fallback
  return {
    rows: clamp(rows, TERMINAL_LIMITS.min_rows, TERMINAL_LIMITS.max_rows, 24),
    cols: clamp(cols, TERMINAL_LIMITS.min_cols, TERMINAL_LIMITS.max_cols, 80),
  }
}

export function decodeBase64(value: string): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}
export function encodeBase64(bytes: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(binary)
}

/** The session shown in the panel: the project's single active session, else the most recent one. */
export const terminalKey = (p: string) => ['project', p, 'terminals', 'current'] as const

async function loadCurrent(p: string, signal: AbortSignal): Promise<TerminalSession | null> {
  let cursor: string | null = null, latest: TerminalSession | null = null
  // Listings are ordered oldest first; walk every page so an active session is never missed.
  for (let page = 0; page < 400; page++) {
    const result: { data: Page<TerminalSession> } = await terminalApi.list(p, cursor, signal)
    for (const item of result.data.items) {
      if (isActiveTerminal(item)) return item
      if (!latest || item.created_at >= latest.created_at) latest = item
    }
    cursor = result.data.next_cursor
    if (!cursor) break
  }
  if (cursor) throw new Error('Session history is too large to determine the current session safely. No new session was started.')
  return latest
}

export function useCurrentTerminal(project_id: string, enabled: boolean) {
  const client = useQueryClient()
  return useQuery({
    queryKey: terminalKey(project_id),
    queryFn: async ({ signal }) => {
      const loaded = await loadCurrent(project_id, signal)
      const current = client.getQueryData<TerminalSession | null>(terminalKey(project_id))
      return loaded ? preferSession(current ?? null, loaded) : current ?? null
    },
    enabled, retry: false, staleTime: 30000,
  })
}

function preferSession(old: TerminalSession | null, next: TerminalSession): TerminalSession | null {
  if (!old) return next
  if (old.id === next.id) {
    // A POST/read response can arrive after a newer SSE update. Session states
    // advance monotonically; never replace running/closed with a stale starting row.
    const stage: Record<TerminalStatus, number> = { starting: 0, running: 1, closing: 2, closed: 3, failed: 3 }
    if (stage[old.status] > stage[next.status]) return old
    return { ...next, last_output_sequence: Math.max(old.last_output_sequence, next.last_output_sequence),
      last_input_sequence: Math.max(old.last_input_sequence, next.last_input_sequence), output_bytes: Math.max(old.output_bytes, next.output_bytes) }
  }
  if (isActiveTerminal(old) && !isActiveTerminal(next)) return old
  if (isActiveTerminal(next) && !isActiveTerminal(old)) return next
  return next.created_at >= old.created_at ? next : old
}
export function setCurrentTerminal(client: QueryClient, session: TerminalSession) {
  client.setQueryData<TerminalSession | null>(terminalKey(session.project_id), old => preferSession(old ?? null, session))
}

// Output is delivered to the mounted view; nothing is cached here, so memory stays bounded.
export type TerminalSignal =
  | { type: 'output', terminal_id: string, sequence: number, data_base64: string }
  | { type: 'updated', terminal: TerminalSession }
  | { type: 'resync' }
type Listener = (signal: TerminalSignal) => void
const listeners = new Map<string, Set<Listener>>()
export function subscribeTerminal(project_id: string, listener: Listener) {
  const set = listeners.get(project_id) ?? new Set<Listener>()
  set.add(listener); listeners.set(project_id, set)
  return () => { set.delete(listener); if (!set.size) listeners.delete(project_id) }
}
function emit(project_id: string, signal: TerminalSignal) {
  for (const listener of listeners.get(project_id) ?? []) listener(signal)
}

const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object'
function isSession(value: unknown, project_id: string): value is TerminalSession {
  return record(value) && typeof value.id === 'string' && value.project_id === project_id && typeof value.status === 'string'
    && typeof value.created_at === 'string' && Number.isInteger(value.last_output_sequence) && Number.isInteger(value.last_input_sequence)
}

/** Applies terminal.* events from the shared project SSE stream. Other events are ignored. */
export function applyTerminalEvent(client: QueryClient, event: unknown) {
  if (!record(event) || typeof event.type !== 'string' || typeof event.project_id !== 'string' || !record(event.payload)) return
  const p = event.project_id, payload = event.payload
  if (event.type === 'terminal.updated' && isSession(payload.terminal, p)) {
    setCurrentTerminal(client, payload.terminal)
    emit(p, { type: 'updated', terminal: payload.terminal })
  } else if (event.type === 'terminal.output' && typeof payload.terminal_id === 'string'
    && Number.isInteger(payload.sequence) && typeof payload.data_base64 === 'string') {
    emit(p, { type: 'output', terminal_id: payload.terminal_id, sequence: payload.sequence as number, data_base64: payload.data_base64 })
  }
}

/** After the shared stream (re)connects, refresh sessions and let the view fetch any missed output. */
export function refreshTerminals(client: QueryClient, project_id: string) {
  void client.invalidateQueries({ queryKey: terminalKey(project_id) })
  emit(project_id, { type: 'resync' })
}
