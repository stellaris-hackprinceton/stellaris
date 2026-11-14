'use client'
/* eslint-disable @next/next/no-img-element -- Artifact previews require session cookies that the image optimizer cannot forward. */

import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import type { Artifact } from '@/contracts/api'
import { artifactContentUrl, readText } from '@/lib/api'
import { ErrorNotice } from '@/features/execution/feedback'
import styles from '@/features/execution/sol.module.css'

export function SafeMarkdown({ text }: { text: string }) {
  return <div className={styles.markdown}><ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]} urlTransform={(url, key) => {
    if (key === 'src') {
      // Only authenticated project artifact images can load automatically.
      return /^\/api\/v1\/projects\/[^/]+\/artifacts\/[^/]+\/content(?:\?|$)/.test(url) ? url : ''
    }
    return /^(https?:\/\/|mailto:|\/[^/]|#)/i.test(url) ? url : ''
  }} components={{ a: ({ href, children }) => <a href={href} rel="noopener noreferrer">{children}</a>, img: ({ src, alt }) => typeof src === 'string' && src ? <img src={src} alt={alt ?? 'Research figure'} loading="lazy" /> : <span>Image unavailable in this preview</span> }}>{text}</ReactMarkdown></div>
}
function TextPreview({ artifact, project_id }: { artifact: Artifact, project_id: string }) {
  const text = useQuery({ queryKey: ['project', project_id, 'artifact-text', artifact.id, artifact.sha256], queryFn: ({ signal }) => readText(artifactContentUrl(project_id, artifact.id, 'inline'), signal), retry: false })
  return <><ErrorNotice error={text.error} />{text.isPending && <p>Loading text preview…</p>}{text.data?.truncated && <p className={styles.notice}>This preview is limited to the first 256 KiB. Download the artifact for its complete content.</p>}{text.data && (artifact.kind === 'report' || artifact.mime_type === 'text/markdown' ? <SafeMarkdown text={text.data.text} /> : <pre tabIndex={0}>{text.data.text}</pre>)}</>
}
export function ArtifactPreview({ artifact, project_id }: { artifact: Artifact, project_id: string }) {
  if (artifact.project_id !== project_id) return <p role="alert">Artifact unavailable in this project.</p>
  const url = artifactContentUrl(project_id, artifact.id, 'inline')
  const mime = artifact.mime_type.toLowerCase().split(';')[0]
  if (['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/avif'].includes(mime)) return <img src={url} alt={artifact.filename} />
  if (['video/mp4', 'video/webm', 'video/ogg'].includes(mime)) return <video controls preload="metadata" src={url} aria-label={artifact.filename} />
  if (['audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/webm', 'audio/ogg'].includes(mime)) return <audio controls preload="metadata" src={url} aria-label={artifact.filename} />
  if ((mime.startsWith('text/') && !['text/html', 'text/xml'].includes(mime)) || ['application/json', 'application/x-python', 'application/x-ndjson'].includes(mime)) return <TextPreview artifact={artifact} project_id={project_id} />
  return <p>This format is not embedded. Use the authenticated download to inspect it.</p>
}
