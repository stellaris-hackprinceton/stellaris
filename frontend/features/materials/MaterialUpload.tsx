'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useQueryClient } from '@tanstack/react-query'
import type { ID } from '@/contracts/api'
import { Button, Dialog } from '@/components/ui'
import { keys, useCapabilities } from '@/lib/queries'
import { invalidateCatalog } from '@/lib/catalog'
import { hrefs } from '@/components/shell/hrefs'
import { kindForMime } from '@/features/studio/upload/FileImport'
import { UploadProgressView } from '@/features/studio/upload/UploadProgressView'
import { useArtifactUpload } from '@/features/studio/upload/useArtifactUpload'
import { mimeForFile } from '@/features/studio/upload/fileTypes'
import styles from '@/features/studio/studio.module.css'

type Props = { project_id: ID, archived: boolean }
const EXTENSIONS: [string, string[]][] = [
  ['.csv', ['text/csv']], ['.json', ['application/json']], ['.txt', ['text/plain']], ['.tsv', ['text/plain']],
  ['.py', ['text/x-python']], ['.js', ['text/javascript', 'application/javascript']], ['.sh', ['text/x-shellscript']],
]

export function MaterialUpload({ project_id, archived }: Props) {
  const client = useQueryClient()
  const capabilities = useCapabilities()
  const upload = useArtifactUpload(project_id)
  const [open, setOpen] = useState(false)
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const picker = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const artifact = upload.phase === 'ready' ? upload.artifact : null
    if (!artifact) return
    client.setQueryData(keys.detail(project_id, 'artifacts', artifact.id), { data: artifact, etag: null, request_id: null })
    void client.invalidateQueries({ predicate: query => query.queryKey[0] === 'project' && query.queryKey[1] === project_id && query.queryKey[2] === 'artifacts' })
    void invalidateCatalog(client, project_id)
  }, [client, project_id, upload.artifact, upload.phase])

  useEffect(() => {
    if (!open || !upload.busy) return
    const preventClose = (event: Event) => {
      const target = event.target
      if (target instanceof HTMLDialogElement && target.classList.contains('materialUploadDialog')) event.preventDefault()
    }
    document.addEventListener('cancel', preventClose, true)
    return () => document.removeEventListener('cancel', preventClose, true)
  }, [open, upload.busy])

  const uploads = capabilities.data?.uploads
  const accepted = uploads?.accepted_mime_types.map(mime => mime.toLowerCase()) ?? []
  const accept = [...(uploads?.accepted_mime_types ?? []), ...EXTENSIONS.filter(([, types]) => types.some(type => accepted.includes(type))).map(([extension]) => extension)].join(',')

  function startUpload(file: File) {
    const mime = mimeForFile(file.type, file.name)
    if (!mime) { setSelectionError('This file type could not be identified. Choose a supported file.'); return }
    if (!accepted.includes(mime)) { setSelectionError(`Materials does not accept ${mime} files.`); return }
    if (uploads && file.size > uploads.max_file_bytes) {
      setSelectionError("This file is larger than this project's upload limit.")
      return
    }
    const kind = kindForMime(mime, file.name)
    setSelectionError(null)
    upload.start({
      blob: file.slice(0, file.size, mime),
      request: {
        filename: file.name, mime_type: mime, size_bytes: file.size, kind, origin: 'reference',
        capture: { method: 'file_upload', recorded_at: null, recording_permission_confirmed: false },
      },
    })
    setOpen(true)
  }

  function selectFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (file) startUpload(file)
  }

  function close() {
    if (!upload.busy) setOpen(false)
  }

  const artifact = upload.phase === 'ready' ? upload.artifact : null
  const allMaterialsHref = artifact ? `${hrefs.view(project_id, 'materials')}?view=all&artifact=${encodeURIComponent(artifact.id)}` : ''

  return <>
    <input ref={picker} type="file" hidden disabled={archived || upload.busy || !uploads} accept={accept} onChange={selectFile} />
    <button type="button" disabled={archived || upload.busy || !uploads} onClick={() => { setSelectionError(null); picker.current?.click() }}>Upload file</button>
    {selectionError && <p role="alert" className={styles.fieldError}>{selectionError}</p>}
    <Dialog open={open} onClose={close} title="Upload file to Materials" className="materialUploadDialog" keepMounted>
      <div className={styles.stack}>
        {upload.phase === 'idle' && <Button onClick={() => picker.current?.click()}>Choose a file</Button>}
        <UploadProgressView up={upload}>
          {artifact && <div className={styles.stack}>
            <p className={styles.muted}>Saved to Materials: <strong>{artifact.filename}</strong></p>
            <div className={styles.row}>
              <Link href={allMaterialsHref} onClick={close}>View in All materials</Link>
              <Button onClick={() => { upload.reset(); picker.current?.click() }}>Upload another</Button>
              <Button onClick={close}>Close</Button>
            </div>
          </div>}
        </UploadProgressView>
      </div>
    </Dialog>
  </>
}
