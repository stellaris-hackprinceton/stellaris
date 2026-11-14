'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useQueryClient } from '@tanstack/react-query'
import type { ID, UploadRequest } from '@/contracts/api'
import { Button, Dialog } from '@/components/ui'
import { keys, useCapabilities } from '@/lib/queries'
import { invalidateCatalog } from '@/lib/catalog'
import { hrefs } from '@/components/shell/hrefs'
import { FileImport } from '@/features/studio/upload/FileImport'
import { UploadProgressView } from '@/features/studio/upload/UploadProgressView'
import { useArtifactUpload } from '@/features/studio/upload/useArtifactUpload'
import { mimeForFile } from '@/features/studio/upload/fileTypes'
import styles from '@/features/studio/studio.module.css'

type Props = { project_id: ID, archived: boolean }

export function MaterialUpload({ project_id, archived }: Props) {
  const client = useQueryClient()
  const capabilities = useCapabilities()
  const upload = useArtifactUpload(project_id)
  const [open, setOpen] = useState(false)

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

  function startUpload(file: File, kind: UploadRequest['kind'], origin: UploadRequest['origin']) {
    const mime = mimeForFile(file.type, file.name)
    upload.start({
      blob: file.slice(0, file.size, mime),
      request: {
        filename: file.name, mime_type: mime, size_bytes: file.size, kind, origin,
        capture: { method: 'file_upload', recorded_at: null, recording_permission_confirmed: false },
      },
    })
  }

  function close() {
    if (!upload.busy) setOpen(false)
  }

  const artifact = upload.phase === 'ready' ? upload.artifact : null
  const allMaterialsHref = artifact ? `${hrefs.view(project_id, 'materials')}?view=all&artifact=${encodeURIComponent(artifact.id)}` : ''

  return <>
    <button type="button" disabled={archived} onClick={() => setOpen(true)}>Upload file</button>
    <Dialog open={open} onClose={close} title="Upload file to Materials" className="materialUploadDialog" keepMounted>
      <div className={styles.stack}>
        {upload.phase !== 'ready' && <FileImport uploads={capabilities.data?.uploads} disabled={archived || upload.busy}
          onUpload={startUpload} autoFocus={open && !upload.busy && upload.phase === 'idle'} />}
        <UploadProgressView up={upload}>
          {artifact && <div className={styles.stack}>
            <p className={styles.muted}>Saved to Materials: <strong>{artifact.filename}</strong></p>
            <div className={styles.row}>
              <Link href={allMaterialsHref} onClick={close}>View in All materials</Link>
              <Button onClick={upload.reset}>Upload another</Button>
              <Button onClick={close}>Close</Button>
            </div>
          </div>}
        </UploadProgressView>
      </div>
    </Dialog>
  </>
}
