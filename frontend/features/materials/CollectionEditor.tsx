'use client'

import type { Collection } from '@/contracts/catalog'
import { useState } from 'react'
import { catalogApi, useCatalogMutation } from '@/lib/catalog'
import { ErrorNotice } from '@/features/execution/feedback'
import styles from './materials.module.css'

export function CollectionEditor({ project_id, collection, archived }: { project_id: string; collection: Collection; archived: boolean }) {
  const mutation = useCatalogMutation(project_id)
  const [base, setBase] = useState(collection)
  return <details onToggle={event => { if (event.currentTarget.open) { setBase(collection); mutation.reset() } }}><summary>Edit collection</summary>
    <form key={base.revision} className={styles.form} onSubmit={async event => {
      event.preventDefault()
      const fields = new FormData(event.currentTarget)
      const tags = String(fields.get('tags') ?? '').split(',').map(tag => tag.trim()).filter(Boolean)
      const body = {
        name: String(fields.get('name')).trim(), description: String(fields.get('description')),
        ...(base.filter ? { filter: { ...base.filter, tags, q: String(fields.get('q')).trim() || undefined, status: String(fields.get('status')) as 'active' | 'trashed' | 'all' } } : {}),
      }
      try { await mutation.mutateAsync(() => catalogApi.editCollection(project_id, base.id, body, { etag: `"${base.revision}"` })) } catch { /* Keep the form values for review and retry. */ }
    }}>
      <label>Collection name<input name="name" required defaultValue={base.name} maxLength={120} /></label>
      <label>Description<textarea name="description" defaultValue={base.description} maxLength={2000} /></label>
      {base.filter && <>
        <label>Required tag slugs, separated by commas<input name="tags" defaultValue={base.filter.tags?.join(', ') ?? ''} /></label>
        <label>Name contains<input name="q" defaultValue={base.filter.q ?? ''} maxLength={100} /></label>
        <label>Included materials<select name="status" defaultValue={base.filter.status ?? 'active'}><option value="active">Active</option><option value="trashed">Trash</option><option value="all">Active and trash</option></select></label>
        <p className={styles.meta}>Materials must match every required tag. Other saved filter constraints remain in place.</p>
      </>}
      <button disabled={archived || mutation.isPending}>Save collection</button>
      <ErrorNotice error={mutation.error} />
    </form>
  </details>
}
