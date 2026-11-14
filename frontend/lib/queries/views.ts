'use client'
// Research, Materials and Reports share the catalog's transport, normalized keys,
// revision reconciliation and event invalidation. Unsupported filters stay disabled.
import type { Artifact } from '@/contracts/api'
import type { FileListFilters, FileOriginType, WorkspaceFile } from '@/contracts/catalog'
import { useCatalogFeatures, useFiles } from '@/lib/catalog'

export type ArtifactKind = Artifact['kind']
export type ViewFile = WorkspaceFile
export type CatalogViewFilter = {
  origin_type?: FileOriginType,
  artifact_kinds?: ArtifactKind[],
  q?: string,
  sort: 'created_at' | 'updated_at',
  order: 'asc' | 'desc',
}
export type CatalogViewUnsupported = 'catalog' | 'views' | null

export function useCatalogView(p: string, filter: CatalogViewFilter, limit: number) {
  const capabilities = useCatalogFeatures()
  const unsupported: CatalogViewUnsupported = capabilities.is_loading || capabilities.error ? null
    : !capabilities.files ? 'catalog'
      : filter.artifact_kinds?.length && !capabilities.views ? 'views' : null
  const filters: FileListFilters = { status: 'active', ...filter, limit }
  const result = useFiles(p, filters, !unsupported && !capabilities.is_loading && !capabilities.error)
  return {
    ...result, unsupported,
    capability_pending: capabilities.is_loading,
    capability_error: capabilities.error,
    is_loading: !unsupported && !capabilities.is_loading && !capabilities.error && result.is_loading,
    is_next_page_error: !!result.error && result.items.length > 0,
  }
}
