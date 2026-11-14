import type { QueryClient } from '@tanstack/react-query'
import type { LogEntry, Message, ProjectEvent, Run, Workspace } from '@/contracts/api'
import type { ApiResult } from '@/contracts/requests'
import { api } from '@/lib/api'
import { invalidateCatalog } from '@/lib/catalog'
import { applyChatClear, generationKey, requestsKey, settingsKey } from '@/lib/agent-controls'
import { keys, type CachedPages } from '@/lib/queries'
import { preferCurrent } from '@/lib/queries/reconcile'

function upsert<R extends { id: string }>(client: QueryClient, p: string, resource: string, item: R) {
  client.setQueriesData<CachedPages<R>>({ queryKey: ['project', p, resource, 'list'] }, old => {
    if (!old) return old
    // Update existing rows. Refetch filtered/paginated lists to place new entities correctly.
    return { ...old, pages: old.pages.map(page => ({ ...page, data: { ...page.data, items: page.data.items.map(row => row.id === item.id ? preferCurrent(row, item) : row) } })) }
  })
  client.setQueryData<ApiResult<R>>(keys.detail(p, resource, item.id), old => {
    const data = preferCurrent(old?.data, item)
    const revision = 'revision' in data && typeof data.revision === 'number' ? data.revision : null
    return { data, etag: revision !== null ? `"${revision}"` : old?.etag ?? null, request_id: old?.request_id ?? null }
  })
}
export async function applyProjectEvent(client: QueryClient, event: ProjectEvent, signal?: AbortSignal) {
  if (signal?.aborted) return
  const p = event.project_id
  const currentGeneration = client.getQueryData<number>(generationKey(p)) ?? 0
  if ((event.type === 'message.created' || event.type === 'message.updated') && (event.payload.message.chat_generation ?? 0) < currentGeneration) return
  if (event.type === 'message.delta' && (event.payload.chat_generation ?? 0) < currentGeneration) return
  const invalidate = (resource: string) => client.invalidateQueries({ queryKey: ['project', p, resource] })
  switch (event.type) {
    case 'chat.cleared': await applyChatClear(client, event.payload); return
    case 'agent.settings.updated': void client.invalidateQueries({ queryKey: settingsKey(p) }); return
    case 'organization.request.updated': void client.invalidateQueries({ queryKey: requestsKey(p) }); await invalidateCatalog(client, p); return
    case 'run.created': case 'run.updated': {
      const previous = client.getQueryData<ApiResult<Run>>(keys.detail(p, 'runs', event.payload.run.id))?.data
      if (previous && previous.revision > event.payload.run.revision) return
      upsert(client, p, 'runs', event.payload.run)
      if (event.type === 'run.created') void invalidate('runs')
      const run = event.payload.run
      client.setQueryData<ApiResult<Workspace>>(keys.detail(p, 'workspace', p), old => {
        if (!old) return old
        const active = new Set(old.data.active_run_ids)
        if (['succeeded', 'failed', 'cancelled'].includes(run.status)) active.delete(run.id); else active.add(run.id)
        return { ...old, data: { ...old.data, active_run_ids: [...active] } }
      })
      if (['succeeded', 'failed', 'cancelled'].includes(run.status) && previous?.status !== run.status) {
        // Terminal transitions: refresh saved outputs once through the shared cache.
        void client.invalidateQueries({ queryKey: keys.detail(p, 'results', run.id) })
        void invalidate('workspace')
        if (run.input.kind === 'paper_ingest' || run.input.kind === 'report') void invalidate('catalog:files')
      }
      return
    }
    case 'message.created': case 'message.updated':
      upsert(client, p, 'messages', event.payload.message)
      if (event.type === 'message.created') void invalidate('messages')
      return
    case 'message.delta': {
      const { message_id, chunk_index, text } = event.payload
      const cached = client.getQueryData<ApiResult<Message>>(keys.detail(p, 'messages', message_id))?.data
      const listed = client.getQueriesData<CachedPages<Message>>({ queryKey: ['project', p, 'messages', 'list'] }).flatMap(([, value]) => value?.pages.flatMap(page => page.data.items) ?? []).find(m => m.id === message_id)
      const message = preferCurrent(listed, cached ?? listed)
      if (message && (message.status !== 'streaming' || chunk_index <= (message.last_chunk_index ?? -1))) return
      if (!message || chunk_index !== (message.last_chunk_index ?? -1) + 1) {
        const result = await api.messages.get(p, message_id, signal)
        if (signal?.aborted) return
        if ((result.data.chat_generation ?? 0) < (client.getQueryData<number>(generationKey(p)) ?? 0)) return
        upsert(client, p, 'messages', result.data)
      } else upsert(client, p, 'messages', { ...message, content_markdown: message.content_markdown + text, last_chunk_index: chunk_index })
      return
    }
    case 'project.updated':
      client.setQueryData<ApiResult<typeof event.payload.project>>(keys.detail(p, 'project', p), old => {
        const data = preferCurrent(old?.data, event.payload.project)
        return { data, etag: `"${data.revision}"`, request_id: null }
      })
      void client.invalidateQueries({ queryKey: ['projects'] }); return
    case 'experiment.updated': upsert(client, p, 'experiments', event.payload.experiment); void invalidate('experiments'); return
    case 'source.created': upsert(client, p, 'sources', event.payload.source); void invalidate('sources'); void invalidate('workspace'); return
    case 'claim.created': upsert(client, p, 'claims', event.payload.claim); void invalidate('claims'); return
    case 'artifact.created':
      upsert(client, p, 'artifacts', event.payload.artifact); void invalidate('artifacts'); void invalidate('workspace')
      if (event.payload.artifact.kind === 'report') void invalidate('catalog:files')
      return
    case 'upload.updated': client.setQueryData(keys.detail(p, 'uploads', event.payload.upload.id), { data: event.payload.upload, etag: null, request_id: null }); return
    case 'results.updated': void invalidate('results'); return
    case 'measurements.available': void invalidate(`measurements:${event.payload.run_id}`); void invalidate('results'); return
    case 'run.log': {
      const entry = event.payload.entry
      // Preserve the live tail even when older paginated history is not loaded.
      client.setQueryData<LogEntry[]>(keys.detail(p, 'live-logs', entry.run_id), old => {
        const entries = new Map((old ?? []).map(row => [row.sequence, row]))
        entries.set(entry.sequence, entry)
        return [...entries.values()].sort((a, b) => a.sequence - b.sequence).slice(-1000)
      })
      client.setQueriesData<CachedPages<typeof entry>>({ queryKey: ['project', p, `logs:${entry.run_id}`, 'list'] }, old => {
        if (!old || old.pages.some(page => page.data.items.some(row => row.sequence === entry.sequence))) return old
        const lastSequence = Math.max(-1, ...old.pages.flatMap(page => page.data.items.map(row => row.sequence)))
        if (lastSequence >= 0 && entry.sequence > lastSequence + 1) void invalidate(`logs:${entry.run_id}`)
        const tail = old.pages.at(-1)
        if (tail?.data.next_cursor) { void invalidate(`logs:${entry.run_id}`); return old }
        return { ...old, pages: old.pages.map((page, index) => index === old.pages.length - 1 ? { ...page, data: { ...page.data, items: [...page.data.items, entry].sort((a, b) => a.sequence - b.sequence).slice(-1000) } } : page) }
      })
      return
    }
    case 'approval.required': case 'approval.updated': void invalidate(`approvals:${event.payload.approval.run_id}`); void invalidate('runs'); return
    case 'catalog.changed': {
      await invalidateCatalog(client, p)
      return
    }
    default: return
  }
}
export function cachedActiveRuns(client: QueryClient, p: string): string[] {
  const workspace = client.getQueryData<ApiResult<Workspace>>(keys.detail(p, 'workspace', p))?.data
  const ids = new Set(workspace?.active_run_ids ?? [])
  for (const [, result] of client.getQueriesData<ApiResult<Run>>({ queryKey: ['project', p, 'runs', 'detail'] })) {
    if (!result) continue
    if (['succeeded', 'failed', 'cancelled'].includes(result.data.status)) ids.delete(result.data.id)
    else ids.add(result.data.id)
  }
  return [...ids]
}
