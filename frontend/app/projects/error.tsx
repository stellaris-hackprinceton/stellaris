'use client'
import Link from 'next/link'
export default function ProjectError({ reset }: { reset: () => void }) {
  return <main style={{ padding: 24 }}><h1>This workspace could not be opened</h1><p>Your saved research has not been replaced.</p><button onClick={reset}>Try opening it again</button><Link href="/projects">Back to projects</Link></main>
}
