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
      // Only project file images can load automatically.
      return /^\/api\/v1\/projects\/[^/]+\/artifacts\/[^/]+\/content(?:\?|$)/.test(url) ? url : ''
    }
    return /^(https?:\/\/|mailto:|\/[^/]|#)/i.test(url) ? url : ''
  }} components={{ a: ({ href, children }) => <a href={href} rel="noopener noreferrer">{children}</a>, img: ({ src, alt }) => typeof src === 'string' && src ? <img src={src} alt={alt ?? 'Research figure'} loading="lazy" /> : <span>Image unavailable in this preview</span> }}>{text}</ReactMarkdown></div>
}
function formatJson(text: string) {
  try { return JSON.stringify(JSON.parse(text), null, 2) } catch { return text }
}
function TextPreview({ artifact, project_id, mime }: { artifact: Artifact, project_id: string, mime: string }) {
  // The bytes are read by fetch and rendered only as escaped text or sanitized Markdown, never by the browser
  // itself, so the default attachment disposition is used. The backend keeps `inline` limited to its approved
  // types (JSON, for example, is attachment-only), which made inline requests for JSON fail with 400.
  const text = useQuery({ queryKey: ['project', project_id, 'artifact-text', artifact.id, artifact.sha256], queryFn: ({ signal }) => readText(artifactContentUrl(project_id, artifact.id), signal), retry: false })
  const body = text.data && mime === 'application/json' && !text.data.truncated ? formatJson(text.data.text) : text.data?.text
  return <><ErrorNotice error={text.error} />{text.isPending && <p>Loading text preview…</p>}{text.data?.truncated && <p className={styles.notice}>This preview is limited to the first 256 KiB. Download the file to view its complete contents.</p>}{text.data && (artifact.kind === 'report' || mime === 'text/markdown' ? <SafeMarkdown text={text.data.text} /> : <pre tabIndex={0} aria-label={`Contents of ${artifact.filename}`}>{body}</pre>)}</>
}
export function ArtifactPreview({ artifact, project_id }: { artifact: Artifact, project_id: string }) {
  if (artifact.project_id !== project_id) return <p role="alert">File unavailable in this project.</p>
  const url = artifactContentUrl(project_id, artifact.id, 'inline')
  const mime = artifact.mime_type.toLowerCase().split(';')[0]
  if (['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/avif'].includes(mime)) return <img src={url} alt={artifact.filename} />
  if (['video/mp4', 'video/webm', 'video/ogg'].includes(mime)) return <video controls preload="metadata" src={url} aria-label={artifact.filename} />
  if (['audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/webm', 'audio/ogg'].includes(mime)) return <audio controls preload="metadata" src={url} aria-label={artifact.filename} />
  if ((mime.startsWith('text/') && !['text/html', 'text/xml'].includes(mime)) || ['application/json', 'application/x-python', 'application/x-ndjson'].includes(mime)) return <TextPreview artifact={artifact} project_id={project_id} mime={mime} />
  return <p>This file type ({mime || 'unknown type'}) has no in-app preview. Download it to inspect its contents.</p>
}
