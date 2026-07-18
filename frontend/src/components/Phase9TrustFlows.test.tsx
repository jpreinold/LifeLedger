import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { recordsApi } from '../api/recordsApi'
import type { LinkCreateRequest, LinkedItemsResponse } from '../types/linkedItem'
import type { LifeRecord, ProtectedRecordInput, ProtectedRecordPayload, RecordInput } from '../types/record'
import { RecordDetailDrawer } from './RecordDetailDrawer'
import { RecordForm, type RecordCreationResult } from './RecordForm'

const emptyLinks: LinkedItemsResponse = { records: [], reminders: [], documents: [] }

vi.mock('../api/recordsApi', () => ({
  recordsApi: {
    listAttachments: vi.fn(),
    revealProtected: vi.fn(),
    clearProtected: vi.fn(),
    revealField: vi.fn(),
    deleteField: vi.fn(),
    createAttachmentPreviewUrl: vi.fn(),
  },
}))

vi.mock('../api/linkedItemsApi', () => ({
  linkedItemsApi: {
    listRecordLinks: vi.fn(async () => emptyLinks),
    listReminderLinks: vi.fn(async () => emptyLinks),
    listCandidates: vi.fn(async () => ({ items: [], next_cursor: null })),
    createRecordLink: vi.fn(),
    deleteRecordLink: vi.fn(),
    createRelationship: vi.fn(),
    updateRelationship: vi.fn(),
    deleteRelationship: vi.fn(),
  },
}))

const api = vi.mocked(recordsApi)

const protectedRecord: LifeRecord = {
  id: 'record-protected',
  record_type: 'passport',
  title: 'Passport',
  subtitle: null,
  category: 'Documents',
  owner_name: 'Alina',
  provider_or_brand: null,
  start_date: null,
  issue_date: null,
  expiration_date: null,
  purchase_date: null,
  renewal_date: null,
  location_hint: null,
  notes: null,
  tags: [],
  status: 'active',
  has_protected_data: true,
  protected_field_names: ['document_number'],
  dynamic_fields: [],
  created_at: '2026-07-17T12:00:00.000Z',
  updated_at: '2026-07-17T12:00:00.000Z',
}

const revealedPayload: ProtectedRecordPayload = {
  document_number: 'P1234567',
  license_number: null,
  vin: null,
  policy_number: null,
  member_number: null,
  serial_number: null,
  account_reference: null,
  sensitive_notes: null,
}

function detailProps() {
  return {
    record: protectedRecord,
    records: [protectedRecord],
    reminders: [],
    onArchive: vi.fn(async () => undefined),
    onAddResponsibility: vi.fn(),
    onClose: vi.fn(),
    onEdit: vi.fn(),
    onOpenLinkedRecord: vi.fn(),
    onOpenLinkedReminder: vi.fn(),
    onProtectedStatusChange: vi.fn(),
    onRecordChange: vi.fn(),
    onRequestDelete: vi.fn(),
    onRestore: vi.fn(async () => undefined),
  }
}

describe('Phase 9 protected details and creation recovery', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    window.localStorage.clear()
    api.listAttachments.mockResolvedValue([])
    api.revealProtected.mockResolvedValue(revealedPayload)
    api.clearProtected.mockResolvedValue({
      has_protected_data: false,
      protected_field_names: [],
      protected_encryption_version: null,
      protected_updated_at: null,
    })
  })

  it('keeps protected details masked until reveal, re-hides plaintext, and confirms clearing', async () => {
    const user = userEvent.setup()
    const props = detailProps()
    render(<RecordDetailDrawer {...props} />)

    const section = await screen.findByRole('region', { name: 'Protected details' })
    expect(within(section).queryByText('P1234567')).not.toBeInTheDocument()
    expect(within(section).getByText('••••••••')).toHaveClass('masked-field-value')
    expect(api.revealProtected).not.toHaveBeenCalled()

    await user.click(within(section).getByRole('button', { name: 'Reveal' }))
    expect(await within(section).findByText('P1234567')).toBeInTheDocument()
    expect(api.revealProtected).toHaveBeenCalledWith('record-protected')

    await user.click(within(section).getByRole('button', { name: 'Hide' }))
    expect(within(section).queryByText('P1234567')).not.toBeInTheDocument()

    await user.click(within(section).getByRole('button', { name: 'Clear' }))
    const confirmation = screen.getByRole('alertdialog', { name: 'Clear protected details?' })
    expect(confirmation).toHaveTextContent('permanently removed')
    expect(api.clearProtected).not.toHaveBeenCalled()
    await user.click(within(confirmation).getByRole('button', { name: 'Clear protected details' }))
    await waitFor(() => expect(api.clearProtected).toHaveBeenCalledWith('record-protected'))
    expect(props.onProtectedStatusChange).toHaveBeenCalledWith('record-protected', expect.objectContaining({ has_protected_data: false }))

    await user.click(screen.getByRole('button', { name: 'Add another detail' }))
    const detailEditor = await screen.findByRole('dialog', { name: 'Add another detail' })
    expect(within(detailEditor).queryByText('Passport number')).not.toBeInTheDocument()
    expect(within(detailEditor).getByRole('button', { name: /Nationality/ })).toBeInTheDocument()
  })

  it('submits a protected detail during creation and retries unfinished setup without browser persistence', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn<(
      input: RecordInput,
      protectedInput: ProtectedRecordInput,
      files: File[],
      links: LinkCreateRequest[],
      workflowId: string,
    ) => Promise<RecordCreationResult>>()
    onCreate
      .mockResolvedValueOnce({
        complete: false,
        recordId: 'record-created',
        message: 'Passport was created, but protected details were not saved. Retry now.',
        stages: [
          { label: 'Item', status: 'saved' },
          { label: 'Protected details', status: 'needs_retry' },
        ],
      })
      .mockResolvedValueOnce({ complete: true, recordId: 'record-created', message: null })
    const onClose = vi.fn()

    render(
      <RecordForm
        isOpen
        isSaving={false}
        record={null}
        records={[]}
        recordType="passport"
        reminders={[]}
        onClose={onClose}
        onCreate={onCreate}
        onUpdate={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('Passport holder'), 'Passport')
    const protectedInput = screen.getByLabelText('Passport number')
    expect(protectedInput).toHaveAttribute('type', 'password')
    await user.type(protectedInput, 'P1234567')
    await user.click(screen.getByRole('button', { name: 'Add passport' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('was created')
    const progress = screen.getByRole('list', { name: 'Item setup progress' })
    expect(within(progress).getByText('Item').parentElement).toHaveTextContent('Saved')
    expect(within(progress).getByText('Protected details').parentElement).toHaveTextContent('Needs retry')
    expect(JSON.stringify(window.localStorage)).not.toContain('P1234567')
    expect(onCreate.mock.calls[0][1]).toEqual({ document_number: 'P1234567' })

    await user.click(screen.getByRole('button', { name: 'Retry unfinished setup' }))
    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(2))
    expect(onCreate.mock.calls[1][1]).toEqual({ document_number: 'P1234567' })
    expect(onCreate.mock.calls[1][4]).toBe(onCreate.mock.calls[0][4])
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('adds and removes a protected detail while editing an existing record', async () => {
    const user = userEvent.setup()
    const onUpdate = vi.fn(async () => true)
    const recordWithoutProtected = {
      ...protectedRecord,
      has_protected_data: false,
      protected_field_names: [],
    }
    const { unmount } = render(
      <RecordForm
        isOpen
        isSaving={false}
        record={recordWithoutProtected}
        records={[recordWithoutProtected]}
        recordType="passport"
        reminders={[]}
        onClose={vi.fn()}
        onCreate={vi.fn(async () => true)}
        onUpdate={onUpdate}
      />,
    )
    await user.type(screen.getByLabelText('Passport number'), 'P-NEW')
    await user.click(screen.getByRole('button', { name: 'Save item' }))
    expect(onUpdate).toHaveBeenCalledWith('record-protected', expect.any(Object), { document_number: 'P-NEW' })

    unmount()
    onUpdate.mockClear()
    render(
      <RecordForm
        isOpen
        isSaving={false}
        record={protectedRecord}
        records={[protectedRecord]}
        recordType="passport"
        reminders={[]}
        onClose={vi.fn()}
        onCreate={vi.fn(async () => true)}
        onUpdate={onUpdate}
      />,
    )
    await user.click(await screen.findByRole('button', { name: 'Remove' }))
    await user.click(screen.getByRole('button', { name: 'Save item' }))
    expect(onUpdate).toHaveBeenCalledWith('record-protected', expect.any(Object), { document_number: null })
  })

  it('blocks duplicate form submissions while the first request is pending', async () => {
    let resolveCreate!: (result: RecordCreationResult) => void
    const onCreate = vi.fn(() => new Promise<RecordCreationResult>((resolve) => {
      resolveCreate = resolve
    }))
    render(
      <RecordForm
        isOpen
        isSaving={false}
        record={null}
        records={[]}
        recordType="general"
        reminders={[]}
        onClose={vi.fn()}
        onCreate={onCreate}
        onUpdate={vi.fn()}
      />,
    )
    await userEvent.type(screen.getByLabelText('Item name'), 'One item')
    const form = screen.getByRole('button', { name: 'Add other item' }).closest('form')
    fireEvent.submit(form!)
    fireEvent.submit(form!)
    expect(onCreate).toHaveBeenCalledTimes(1)

    resolveCreate({ complete: false, recordId: 'record-1', message: 'Created; finish later.' })
    expect(await screen.findByRole('alert')).toHaveTextContent('finish later')
  })
})
