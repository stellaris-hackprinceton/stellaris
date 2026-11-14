import { test, beforeEach, afterEach, mock } from 'node:test'
import assert from 'node:assert/strict'
import { ApiError, request, setCsrfToken } from './http.ts'

beforeEach(() => setCsrfToken(null))
afterEach(() => mock.restoreAll())

test('an unresolved session cannot submit writes', async () => {
  const fetch = mock.method(globalThis, 'fetch', async () => { throw new Error('Unexpected request') })
  await assert.rejects(request('/projects', { method: 'POST', body: {}, command: { idempotency_key: 'unresolved' } }), error => error instanceof ApiError && error.code === 'CSRF_REQUIRED')
  assert.equal(fetch.mock.callCount(), 0)
})

test('an empty token alone does not enable development writes', async () => {
  setCsrfToken('')
  await assert.rejects(request('/projects', { method: 'POST', body: {}, command: { idempotency_key: 'empty' } }), { code: 'CSRF_REQUIRED' })
})

test('explicit development_none accepts the backend empty-token session', async () => {
  setCsrfToken('', 'development_none')
  const fetch = mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.headers.get('Idempotency-Key'), 'stable-command')
    assert.equal(options.headers.has('X-CSRF-Token'), false)
    assert.equal(options.credentials, 'same-origin')
    return Response.json({ id: 'created' }, { status: 201, headers: { ETag: '"1"', 'X-Request-ID': 'request-id' } })
  })
  const result = await request('/projects', { method: 'POST', body: { name: 'Development project' }, command: { idempotency_key: 'stable-command' } })
  assert.equal(result.data.id, 'created')
  assert.equal(result.etag, '"1"')
  assert.equal(result.request_id, 'request-id')
  assert.equal(fetch.mock.callCount(), 1)
})

test('authenticated PATCH preserves CSRF and the loaded ETag', async () => {
  setCsrfToken('actual-token')
  mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.headers.get('X-CSRF-Token'), 'actual-token')
    assert.equal(options.headers.get('If-Match'), '"4"')
    return Response.json({ revision: 5 })
  })
  await request('/projects/project-id', { method: 'PATCH', body: { name: 'Changed' }, edit: { etag: '"4"' } })
})

test('DELETE preserves the session, optional ETag, and empty 204 response', async () => {
  setCsrfToken('actual-token')
  mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.method, 'DELETE')
    assert.equal(options.headers.get('X-CSRF-Token'), 'actual-token')
    assert.equal(options.headers.get('If-Match'), '"7"')
    return new Response(null, { status: 204, headers: { 'X-Request-ID': 'delete-request' } })
  })
  const result = await request('/projects/project-id/files/file-id', { method: 'DELETE', deleteOptions: { etag: '"7"' } })
  assert.equal(result.data, undefined)
  assert.equal(result.request_id, 'delete-request')
})

test('clearing the session removes development write permission', async () => {
  setCsrfToken('', 'development_none')
  setCsrfToken(null)
  await assert.rejects(request('/projects', { method: 'POST', body: {}, command: { idempotency_key: 'cleared' } }), { code: 'CSRF_REQUIRED' })
})

test('development mode still requires a stable command key', async () => {
  setCsrfToken('', 'development_none')
  await assert.rejects(request('/projects', { method: 'POST', body: {} }), /stable idempotency_key/)
})

test('structured server errors remain readable by merged feature handlers', async () => {
  mock.method(globalThis, 'fetch', async () => Response.json({ error: { code: 'PROJECT_ARCHIVED', message: 'Restore the project.', retryable: false, request_id: 'problem-id', details: {} } }, { status: 409 }))
  await assert.rejects(request('/projects/project-id'), error => {
    assert.equal(error.code, 'PROJECT_ARCHIVED')
    assert.equal(error.request_id, 'problem-id')
    assert.equal(error.status, 409)
    assert.equal(error.retryable, false)
    return true
  })
})
