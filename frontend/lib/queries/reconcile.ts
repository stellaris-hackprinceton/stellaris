export function preferCurrent<R>(current: R | undefined, incoming: R): R {
  if (!current || typeof current !== 'object' || typeof incoming !== 'object' || !incoming) return incoming
  const a = current as Record<string, unknown>, b = incoming as Record<string, unknown>
  if (typeof a.revision === 'number' && typeof b.revision === 'number' && a.revision > b.revision) return current
  if ('last_chunk_index' in a && 'last_chunk_index' in b) {
    if (a.status !== 'streaming' && b.status === 'streaming') return current
    const oldIndex = typeof a.last_chunk_index === 'number' ? a.last_chunk_index : -1
    const newIndex = typeof b.last_chunk_index === 'number' ? b.last_chunk_index : -1
    if (oldIndex > newIndex) return current
  }
  return incoming
}
