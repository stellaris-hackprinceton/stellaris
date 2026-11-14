'use client'
// Loaded only through next/dynamic with ssr: false (see TerminalPanel); xterm needs browser APIs.
import '@xterm/xterm/css/xterm.css'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { TerminalSession, TerminalSize } from '@/contracts/terminal'
import { Button, ErrorNotice, describeError } from '@/components/ui'
import { clampSize, subscribeTerminal, terminalApi } from '@/lib/terminal'
import { TerminalController, type InputState } from './controller'
import styles from './terminal.module.css'

type Props = {
  project_id: string,
  session: TerminalSession,
  archived: boolean,
  visible: boolean,
  /** Shift+Escape leaves the terminal, which otherwise captures Tab. */
  onEscape: () => void,
}

export function TerminalView({ project_id, session, archived, visible, onEscape }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const term = useRef<Terminal | null>(null)
  const fit = useRef<FitAddon | null>(null)
  const controller = useRef<TerminalController | null>(null)
  const visibleRef = useRef(visible), escapeRef = useRef(onEscape), sessionRef = useRef(session), archivedRef = useRef(archived)
  const lastSize = useRef<TerminalSize>({ rows: session.rows, cols: session.cols })
  const resizeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const [input, setInput] = useState<InputState>({ kind: 'disabled', message: 'Loading session output…' })
  const [outputError, setOutputError] = useState<unknown | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => { escapeRef.current = onEscape }, [onEscape])

  // Fit locally, then resize the remote PTY only while visible, running and changed.
  const scheduleResize = useCallback(() => {
    if (resizeTimer.current) clearTimeout(resizeTimer.current)
    resizeTimer.current = setTimeout(() => {
      const t = term.current, el = host.current
      if (!t || !fit.current || !el || !visibleRef.current || el.clientWidth === 0 || el.clientHeight === 0) return
      fit.current.fit()
      const size = clampSize({ rows: t.rows, cols: t.cols }), s = sessionRef.current
      if (s.status !== 'running' || archivedRef.current) return
      if (size.rows === lastSize.current.rows && size.cols === lastSize.current.cols) return
      lastSize.current = size
      terminalApi.resize(project_id, s.id, size).catch(() => { lastSize.current = { rows: 0, cols: 0 } })
    }, 150)
  }, [project_id])

  useEffect(() => {
    const el = host.current
    if (!el) return
    const t = new Terminal({
      scrollback: 5000, cursorBlink: true, fontSize: 13,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
      theme: { background: '#0f141a', foreground: '#e6edf3' },
    })
    const f = new FitAddon()
    t.loadAddon(f)
    t.open(el)
    term.current = t; fit.current = f
    if (el.clientWidth > 0) f.fit()
    t.attachCustomKeyEventHandler(event => {
      if (event.type === 'keydown' && event.key === 'Escape' && event.shiftKey) { escapeRef.current(); return false }
      return true
    })
    const c = new TerminalController(project_id, sessionRef.current, { write: bytes => t.write(bytes) }, setInput, setOutputError, setNotice)
    c.setArchived(archivedRef.current)
    controller.current = c
    // Ignore terminal-generated replies (e.g. device queries) while historical output is replayed.
    let replaying = true
    const data = t.onData(value => { if (!replaying) { setNotice(null); c.type(value) } })
    const unsubscribe = subscribeTerminal(project_id, signal => c.handle(signal))
    void c.start().then(() => t.write(new Uint8Array(0), () => { replaying = false }))
    const observer = new ResizeObserver(() => scheduleResize())
    observer.observe(el)
    return () => {
      observer.disconnect(); unsubscribe(); data.dispose(); c.dispose(); t.dispose()
      if (resizeTimer.current) clearTimeout(resizeTimer.current)
      term.current = null; fit.current = null; controller.current = null
    }
    // One terminal instance per session; the parent keys this component by session id.
  }, [project_id, scheduleResize])

  useEffect(() => {
    sessionRef.current = session; archivedRef.current = archived
    controller.current?.setArchived(archived)
    controller.current?.setSession(session)
    if (term.current) term.current.options.disableStdin = archived || session.status !== 'running'
    scheduleResize()
  }, [session, archived, scheduleResize])

  useEffect(() => {
    visibleRef.current = visible
    if (visible) { scheduleResize(); term.current?.focus() }
  }, [visible, scheduleResize])

  return (
    <div className={styles.viewport}>
      <div ref={host} className={styles.xterm} />
      {outputError != null && (
        <ErrorNotice {...describeError(outputError, 'Session output could not be loaded')}
          action={<Button onClick={() => void controller.current?.catchUp()}>Reload output</Button>} />
      )}
      <div className={styles.inputStatus} role="status" aria-live="polite">
        {input.kind === 'sending' ? <span>Sending input…</span>
          : input.kind === 'ready' ? <span className="sr-only">Input ready</span>
          : <span>{input.message}</span>}
        {input.kind === 'uncertain' && <Button onClick={() => controller.current?.retry()}>Retry same input</Button>}
        {input.kind === 'blocked' && <Button onClick={() => void controller.current?.resume()}>Resume input</Button>}
        {notice && <span>{notice}</span>}
      </div>
    </div>
  )
}
