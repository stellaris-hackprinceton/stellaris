'use client'
import type { QueryClient } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import type { AgentSettings, ChatClear, OrganizationRequest, Page } from '@/contracts/api'
import { request, resourcePath } from '@/lib/api'
import { useCapabilities, useSession } from '@/lib/queries'

export const settingsKey = (p: string) => ['project', p, 'agent-settings'] as const
export const requestsKey = (p: string) => ['project', p, 'organization-requests'] as const
export const generationKey = (p: string) => ['project', p, 'chat-generation'] as const
const base = (p: string) => resourcePath(p, 'agent-settings')
export const agentControlsApi = {
  settings: (p: string, signal?: AbortSignal) => request<AgentSettings>(base(p), { signal }),
  permission: (p: string, organization_permission: AgentSettings['organization_permission'], etag: string) => request<AgentSettings>(base(p), { method: 'PATCH', body: { organization_permission }, edit: { etag } }),
  requests: (p: string, signal?: AbortSignal) => request<Page<OrganizationRequest>>(resourcePath(p, 'organization-requests') + '?status=pending&limit=50', { signal }),
  decide: (p: string, id: string, decision: 'approve' | 'reject', key: string) => request<OrganizationRequest>(resourcePath(p, 'organization-requests', id) + '/decision', { method: 'POST', body: { decision }, command: { idempotency_key: key } }),
  clear: (p: string, key: string) => request<ChatClear>(resourcePath(p, 'chat') + '/clear', { method: 'POST', body: {}, command: { idempotency_key: key } }),
}
export function useAgentSettings(p: string) {
  const session = useSession(), caps = useCapabilities()
  return useQuery({ queryKey: settingsKey(p), queryFn: ({ signal }) => agentControlsApi.settings(p, signal), enabled: !!session.data && caps.data?.features.agent_controls === true, retry: false })
}
export function useOrganizationRequests(p: string) {
  const session = useSession(), caps = useCapabilities()
  return useQuery({ queryKey: requestsKey(p), queryFn: ({ signal }) => agentControlsApi.requests(p, signal), enabled: !!session.data && caps.data?.features.agent_controls === true, retry: false })
}
export async function applyChatClear(client: QueryClient, cleared: ChatClear) {
  const p = cleared.project_id
  const previous = client.getQueryData<number>(generationKey(p)) ?? 0
  if (cleared.generation < previous) return
  client.setQueryData(generationKey(p), cleared.generation)
  await client.cancelQueries({ queryKey: ['project', p, 'messages'] })
  await client.resetQueries({ queryKey: ['project', p, 'messages'] })
  await client.invalidateQueries({ queryKey: ['project', p, 'workspace'] })
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('stellaris:chat-cleared', { detail: cleared }))
}
