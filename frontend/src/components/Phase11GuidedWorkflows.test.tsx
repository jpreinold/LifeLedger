import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { GuidedWorkflowId } from '../lib/guidedWorkflows'
import type { LifeRecord } from '../types/record'
import type { Reminder } from '../types/reminder'
import { AddTypeSelector } from './AddTypeSelector'
import { GuidedWorkflowDrawer } from './GuidedWorkflowDrawer'
import { RecordDetailDrawer } from './RecordDetailDrawer'

const apiMocks = vi.hoisted(() => ({
  createRecord: vi.fn(),
  updateRecord: vi.fn(),
  addField: vi.fn(),
  updateField: vi.fn(),
  setProtected: vi.fn(),
  updateProtected: vi.fn(),
  uploadRecordAttachment: vi.fn(),
  listAttachments: vi.fn(),
  createAttachmentPreviewUrl: vi.fn(),
  createReminder: vi.fn(),
  createRecordLink: vi.fn(),
}))

vi.mock('../api/recordsApi', () => ({
  recordsApi: {
    create: apiMocks.createRecord,
    update: apiMocks.updateRecord,
    addField: apiMocks.addField,
    updateField: apiMocks.updateField,
    setProtected: apiMocks.setProtected,
    updateProtected: apiMocks.updateProtected,
    uploadRecordAttachment: apiMocks.uploadRecordAttachment,
    listAttachments: apiMocks.listAttachments,
    createAttachmentPreviewUrl: apiMocks.createAttachmentPreviewUrl,
  },
}))

vi.mock('../api/remindersApi', () => ({
  remindersApi: { create: apiMocks.createReminder },
}))

vi.mock('../api/linkedItemsApi', () => ({
  linkedItemsApi: {
    createRecordLink: apiMocks.createRecordLink,
    listRecordLinks: vi.fn(async () => ({ records: [], reminders: [], documents: [] })),
    listReminderLinks: vi.fn(async () => ({ records: [], reminders: [], documents: [] })),
    listCandidates: vi.fn(async () => ({ items: [], next_cursor: null })),
    deleteRecordLink: vi.fn(),
    createRelationship: vi.fn(),
    updateRelationship: vi.fn(),
    deleteRelationship: vi.fn(),
  },
}))

const petRecord: LifeRecord = {
  id: 'pet-1',
  record_type: 'pet',
  title: 'Baxter',
  subtitle: 'Beagle',
  category: 'Family',
  owner_name: null,
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
  has_protected_data: false,
  protected_field_names: [],
  dynamic_fields: [],
  created_at: '2026-07-01T12:00:00.000Z',
  updated_at: '2026-07-18T12:00:00.000Z',
}

const reminder = {
  id: 'reminder-1',
  title: 'Rabies vaccination',
  due_date: '2030-08-01',
} as unknown as Reminder

describe('Phase 11 guided workflows', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.createRecord.mockResolvedValue(petRecord)
    apiMocks.updateRecord.mockResolvedValue(petRecord)
    apiMocks.addField.mockResolvedValue(petRecord)
    apiMocks.updateField.mockResolvedValue(petRecord)
    apiMocks.setProtected.mockResolvedValue({ has_protected_data: true, protected_field_names: ['document_number'], protected_encryption_version: 1, protected_updated_at: '2026-07-18T12:00:00.000Z' })
    apiMocks.updateProtected.mockResolvedValue({ has_protected_data: true, protected_field_names: ['document_number'], protected_encryption_version: 1, protected_updated_at: '2026-07-18T12:00:00.000Z' })
    apiMocks.createReminder.mockResolvedValue(reminder)
    apiMocks.createRecordLink.mockResolvedValue({})
    apiMocks.listAttachments.mockResolvedValue([])
  })

  it('exposes all four common tracking intents from the global add selector', async () => {
    const user = userEvent.setup()
    const onChooseWorkflow = vi.fn<(workflowId: GuidedWorkflowId) => void>()
    render(
      <AddTypeSelector
        isOpen
        onBrowseItemTypes={vi.fn()}
        onChooseBirthday={vi.fn()}
        onChooseItem={vi.fn()}
        onChooseMaintenance={vi.fn()}
        onChooseReminder={vi.fn()}
        onChooseRenewal={vi.fn()}
        onChooseWorkflow={onChooseWorkflow}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Common things to track' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Track my passport expiration' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Track my vehicle registration' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Track a pet vaccination' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Track a subscription renewal' })).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Track a pet vaccination' }))
    await waitFor(() => expect(onChooseWorkflow).toHaveBeenCalledWith('pet_vaccination'))
  })

  it('uses item context, accepts a custom vaccination, skips a document, and saves one linked responsibility', async () => {
    const user = userEvent.setup()
    const onDataChanged = vi.fn(async () => undefined)
    let finishReminder: ((value: Reminder) => void) | undefined
    apiMocks.createReminder.mockImplementation(() => new Promise<Reminder>((resolve) => { finishReminder = resolve }))
    render(
      <GuidedWorkflowDrawer
        initialItem={petRecord}
        isOpen
        records={[petRecord]}
        workflowId="pet_vaccination"
        onClose={vi.fn()}
        onDataChanged={onDataChanged}
        onOpenItem={vi.fn()}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Add the useful details' })).toBeVisible()
    expect(screen.queryByRole('radio', { name: /use an existing pet/i })).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(4)

    await user.click(screen.getByRole('button', { name: 'Continue' }))
    await user.type(screen.getByLabelText('Vaccination *'), 'Custom vaccine')
    await user.type(screen.getByLabelText('Next due date *'), '2030-08-01')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(screen.getByText('You can skip this step and add the document from the item later.')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(screen.getByText('Custom vaccine vaccination')).toBeVisible()
    expect(screen.getByText('Document: Add later')).toBeVisible()
    expect(screen.getByText('One time')).toBeVisible()
    expect(screen.queryByText('pet_vaccination')).not.toBeInTheDocument()

    await user.dblClick(screen.getByRole('button', { name: 'Save vaccination' }))
    expect(apiMocks.createReminder).toHaveBeenCalledTimes(1)
    finishReminder?.(reminder)
    await screen.findByRole('heading', { name: 'Pet vaccination is now tracked' })

    expect(apiMocks.createRecord).not.toHaveBeenCalled()
    expect(apiMocks.updateRecord).not.toHaveBeenCalled()
    expect(apiMocks.createReminder).toHaveBeenCalledTimes(1)
    expect(apiMocks.createRecordLink).toHaveBeenCalledWith('pet-1', expect.objectContaining({
      target_type: 'reminder',
      target_id: 'reminder-1',
      relationship_type: 'reminder_for',
    }))
    expect(apiMocks.uploadRecordAttachment).not.toHaveBeenCalled()
    expect(onDataChanged).toHaveBeenCalledTimes(1)
  })

  it('shows only the compatible guided suggestion from an item Responsibility section', async () => {
    const user = userEvent.setup()
    const vehicle = { ...petRecord, id: 'vehicle-1', record_type: 'vehicle', title: 'Mazda3', category: 'Transportation' } as LifeRecord
    const onStartGuidedWorkflow = vi.fn()
    render(
      <RecordDetailDrawer
        record={vehicle}
        records={[vehicle, petRecord]}
        reminders={[]}
        onArchive={vi.fn(async () => undefined)}
        onAddResponsibility={vi.fn()}
        onClose={vi.fn()}
        onEdit={vi.fn()}
        onOpenLinkedRecord={vi.fn()}
        onOpenLinkedReminder={vi.fn()}
        onProtectedStatusChange={vi.fn()}
        onRecordChange={vi.fn()}
        onRequestDelete={vi.fn()}
        onRestore={vi.fn(async () => undefined)}
        onStartGuidedWorkflow={onStartGuidedWorkflow}
      />,
    )

    await user.click(await screen.findByRole('tab', { name: 'Responsibilities' }))
    expect(screen.getByRole('button', { name: 'Track my vehicle registration' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Track a pet vaccination' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Track my passport expiration' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Track my vehicle registration' }))
    expect(onStartGuidedWorkflow).toHaveBeenCalledWith(vehicle, 'vehicle_registration')
  })

  it('clears unsaved protected values when the drawer is discarded and reopened', async () => {
    const user = userEvent.setup()

    function Harness() {
      const [open, setOpen] = useState(true)
      return (
        <>
          {!open ? <button type="button" onClick={() => setOpen(true)}>Reopen workflow</button> : null}
          <GuidedWorkflowDrawer
            isOpen={open}
            records={[]}
            workflowId="passport_expiration"
            onClose={() => setOpen(false)}
            onDataChanged={async () => undefined}
            onOpenItem={vi.fn()}
          />
        </>
      )
    }

    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Passport holder'), { target: { value: 'Jamie' } })
    expect(screen.getByLabelText('Passport holder')).toHaveValue('Jamie')
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    await screen.findByRole('heading', { name: 'Add the useful details' })
    fireEvent.change(screen.getByLabelText('When does it expire? *'), { target: { value: '2030-09-01' } })
    await user.type(screen.getByLabelText(/^Passport number/), 'P1234567')
    await user.click(screen.getByRole('button', { name: 'Close guided tracking' }))
    await user.click(await screen.findByRole('button', { name: 'Discard setup' }))
    await user.click(await screen.findByRole('button', { name: 'Reopen workflow' }))

    expect(screen.getByLabelText('Passport holder')).toHaveValue('')
    expect(screen.queryByDisplayValue('P1234567')).not.toBeInTheDocument()
  })
})
