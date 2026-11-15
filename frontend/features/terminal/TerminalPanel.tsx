'use client'
import dynamic from 'next/dynamic'
import { useRef, useState, useSyncExternalStore, type CSSProperties } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { TerminalSession } from '@/contracts/terminal'
import { ApiError } from '@/lib/api/http'
import { useCapabilities, useProject } from '@/lib/queries'
import { isActiveTerminal, setCurrentTerminal, terminalApi, terminalKey, useCurrentTerminal } from '@/lib/terminal'
import {
  Button, CloseIcon, Dialog, EmptyState, ErrorNotice, IconButton, ResizeHandle, Skeleton, StatusBadge, describeError, errorCode, newCommandKey, usePanelSize,
  type StatusTone,
} from '@/components/ui'
import styles from './terminal.module.css'

const TerminalView = dynamic(() => import('./TerminalView').then(m => m.TerminalView), {
  ssr: false, loading: () => <p className={styles.note}>Loading terminal…</p>,
})

export const TERMINAL_PANEL_ID = 'project-terminal'
const DEFAULT_SIZE = { rows: 24, cols: 80 }

const STATUS: Record<TerminalSession['status'], { label: string, tone: StatusTone }> = {
  starting: { label: 'Starting — request accepted', tone: 'info' },
  running: { label: 'Shell session open', tone: 'success' },
  closing: { label: 'Ending session', tone: 'warning' },
  closed: { label: 'Session ended', tone: 'neutral' },
  failed: { label: 'Session failed', tone: 'error' },
}
const uncertain = (error: unknown) => !(error instanceof ApiError) || error.status >= 500 || error.status === 429 || error.status === 408

type Props = { project_id: string, open: boolean, onHide: () => void }

const HEIGHT = { initial: 340, min: 160 }
const subscribeResize = (cb: () => void) => { window.addEventListener('resize', cb); return () => window.removeEventListener('resize', cb) }
const useWindowHeight = () => useSyncExternalStore(subscribeResize, () => window.innerHeight, () => 900)

export function TerminalPanel({ project_id, open, onHide }: Props) {
  const client = useQueryClient()
  const caps = useCapabilities(), project = useProject(project_id)
  const supported = (caps.data?.features as { terminal?: boolean } | undefined)?.terminal === true
  const archived = project.data?.status === 'archived'
  // Leave room for the header and some of the page above the terminal.
  const maxHeight = Math.max(HEIGHT.min, useWindowHeight() - 180)
  const [height, setHeight, resetHeight] = usePanelSize('stellaris.terminalHeight', HEIGHT.initial, HEIGHT.min, maxHeight)
  const current = useCurrentTerminal(project_id, supported)
  const session = current.data ?? null
  const active = isActiveTerminal(session)

  // Stable keys: a retry after an uncertain failure replays the same command.
  const startKey = useRef<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<unknown>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const closeKey = useRef<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [closing, setClosing] = useState(false)
  const [closeError, setCloseError] = useState<unknown>(null)

  async function start() {
    startKey.current ??= newCommandKey()
    setStarting(true); setStartError(null); setNotice(null)
    try {
      const result = await terminalApi.start(project_id, DEFAULT_SIZE, startKey.current)
      startKey.current = null
      setCurrentTerminal(client, result.data)
    } catch (error) {
      if (errorCode(error) === 'TERMINAL_ACTIVE') {
        startKey.current = null
        setNotice('This project already has an active session. It was attached instead of starting another.')
        await client.refetchQueries({ queryKey: terminalKey(project_id) })
      } else {
        if (!uncertain(error)) startKey.current = null
        setStartError(error)
      }
    } finally { setStarting(false) }
  }

  async function end() {
    if (!session) return
    closeKey.current ??= newCommandKey()
    setClosing(true); setCloseError(null)
    try {
      const result = await terminalApi.close(project_id, session.id, closeKey.current)
      closeKey.current = null
      setCurrentTerminal(client, result.data)
      setConfirming(false)
    } catch (error) {
      if (!uncertain(error)) closeKey.current = null
      setCloseError(error)
    } finally { setClosing(false) }
  }

  const status = session ? STATUS[session.status] : null
  return (
    <section id={TERMINAL_PANEL_ID} className={styles.panel} aria-label="Terminal" hidden={!open} style={{ '--terminal-height': `${height}px` } as CSSProperties}>
      <ResizeHandle label="Resize terminal" axis="y" direction={-1} value={height} min={HEIGHT.min} max={maxHeight}
        onChange={setHeight} onReset={resetHeight} className={styles.resize} />
      <div className={styles.bar}>
        <h2 className={styles.title}>Terminal</h2>
        {status && <StatusBadge tone={status.tone}>{status.label}</StatusBadge>}
        <div className={styles.actions}>
          {supported && !active && (
            <Button variant="primary" pending={starting} disabled={archived || current.isLoading || !!current.error} onClick={() => void start()}>
              {startError != null && uncertain(startError) ? 'Retry start' : session ? 'Start new session' : 'Start session'}
            </Button>
          )}
          {supported && active && (
            <Button variant="danger" disabled={session?.status === 'closing'}
              onClick={() => { setCloseError(null); setConfirming(true) }}>End session</Button>
          )}
          {session && <a className={styles.download} href={terminalApi.transcriptUrl(project_id, session.id)} download>Download transcript</a>}
          <IconButton id={`${TERMINAL_PANEL_ID}-hide`} label="Hide terminal" icon={<CloseIcon />} onClick={onHide} />
        </div>
      </div>
      <p className={styles.note}>
        Separate terminal workspace: no research agent scratch, no published evidence, no network and no model provider access.
        Files persist only in this project&apos;s terminal workspace. Transcripts are raw output, not research artifacts.
        Shift+Escape leaves the terminal.
      </p>
      {archived && <p className={styles.note} role="note">This project is archived. Starting sessions and sending input are disabled; you can still read or end sessions.</p>}
      {notice && <p className={styles.note} role="status">{notice}</p>}
      {startError != null && <ErrorNotice {...describeError(startError, 'The session was not started')} />}
      {session?.error && !active && <p className={styles.note}>{session.error.message}</p>}
      <div className={styles.body}>
        {caps.isLoading ? <Skeleton height="6rem" />
          : !supported ? <EmptyState title="Terminal unavailable">This backend does not report an available terminal runtime.</EmptyState>
          : current.error ? <ErrorNotice {...describeError(current.error, 'Sessions could not be loaded')}
              action={<Button onClick={() => void current.refetch()}>Reload sessions</Button>} />
          : current.isLoading ? <Skeleton height="6rem" />
          : session ? <TerminalView key={session.id} project_id={project_id} session={session} archived={archived} visible={open}
              onEscape={() => document.getElementById(`${TERMINAL_PANEL_ID}-hide`)?.focus()} />
          : <EmptyState title="No terminal session">Start a session to open a shell. Nothing starts automatically.</EmptyState>}
      </div>
      <Dialog open={confirming} onClose={() => setConfirming(false)} title="End terminal session?">
        <p className="prose">Ending stops the shell and removes its container. Files in the terminal workspace are kept, and the transcript stays downloadable.</p>
        {closeError != null && <ErrorNotice {...describeError(closeError, 'The session was not ended')} />}
        <div className={styles.dialogActions}>
          <Button variant="danger" pending={closing} onClick={() => void end()}>{closeError != null && uncertain(closeError) ? 'Retry end session' : 'End session'}</Button>
          <Button onClick={() => setConfirming(false)}>Cancel</Button>
        </div>
      </Dialog>
    </section>
  )
}
