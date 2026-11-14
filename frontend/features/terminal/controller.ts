// Output replay and input sequencing for one terminal session. No xterm dependency.
import type { TerminalSession } from '@/contracts/terminal'
import { TERMINAL_LIMITS } from '@/contracts/terminal'
import { ApiError } from '@/lib/api/http'
import { decodeBase64, encodeBase64, terminalApi, type TerminalSignal } from '@/lib/terminal'

export type InputState =
  | { kind: 'ready' }
  | { kind: 'sending' }
  /** Acceptance unknown: only an explicit retry of the same sequence and bytes is allowed. */
  | { kind: 'uncertain', message: string }
  /** Definitive failure: pending input was discarded; resume re-reads the session's sequence. */
  | { kind: 'blocked', message: string }
  | { kind: 'disabled', message: string }

type Sink = { write: (bytes: Uint8Array) => void }
type Inflight = { sequence: number, bytes: Uint8Array, base64: string, attempts: number }
const MAX_PENDING = 256 * 1024
const encoder = new TextEncoder()

export class TerminalController {
  private written = 0
  private fetching = false
  private refetch = false
  private nextSequence: number
  private pending: Uint8Array[] = []
  private pendingBytes = 0
  private inflight: Inflight | null = null
  private lock: { kind: 'uncertain' | 'blocked', message: string } | null = null
  private archived = false
  private disposed = false
  private retryTimer: ReturnType<typeof setTimeout> | undefined
  private readonly abort = new AbortController()

  constructor(
    private readonly project_id: string,
    private session: TerminalSession,
    private readonly sink: Sink,
    private readonly onInput: (state: InputState) => void,
    private readonly onOutputError: (error: unknown | null) => void,
    private readonly onNotice: (message: string) => void,
  ) {
    this.nextSequence = session.last_input_sequence + 1
  }

  get inputState(): InputState {
    if (this.lock) return this.lock
    if (this.archived) return { kind: 'disabled', message: 'This project is archived. Terminal input is disabled.' }
    if (this.session.status !== 'running') return { kind: 'disabled', message: this.session.status === 'starting' ? 'Waiting for the shell to start. Input is disabled until it is running.' : 'This shell session is not running. Input is disabled.' }
    return this.inflight ? { kind: 'sending' } : { kind: 'ready' }
  }
  private publish() { if (!this.disposed) this.onInput(this.inputState) }

  /** Replays persisted output from the start; resolves once the initial replay is written. */
  start() { this.publish(); return this.catchUp() }

  dispose() {
    this.disposed = true
    this.abort.abort()
    if (this.retryTimer) clearTimeout(this.retryTimer)
  }

  setArchived(archived: boolean) { this.archived = archived; this.publish() }

  setSession(session: TerminalSession) {
    if (session.id !== this.session.id) return
    this.session = session
    // Another tab's accepted input advances the sequence; only adopt it when nothing is in flight.
    if (!this.inflight && session.last_input_sequence >= this.nextSequence) this.nextSequence = session.last_input_sequence + 1
    if (session.status !== 'running' && !this.inflight) this.discardPending()
    if (session.last_output_sequence > this.written) void this.catchUp()
    this.publish()
  }

  handle(signal: TerminalSignal) {
    if (this.disposed) return
    if (signal.type === 'resync') { void this.catchUp(); return }
    if (signal.type === 'updated') { this.setSession(signal.terminal); return }
    if (signal.terminal_id !== this.session.id || signal.sequence <= this.written) return
    if (signal.sequence === this.written + 1 && !this.fetching) {
      this.sink.write(decodeBase64(signal.data_base64)); this.written = signal.sequence
      return
    }
    void this.catchUp() // Gap: fetch persisted output instead of buffering out-of-order chunks.
  }

  async catchUp(): Promise<void> {
    if (this.fetching) { this.refetch = true; return }
    this.fetching = true
    try {
      do {
        this.refetch = false
        const after = this.written
        let cursor: string | null = null
        do {
          const page = await terminalApi.output(this.project_id, this.session.id, after, cursor, this.abort.signal)
          if (this.disposed) return
          for (const chunk of [...page.data.items].sort((a, b) => a.sequence - b.sequence)) {
            if (chunk.sequence <= this.written) continue
            this.sink.write(decodeBase64(chunk.data_base64)); this.written = chunk.sequence
          }
          cursor = page.data.next_cursor
        } while (cursor && !this.disposed)
      } while (this.refetch && !this.disposed)
      this.onOutputError(null)
    } catch (error) {
      if (!this.disposed) this.onOutputError(error)
    } finally { this.fetching = false }
  }

  type(data: string) {
    if (this.disposed || !data) return
    const state = this.inputState
    if (state.kind !== 'ready' && state.kind !== 'sending') { this.onNotice(`Input was not sent: ${state.message}`); return }
    const bytes = encoder.encode(data)
    if (this.pendingBytes + bytes.length > MAX_PENDING) { this.onNotice('Input was not sent: too much input is waiting for delivery.'); return }
    this.pending.push(bytes); this.pendingBytes += bytes.length
    this.pump()
  }

  /** Explicit retry of the same uncertain sequence and bytes. */
  retry() {
    if (this.lock?.kind !== 'uncertain' || !this.inflight) return
    this.lock = null; this.inflight.attempts = 0
    void this.send()
  }

  /** Re-reads the session after a definitive failure and continues from its recorded sequence. */
  async resume() {
    if (this.lock?.kind !== 'blocked') return
    try {
      const fresh = await terminalApi.get(this.project_id, this.session.id, this.abort.signal)
      if (this.disposed) return
      this.session = fresh.data
      this.nextSequence = fresh.data.last_input_sequence + 1
      this.lock = null
      this.publish()
    } catch { this.onNotice('Could not refresh the session. Try again.') }
  }

  private discardPending() { this.pending = []; this.pendingBytes = 0 }

  private pump() {
    if (this.inflight || this.lock || this.disposed || !this.pendingBytes) { this.publish(); return }
    const size = Math.min(TERMINAL_LIMITS.max_input_bytes, this.pendingBytes)
    const out = new Uint8Array(size)
    let offset = 0
    while (offset < size) {
      const head = this.pending[0], take = Math.min(head.length, size - offset)
      out.set(head.subarray(0, take), offset); offset += take
      if (take === head.length) this.pending.shift(); else this.pending[0] = head.subarray(take)
    }
    this.pendingBytes -= size
    this.inflight = { sequence: this.nextSequence, bytes: out, base64: encodeBase64(out), attempts: 0 }
    void this.send()
  }

  private async send() {
    const f = this.inflight
    if (!f || this.disposed) return
    this.publish()
    try {
      await terminalApi.input(this.project_id, this.session.id, f.sequence, f.base64)
      if (this.disposed) return
      this.inflight = null; this.nextSequence = f.sequence + 1
      this.pump()
    } catch (error) {
      if (this.disposed) return
      const status = error instanceof ApiError ? error.status : 0
      if (!(error instanceof ApiError) || status >= 500 || status === 429 || status === 408) {
        f.attempts++
        if (f.attempts < 3) { this.retryTimer = setTimeout(() => void this.send(), 500 * 2 ** f.attempts); return }
        this.lock = { kind: 'uncertain', message: 'Delivery of the last input could not be confirmed. Retry sends the same bytes with the same sequence; they are never resent under a new sequence.' }
        this.publish(); return
      }
      this.inflight = null
      this.discardPending()
      const code = error.code
      if (code === 'TERMINAL_INPUT_UNKNOWN') {
        this.nextSequence = f.sequence + 1
        this.lock = { kind: 'blocked', message: 'The backend recorded this input but could not confirm delivery to the shell. It will not be resent. Pending input was discarded.' }
      } else if (code === 'INPUT_SEQUENCE_GAP' || code === 'INPUT_CONFLICT') {
        this.lock = { kind: 'blocked', message: 'Input was sent to this session from another tab or window. Your pending input was not sent.' }
      } else if (code === 'TERMINAL_NOT_RUNNING') {
        this.session = { ...this.session, status: this.session.status === 'running' ? 'closing' : this.session.status }
      } else {
        this.lock = { kind: 'blocked', message: `Input was rejected (${code}): ${error.message} Pending input was discarded.` }
      }
      this.publish()
    }
  }
}
