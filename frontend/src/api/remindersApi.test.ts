import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from './apiClient'
import { remindersApi } from './remindersApi'

vi.mock('../auth/session', () => ({
  getAuthorizationHeaders: vi.fn(async () => ({ Authorization: 'Bearer test-token' })),
}))

describe('remindersApi.remove', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('treats an already absent reminder as a successful idempotent delete', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(
      JSON.stringify({ detail: 'Reminder not found' }),
      { status: 404, headers: { 'Content-Type': 'application/json' } },
    ))

    await expect(remindersApi.remove('reminder-1')).resolves.toBeUndefined()
  })

  it('confirms a retryable delete failure when the reminder is already gone', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new TypeError('response lost'))
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ detail: 'Reminder not found' }),
        { status: 404, headers: { 'Content-Type': 'application/json' } },
      ))

    await expect(remindersApi.remove('reminder-2')).resolves.toBeUndefined()
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/reminders/reminder-2',
      expect.objectContaining({ cache: 'no-store' }),
    )
  })

  it('preserves the original delete error when the reminder still exists', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new TypeError('response lost'))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'reminder-3' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }))

    const error: unknown = await remindersApi.remove('reminder-3').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ category: 'network', retryable: true })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('does not mask a non-retryable delete failure', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(
      JSON.stringify({ detail: 'Not permitted' }),
      { status: 403, headers: { 'Content-Type': 'application/json' } },
    ))

    await expect(remindersApi.remove('reminder-4')).rejects.toMatchObject({ category: 'forbidden' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
