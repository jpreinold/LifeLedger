import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiRequest } from './apiClient'

vi.mock('../auth/session', () => ({
  getAuthorizationHeaders: vi.fn(async () => ({ Authorization: 'Bearer test-token' })),
}))

describe('apiRequest', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('normalizes typed validation errors and preserves safe request IDs', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Check the protected detail.' }),
      { status: 422, headers: { 'Content-Type': 'application/json', 'x-request-id': 'request-123' } },
    ))

    await expect(apiRequest('/records/1/protected', { method: 'PATCH', body: '{}' })).rejects.toMatchObject({
      name: 'ApiError',
      category: 'validation',
      status: 422,
      requestId: 'request-123',
      retryable: false,
      message: 'Check the protected detail.',
    })
  })

  it('does not expose raw server error detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Traceback: internal private implementation' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } },
    ))

    const error: unknown = await apiRequest('/records').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    if (!(error instanceof ApiError)) throw new Error('Expected ApiError')
    expect(error).toMatchObject({ category: 'server', retryable: true })
    expect(error.message).toBe('LifeLedger could not complete this request. Try again.')
    expect(error.message).not.toContain('Traceback')
  })

  it('normalizes typed account errors without exposing backend payloads', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
      JSON.stringify({ detail: { code: 'deletion_in_progress', message: 'New changes are unavailable while account deletion is in progress.' }, private_debug: 'never show' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    ))

    await expect(apiRequest('/records', { method: 'POST', body: '{}' })).rejects.toMatchObject({
      category: 'conflict',
      code: 'deletion_in_progress',
      message: 'New changes are unavailable while account deletion is in progress.',
      retryable: false,
    })
  })

  it('normalizes network failures and passes authorization, no-store, and abort signals', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('network down'))
    await expect(apiRequest('/search')).rejects.toMatchObject({ category: 'network', status: null, retryable: true })

    const controller = new AbortController()
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await expect(apiRequest<void>('/records/1', { method: 'DELETE', signal: controller.signal })).resolves.toBeUndefined()
    expect(fetchMock).toHaveBeenLastCalledWith(
      'http://localhost:8000/records/1',
      expect.objectContaining({
        cache: 'no-store',
        method: 'DELETE',
        signal: controller.signal,
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      }),
    )
  })
})
