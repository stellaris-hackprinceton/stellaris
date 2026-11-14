'use client'

import { Button } from '@/components/ui'
import { ApiError } from '@/lib/api'
import styles from './connection-notice.module.css'

export function ConnectionNotice({ error, endpoint, pending, retry }: {
  error: unknown, endpoint: '/api/v1/session' | '/api/v1/capabilities', pending: boolean, retry: () => void
}) {
  return <main className={styles.page}>
    <section className={styles.panel} aria-labelledby="connection-title">
      <h1 id="connection-title">Stellaris can’t connect to the research backend</h1>
      <p className={styles.description}>The frontend is running, but the research service isn’t available. Start the backend or check its API connection, then try again.</p>
      <div className={styles.actions}>
        <Button variant="primary" pending={pending} onClick={retry}>Retry connection</Button>
        <a href="/docs/connection-setup.md">Connection setup guide</a>
      </div>
      <p className={styles.footnote}>Your saved project data has not been changed.</p>
      <details className={styles.diagnostics}>
        <summary>Connection details</summary>
        <dl>
          <dt>Request</dt><dd><code>{endpoint}</code></dd>
          {error instanceof ApiError && <><dt>HTTP status</dt><dd>{error.status}</dd><dt>Error code</dt><dd>{error.code}</dd>{error.request_id && <><dt>Request ID</dt><dd>{error.request_id}</dd></>}</>}
          <dt>Message</dt><dd>{error instanceof Error ? error.message : 'The request did not complete.'}</dd>
        </dl>
      </details>
    </section>
  </main>
}
