import type { ID, Timestamp } from './api'

export type FileKind = 'artifact' | 'record' | 'note'
export type FileOriginType = 'artifact' | 'source' | 'claim' | 'experiment' | 'run' | 'run_measurements'
export type ScientificOrigin = 'observed' | 'derived' | 'simulated' | 'generated' | 'reference'
export type FileTag = { slug: string, assigned_by: 'system' | 'user' }
export type WorkspaceFile = {
  id: ID, project_id: ID, name: string, file_kind: FileKind,
  origin: { type: FileOriginType, id: ID, revision: number | null } | null,
  scientific_origin: ScientificOrigin | null, mime_type: string, size_bytes: number,
  content_sha256: string, editable: { name: boolean, content: boolean, tags: true },
  status: 'active' | 'trashed', tags: FileTag[], collection_ids: ID[],
  content_revision: number | null, revision: number, created_at: Timestamp, updated_at: Timestamp
}
export type NoteRevision = {
  file_id: ID, content_revision: number, name: string, mime_type: 'text/markdown' | 'text/plain',
  size_bytes: number, content_sha256: string, created_at: Timestamp
}
export type Tag = {
  slug: string, label: string, color: string | null, system: boolean, file_count: number,
  revision: number, created_at: Timestamp, updated_at: Timestamp
}
export type FileFilter = {
  tags?: string[], file_kind?: FileKind, origin_type?: FileOriginType,
  status?: 'active' | 'trashed' | 'all', q?: string
}
export type Collection = {
  id: ID, project_id: ID, name: string, description: string, filter: FileFilter | null,
  file_count: number, revision: number, created_at: Timestamp, updated_at: Timestamp
}
export type Relation = {
  id: ID, project_id: ID, from_file_id: ID, to_file_id: ID, type: string,
  note: string | null, created_by: 'user' | 'system', created_at: Timestamp
}
export type CatalogStatus = {
  schema_version: number, workspace_files: boolean, last_synced_at: Timestamp | null,
  projected: { artifact: number, source: number, claim: number, experiment: number, run: number, run_measurements: number },
  notes: { count: number, retained_bytes: number, max_bytes: number },
  last_sync_error: { code: string, message: string } | null
}
export type FileListFilters = FileFilter & {
  collection_id?: ID, sort?: 'created_at' | 'updated_at' | 'name', order?: 'asc' | 'desc',
  limit?: number, cursor?: string
}
export type RelationFilters = { file_id?: ID, direction?: 'out' | 'in' | 'both', type?: string, created_by?: 'user' | 'system', limit?: number, cursor?: string }
export type CreateNote = { name: string, content: string, mime_type?: 'text/markdown' | 'text/plain', tags?: string[] }
export type EditFile = { name?: string, content?: string, status?: 'active' | 'trashed', tags?: string[] }
export type CreateTag = { slug: string, label?: string, color?: string | null }
export type EditTag = { label?: string, color?: string | null }
export type CreateCollection = { name: string, description?: string, filter?: FileFilter | null }
export type EditCollection = { name?: string, description?: string, filter?: FileFilter | null }
export type CreateRelation = { from_file_id: ID, to_file_id: ID, type?: string, note?: string | null }
