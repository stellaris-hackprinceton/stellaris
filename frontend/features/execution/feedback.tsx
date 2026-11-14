'use client'
import { ApiError } from '@/lib/api'
import styles from './sol.module.css'
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null
  return <div role="alert" className={styles.error}><p>{error instanceof Error ? error.message : 'The request could not be completed.'}</p>{error instanceof ApiError && <><p>Code: {error.error.code}{error.error.request_id ? ` · Request: ${error.error.request_id}` : ''}</p>{Object.keys(error.error.details).length > 0 && <details><summary>Validation details</summary><pre>{JSON.stringify(error.error.details, null, 2)}</pre></details>}{error.status === 412 && <p>Your saved version changed. Preserve your draft and reload before reapplying edits.</p>}{error.error.code === 'EXPERIMENT_REVISION_CONFLICT' && <p>Review the latest saved experiment before submitting a new analysis.</p>}</>}</div>
}
export function PageMore({ has_more, loading, load }: { has_more: boolean, loading: boolean, load: () => unknown }) { return has_more ? <button type="button" disabled={loading} onClick={() => void load()}>{loading ? 'Loading…' : 'Load more'}</button> : null }
export const projectHref = (p: string) => `/projects/${encodeURIComponent(p)}`
export const runHref = (p: string, r: string) => `${projectHref(p)}/runs/${encodeURIComponent(r)}`
export const artifactHref = (p: string, a: string) => `${projectHref(p)}/workspace?artifact=${encodeURIComponent(a)}`
