import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { recordsApi } from '../api/recordsApi'
import type { RecordAttachment } from '../types/record'
import { RecordDocumentsPanel } from './RecordDocumentsPanel'

vi.mock('../api/recordsApi', () => ({
  recordsApi: {
    listAttachments: vi.fn(),
    createAttachmentPreviewUrl: vi.fn(),
    createAttachmentDownloadUrl: vi.fn(),
    createAttachmentUploadIntent: vi.fn(),
    uploadAttachmentFile: vi.fn(),
    completeAttachmentUpload: vi.fn(),
    deleteAttachment: vi.fn(),
  },
}))

const api = vi.mocked(recordsApi)

function attachment(id: string, status: RecordAttachment['status'] = 'available'): RecordAttachment {
  return {
    attachment_id: id,
    record_id: 'record-1',
    display_name: 'duplicate-name.png',
    content_type: 'image/png',
    size_bytes: 1024,
    status,
    scan_result: status === 'available' ? 'no_threats_found' : 'pending',
    created_at: '2026-07-17T12:00:00.000Z',
    uploaded_at: '2026-07-17T12:01:00.000Z',
    scan_completed_at: status === 'available' ? '2026-07-17T12:02:00.000Z' : null,
    available_at: status === 'available' ? '2026-07-17T12:02:00.000Z' : null,
    deleted_at: null,
  }
}

describe('RecordDocumentsPanel exact navigation', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.createAttachmentPreviewUrl.mockImplementation(async (_recordId, attachmentId) => ({
      url: `https://example.test/${attachmentId}`,
      expires_at: '2026-07-17T12:05:00.000Z',
    }))
  })

  it('disambiguates duplicate filenames by ID and preserves the record panel after preview', async () => {
    const user = userEvent.setup()
    api.listAttachments.mockResolvedValue([attachment('document-a'), attachment('document-b')])

    render(<RecordDocumentsPanel initialAttachmentId="document-b" isActive recordId="record-1" />)

    const preview = await screen.findByRole('dialog', { name: 'Preview duplicate-name.png' })
    expect(preview).toBeInTheDocument()
    const targetCalls = api.createAttachmentPreviewUrl.mock.calls.filter((call) => call[1] === 'document-b')
    expect(targetCalls).toEqual([['record-1', 'document-b']])
    const openButtons = screen.getAllByRole('button', { name: 'Open preview for duplicate-name.png' })
    expect(openButtons[0]).not.toHaveAttribute('aria-current')
    expect(openButtons[1]).toHaveAttribute('aria-current', 'true')

    await user.click(within(preview).getByRole('button', { name: 'Close document preview' }))
    expect(screen.getByRole('region', { name: 'Documents' })).toBeInTheDocument()
    expect(openButtons[1]).toHaveAttribute('aria-current', 'true')
  })

  it('shows a clear state for a stale document ID without retrying it repeatedly', async () => {
    api.listAttachments.mockResolvedValue([attachment('document-a')])

    const { rerender } = render(<RecordDocumentsPanel initialAttachmentId="missing-document" isActive recordId="record-1" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('This document is no longer available')
    rerender(<RecordDocumentsPanel initialAttachmentId="missing-document" isActive recordId="record-1" />)
    expect(api.createAttachmentPreviewUrl).not.toHaveBeenCalledWith('record-1', 'missing-document')
    expect(screen.getByRole('region', { name: 'Documents' })).toBeInTheDocument()
  })

  it('selects a scanning document but never requests preview or download access', async () => {
    api.listAttachments.mockResolvedValue([attachment('scanning-document', 'scanning')])

    render(<RecordDocumentsPanel initialAttachmentId="scanning-document" isActive recordId="record-1" />)

    const statusButton = await screen.findByRole('button', { name: /Open document status.*scanning/i })
    await waitFor(() => expect(statusButton).toHaveAttribute('aria-current', 'true'))
    expect(screen.getByRole('status')).toHaveTextContent('Preview and download stay unavailable')
    expect(api.createAttachmentPreviewUrl).not.toHaveBeenCalled()
    expect(api.createAttachmentDownloadUrl).not.toHaveBeenCalled()
  })
})