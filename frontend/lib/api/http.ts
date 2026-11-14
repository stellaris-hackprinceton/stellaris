import type { ApiResult, CommandOptions, EditOptions, UploadProgress } from '@/contracts/requests'

export type ErrorEnvelope = { code: string, message: string, request_id?: string, retryable: boolean, details: Record<string, unknown> }
export class ApiError extends Error {
  get code() { return this.error.code }
  get request_id() { return this.error.request_id }
  get details() { return this.error.details }
  get retryable() { return this.error.retryable }
  constructor(public status: number, public error: ErrorEnvelope, public retry_after: string | null = null) {
    super(error.message)
    this.name = 'ApiError'
  }
}
let csrf: string | null = null
let developmentSession = false
export const setCsrfToken = (token: string | null, auth_mode?: 'development_none') => {
  csrf = token
  developmentSession = token !== null && auth_mode === 'development_none'
}
export const isAuthError = (error: unknown) => error instanceof ApiError && error.status === 401
export function reportAuthFailure() { if (typeof window !== 'undefined') window.dispatchEvent(new Event('stellaris:auth-expired')) }
export const commandKey = () => crypto.randomUUID()
export function apiUrl(path: string) { return `/api/v1${path}` }
export const encode = (value: string) => encodeURIComponent(value)
export async function responseError(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null)
  const candidate = body && typeof body === 'object' && 'error' in body ? body.error : null
  const e = candidate && typeof candidate === 'object' ? candidate as Partial<ErrorEnvelope> : {}
  const error = new ApiError(response.status, {
    code: e.code ?? (response.status === 401 ? 'AUTH_REQUIRED' : 'SERVICE_UNAVAILABLE'),
    message: e.message ?? `The service returned HTTP ${response.status}.`,
    retryable: e.retryable ?? response.status >= 500,
    request_id: e.request_id ?? response.headers.get('X-Request-ID') ?? undefined,
    details: e.details ?? {},
  }, response.headers.get('Retry-After'))
  if (response.status === 401) reportAuthFailure()
  return error
}
export async function request<T>(path: string, options: {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', body?: unknown, signal?: AbortSignal,
  command?: CommandOptions, edit?: EditOptions, deleteOptions?: EditOptions | { signal?: AbortSignal }
} = {}): Promise<ApiResult<T>> {
  const method = options.method ?? 'GET'
  const headers = new Headers({ Accept: 'application/json' })
  if (method !== 'GET') {
    if (!csrf && !developmentSession) throw new ApiError(403, { code: 'CSRF_REQUIRED', message: 'Resolve your session before submitting changes.', retryable: false, details: {} })
    if (csrf) headers.set('X-CSRF-Token', csrf)
    headers.set('Content-Type', 'application/json')
  }
  if (method === 'POST') {
    if (!options.command?.idempotency_key) throw new Error('A stable idempotency_key is required.')
    headers.set('Idempotency-Key', options.command.idempotency_key)
  }
  if (method === 'PATCH') {
    if (!options.edit?.etag) throw new Error('A loaded ETag is required.')
    headers.set('If-Match', options.edit.etag)
  }
  if (method === 'DELETE' && options.deleteOptions && 'etag' in options.deleteOptions) headers.set('If-Match', options.deleteOptions.etag)
  const response = await fetch(apiUrl(path), {
    method, headers, credentials: 'same-origin', cache: 'no-store',
    signal: options.signal ?? options.command?.signal ?? options.edit?.signal ?? options.deleteOptions?.signal,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!response.ok) throw await responseError(response)
  if (response.status === 204) return { data: undefined as T, etag: response.headers.get('ETag'), request_id: response.headers.get('X-Request-ID') }
  return { data: await response.json() as T, etag: response.headers.get('ETag'), request_id: response.headers.get('X-Request-ID') }
}
export async function readText(path: string, signal?: AbortSignal) {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', signal, headers: { Range: 'bytes=0-262143' } })
  if (!response.ok) throw await responseError(response)
  if (!response.body) return { text: '', truncated: false }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let bytes = 0, text = '', overflow = false
  try {
    while (true) {
      const chunk = await reader.read()
      if (chunk.done) break
      const remaining = 262144 - bytes
      text += decoder.decode(chunk.value.subarray(0, remaining), { stream: true })
      bytes += Math.min(remaining, chunk.value.byteLength)
      if (bytes >= 262144) { overflow = true; break }
    }
    text += decoder.decode()
  } finally { await reader.cancel() }
  const rangeTotal = response.headers.get('Content-Range')?.match(/\/(\d+)$/)?.[1]
  const reportedTotal = rangeTotal ? Number(rangeTotal) : Number(response.headers.get('Content-Length') ?? 0)
  return { text, truncated: reportedTotal > bytes || (overflow && !reportedTotal) }
}
export function putBytes(path: string, blob: Blob, options: { signal?: AbortSignal, on_progress?: (progress: UploadProgress) => void } = {}): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!csrf && !developmentSession) { reject(new Error('Resolve your session before uploading.')); return }
    const xhr = new XMLHttpRequest()
    const abort = () => xhr.abort()
    const clean = () => options.signal?.removeEventListener('abort', abort)
    xhr.open('PUT', apiUrl(path))
    xhr.withCredentials = true
    if (csrf) xhr.setRequestHeader('X-CSRF-Token', csrf)
    xhr.setRequestHeader('Content-Type', blob.type || 'application/octet-stream')
    xhr.upload.onprogress = e => options.on_progress?.({ loaded_bytes: e.loaded, total_bytes: e.lengthComputable ? e.total : null })
    xhr.onload = async () => {
      clean()
      if (xhr.status >= 200 && xhr.status < 300) { resolve(); return }
      reject(await responseError(new Response(xhr.responseText, { status: xhr.status, headers: { 'X-Request-ID': xhr.getResponseHeader('X-Request-ID') ?? '' } })))
    }
    xhr.onerror = () => { clean(); reject(new Error('Upload connection failed. Retry with the same file.')) }
    xhr.onabort = () => { clean(); reject(new DOMException('Upload cancelled', 'AbortError')) }
    if (options.signal?.aborted) { reject(new DOMException('Upload cancelled', 'AbortError')); return }
    options.signal?.addEventListener('abort', abort, { once: true })
    xhr.send(blob)
  })
}
