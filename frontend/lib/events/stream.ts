import type { ProjectEvent } from '@/contracts/api'
import { apiUrl, responseError, resourcePath } from '@/lib/api'

export async function consumeEvents(project: string, cursor: string, signal: AbortSignal, onEvent: (event: ProjectEvent) => Promise<void>, onOpen: () => void) {
  const response = await fetch(apiUrl(resourcePath(project, 'events')) + `?after=${encodeURIComponent(cursor)}`, {
    headers: { Accept: 'text/event-stream', 'Last-Event-ID': cursor }, credentials: 'same-origin', cache: 'no-store', signal,
  })
  if (!response.ok) throw await responseError(response)
  if (!response.headers.get('Content-Type')?.includes('text/event-stream') || !response.body) throw new Error('The backend did not return an event stream.')
  const reader = response.body.getReader(), decoder = new TextDecoder()
  let buffer = '', data: string[] = [], id = '', eventType = '', firstLine = true
  onOpen()
  async function line(value: string) {
    if (firstLine) { value = value.replace(/^\uFEFF/, ''); firstLine = false }
    if (!value) {
      if (data.length) {
        const parsed: unknown = JSON.parse(data.join('\n'))
        if (!parsed || typeof parsed !== 'object') throw new Error('Invalid project event.')
        const event = parsed as ProjectEvent
        if (event.project_id !== project || !event.cursor || event.cursor !== id || (eventType && event.type !== eventType)) throw new Error('Project event identity does not match its stream.')
        await onEvent(event)
      }
      data = []; id = ''; eventType = ''; return
    }
    if (value.startsWith(':')) return
    const index = value.indexOf(':')
    const field = index < 0 ? value : value.slice(0, index)
    const content = index < 0 ? '' : value.slice(index + 1).replace(/^ /, '')
    if (field === 'data') data.push(content)
    if (field === 'id' && !content.includes('\0')) id = content
    if (field === 'event') eventType = content
    if (data.reduce((size, row) => size + row.length, 0) > 1048576) throw new Error('Event exceeded the supported size.')
  }
  try {
    while (true) {
      const chunk = await reader.read()
      if (chunk.done) throw new Error('The event stream disconnected.')
      buffer += decoder.decode(chunk.value, { stream: true })
      let boundary: number
      while ((boundary = buffer.search(/[\r\n]/)) >= 0) {
        if (buffer[boundary] === '\r' && boundary === buffer.length - 1) break
        const width = buffer.slice(boundary, boundary + 2) === '\r\n' ? 2 : 1
        const value = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + width)
        await line(value)
      }
      if (buffer.length > 1048576) throw new Error('Event line exceeded the supported size.')
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock() }
}
