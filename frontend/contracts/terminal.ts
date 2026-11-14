// Wire schemas from docs/terminal-contract.md. The terminal is an optional, user-started shell over a
// separate terminal workspace; it is not the research agent workspace or a scientific execution environment.
import type { ID, Timestamp } from './api'

export type TerminalStatus = 'starting' | 'running' | 'closing' | 'closed' | 'failed'
export const ACTIVE_TERMINAL_STATUSES: readonly TerminalStatus[] = ['starting', 'running', 'closing']

export type TerminalSession = {
  id: ID,
  project_id: ID,
  status: TerminalStatus,
  rows: number,
  cols: number,
  created_at: Timestamp,
  finished_at: Timestamp | null,
  error: { code: string, message: string } | null,
  output_bytes: number,
  last_output_sequence: number,
  last_input_sequence: number,
  /** Currently always null: transcripts are not artifacts. */
  transcript_artifact_id: null,
}

export type TerminalOutputChunk = { sequence: number, occurred_at: Timestamp, data_base64: string }

export type TerminalSize = { rows: number, cols: number }

/** Additive capability fields reported by the backend (`features.terminal` and top-level `terminal`). */
export type TerminalCapabilities = {
  network_access: false,
  max_output_bytes: number,
  max_input_bytes: number,
  max_active_per_project: number,
  max_duration_s: number,
}

export type TerminalEventPayloads = {
  'terminal.updated': { terminal: TerminalSession },
  'terminal.output': { terminal_id: ID, sequence: number, data_base64: string },
}

export const TERMINAL_LIMITS = {
  min_rows: 2, max_rows: 200, min_cols: 2, max_cols: 500,
  max_input_bytes: 16 * 1024,
} as const
