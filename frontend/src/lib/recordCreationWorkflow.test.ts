import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/apiClient'
import type { LinkCreateRequest } from '../types/linkedItem'
import type { ProtectedRecordStatus } from '../types/record'
import { runRecordSetupAttempt, type RecordSetupProgress } from './recordCreationWorkflow'

const protectedStatus: ProtectedRecordStatus = {
  has_protected_data: true,
  protected_field_names: ['document_number'],
  protected_encryption_version: 1,
  protected_updated_at: '2026-07-17T12:00:00.000Z',
}

function progress(): RecordSetupProgress {
  return { protectedSaved: false, successfulFiles: new Set(), successfulLinks: new Set() }
}

describe('record creation child setup recovery', () => {
  it('retries only failed protected, document, and link operations after a network interruption', async () => {
    const state = progress()
    const documentA = new File(['a'], 'a.pdf', { type: 'application/pdf', lastModified: 1 })
    const documentB = new File(['b'], 'b.pdf', { type: 'application/pdf', lastModified: 2 })
    const linkA: LinkCreateRequest = { target_type: 'record', target_id: 'record-a' }
    const linkB: LinkCreateRequest = { target_type: 'reminder', target_id: 'reminder-b' }
    const saveProtected = vi.fn()
      .mockRejectedValueOnce(new TypeError('network unavailable'))
      .mockResolvedValueOnce(protectedStatus)
    const uploadFile = vi.fn(async (_recordId: string, file: File) => {
      if (file.name === 'b.pdf' && uploadFile.mock.calls.filter((call) => call[1].name === 'b.pdf').length === 1) {
        throw new TypeError('network unavailable')
      }
    })
    const createLink = vi.fn(async (_recordId: string, link: LinkCreateRequest) => {
      if (link.target_id === 'reminder-b' && createLink.mock.calls.filter((call) => call[1].target_id === 'reminder-b').length === 1) {
        throw new TypeError('network unavailable')
      }
    })
    const dependencies = { saveProtected, uploadFile, createLink }

    const first = await runRecordSetupAttempt(
      'record-created',
      { document_number: 'P1234567' },
      [documentA, documentB],
      [linkA, linkB],
      state,
      dependencies,
    )
    expect(first).toMatchObject({ protectedFailed: true, failedFiles: ['b.pdf'], linkFailures: 1 })

    const second = await runRecordSetupAttempt(
      'record-created',
      { document_number: 'P1234567' },
      [documentA, documentB],
      [linkA, linkB],
      state,
      dependencies,
    )
    expect(second).toMatchObject({ protectedFailed: false, failedFiles: [], linkFailures: 0, protectedStatus })
    expect(saveProtected).toHaveBeenCalledTimes(2)
    expect(uploadFile.mock.calls.filter((call) => call[1].name === 'a.pdf')).toHaveLength(1)
    expect(uploadFile.mock.calls.filter((call) => call[1].name === 'b.pdf')).toHaveLength(2)
    expect(createLink.mock.calls.filter((call) => call[1].target_id === 'record-a')).toHaveLength(1)
    expect(createLink.mock.calls.filter((call) => call[1].target_id === 'reminder-b')).toHaveLength(2)
  })

  it('treats a duplicate link conflict as an idempotent success', async () => {
    const state = progress()
    const createLink = vi.fn().mockRejectedValue(new ApiError('Already linked.', { category: 'conflict', status: 409 }))
    const dependencies = {
      saveProtected: vi.fn().mockResolvedValue(protectedStatus),
      uploadFile: vi.fn(),
      createLink,
    }
    const link: LinkCreateRequest = { target_type: 'record', target_id: 'already-linked' }

    const first = await runRecordSetupAttempt('record-created', {}, [], [link], state, dependencies)
    const second = await runRecordSetupAttempt('record-created', {}, [], [link], state, dependencies)

    expect(first.linkFailures).toBe(0)
    expect(second.linkFailures).toBe(0)
    expect(createLink).toHaveBeenCalledTimes(1)
  })
})
