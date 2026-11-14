import { readFile, realpath } from 'node:fs/promises'
import path from 'node:path'
import { connection } from 'next/server'

// Serve the one canonical documentation tree. No copied public/docs directory.
export async function GET(_request: Request, context: { params: Promise<{ path?: string[] }> }) {
  await connection()
  const segments = (await context.params).path ?? ['README.md']
  if (segments.some(part => !part || part === '.' || part === '..' || /[\\/\0]/.test(part)) || !segments.at(-1)?.endsWith('.md')) {
    return new Response('Documentation not found.', { status: 404 })
  }
  try {
    // Docker copies docs explicitly. Do not trace unrelated application files.
    const root = await realpath(/* turbopackIgnore: true */ process.env.STELLARIS_DOCS_ROOT ?? path.resolve(process.cwd(), '..', 'docs'))
    const file = await realpath(/* turbopackIgnore: true */ path.join(root, ...segments))
    if (!file.startsWith(root + path.sep)) return new Response('Documentation not found.', { status: 404 })
    const markdown = await readFile(/* turbopackIgnore: true */ file, 'utf8')
    return new Response(markdown, { headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'X-Content-Type-Options': 'nosniff',
      'Content-Security-Policy': "default-src 'none'",
      'Cache-Control': 'no-store',
    } })
  } catch {
    return new Response('Documentation not found.', { status: 404 })
  }
}
