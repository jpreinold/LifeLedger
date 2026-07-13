import { useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createRenewalReminderInput } from '../lib/reminderInput'
import type { DynamicFieldPreset } from '../lib/recordTypes'
import type { LinkCreateRequest } from '../types/linkedItem'
import type { LifeRecord, ProtectedRecordInput, RecordInput } from '../types/record'
import type { ReminderInput } from '../types/reminder'
import { AddFieldDrawer } from './AddFieldDrawer'
import { RecordDetailDrawer } from './RecordDetailDrawer'
import { RecordForm } from './RecordForm'
import { ReminderFields } from './ReminderForm'

const recordsApiMocks = vi.hoisted(() => ({
  addField: vi.fn(),
  listAttachments: vi.fn(),
}))

vi.mock('../api/recordsApi', () => ({
  recordsApi: {
    addField: recordsApiMocks.addField,
    listAttachments: recordsApiMocks.listAttachments,
  },
}))

const addFieldMock = recordsApiMocks.addField
const listAttachmentsMock = recordsApiMocks.listAttachments

const baseRecord: LifeRecord = {
  id: 'record-1',
  record_type: 'general',
  title: 'Resume',
  subtitle: null,
  category: 'General',
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
  created_at: '2026-07-11T22:54:00.000Z',
  updated_at: '2026-07-11T22:54:00.000Z',
}

const suggestedFields: DynamicFieldPreset[] = [
  {
    key: 'microchip',
    label: 'Microchip',
    field_type: 'short_text',
    is_sensitive: true,
    description: 'Pet identification microchip number.',
  },
  {
    key: 'vet',
    label: 'Vet',
    field_type: 'short_text',
    description: 'Veterinarian clinic or doctor.',
  },
]

describe('Phase 6 mobile flows', () => {
  beforeEach(() => {
    addFieldMock.mockReset()
    listAttachmentsMock.mockReset()
    listAttachmentsMock.mockResolvedValue([])
  })

  it('switches add-field tabs and closes the sheet', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    render(
      <AddFieldDrawer
        isOpen
        record={baseRecord}
        suggestedFields={suggestedFields}
        onClose={onClose}
        onSaved={vi.fn()}
      />,
    )

    expect(screen.getByText('Choose a suggested field')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Custom' }))

    expect(screen.getByLabelText('Field name')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Custom' })).toHaveAttribute('aria-selected', 'true')

    await user.click(screen.getByRole('tab', { name: 'Suggested' }))

    expect(screen.getByRole('button', { name: /Microchip/ })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Close add field' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('opens suggested-field value entry and returns to the suggested list', async () => {
    const user = userEvent.setup()

    render(
      <AddFieldDrawer
        isOpen
        record={baseRecord}
        suggestedFields={suggestedFields}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: /Microchip/ }))

    expect(screen.getByText('Microchip')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Enter microchip')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Back to suggested fields' }))

    expect(screen.getByText('Choose a suggested field')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Vet/ })).toBeInTheDocument()
  })

  it('saves custom fields with hide-by-default unchanged in the API payload', async () => {
    const user = userEvent.setup()
    const onSaved = vi.fn()
    addFieldMock.mockResolvedValue({ ...baseRecord, dynamic_fields: [] })

    render(
      <AddFieldDrawer
        isOpen
        record={baseRecord}
        suggestedFields={suggestedFields}
        onClose={vi.fn()}
        onSaved={onSaved}
      />,
    )

    await user.click(screen.getByRole('tab', { name: 'Custom' }))
    await user.type(screen.getByLabelText('Field name'), 'Microchip')
    await user.click(screen.getByRole('switch', { name: /Hide value by default/ }))
    await user.type(screen.getByLabelText('Value'), '987654321')
    await user.click(screen.getByRole('button', { name: /Save field/ }))

    await waitFor(() => expect(addFieldMock).toHaveBeenCalledTimes(1))
    expect(addFieldMock).toHaveBeenCalledWith('record-1', {
      key: 'microchip',
      label: 'Microchip',
      field_type: 'short_text',
      value: '987654321',
      is_sensitive: true,
      select_options: [],
      display_order: null,
    })
    expect(onSaved).toHaveBeenCalledWith({ ...baseRecord, dynamic_fields: [] })
  })

  it('updates renewal contextual fields and opens accordion sections', async () => {
    const user = userEvent.setup()

    render(<ReminderFieldsHarness />)

    await user.click(screen.getByRole('radio', { name: /Subscription/ }))

    expect(screen.getByLabelText('Service name')).toBeInTheDocument()
    expect(screen.getByLabelText('Next renewal date')).toBeInTheDocument()

    const schedule = screen.getByText('Schedule').closest('details')
    const moreOptions = screen.getByText('More options').closest('details')

    expect(schedule).not.toHaveAttribute('open')
    expect(moreOptions).not.toHaveAttribute('open')

    await user.click(screen.getByText('Schedule'))
    await user.click(screen.getByText('More options'))

    expect(schedule).toHaveAttribute('open')
    expect(moreOptions).toHaveAttribute('open')
  })

  it('associates renewal validation with the touched input', () => {
    render(<ReminderFieldsHarness />)

    const itemInput = screen.getByLabelText('Item name')

    expect(itemInput).not.toHaveAttribute('aria-invalid', 'true')

    fireEvent.blur(itemInput)

    expect(itemInput).toHaveAttribute('aria-invalid', 'true')
    expect(itemInput).toHaveAccessibleDescription('Enter an item name.')
  })

  it('keeps record dashboard actions wired', async () => {
    const user = userEvent.setup()
    const onArchive = vi.fn(async () => undefined)
    const onEdit = vi.fn()
    const onRequestDelete = vi.fn()

    render(
      <RecordDetailDrawer
        record={baseRecord}
        records={[]}
        reminders={[]}
        onArchive={onArchive}
        onClose={vi.fn()}
        onEdit={onEdit}
        onOpenLinkedRecord={vi.fn()}
        onOpenLinkedReminder={vi.fn()}
        onProtectedStatusChange={vi.fn()}
        onRecordChange={vi.fn()}
        onRequestDelete={onRequestDelete}
        onRestore={vi.fn(async () => undefined)}
      />,
    )

    await waitFor(() => expect(screen.getByRole('dialog', { name: 'Record dashboard' })).toBeVisible())
    const actions = screen.getByLabelText('Record actions')

    await user.click(within(actions).getByRole('button', { name: /Archive/ }))
    await user.click(within(actions).getByRole('button', { name: /Delete/ }))
    await user.click(within(actions).getByRole('button', { name: /Edit/ }))

    expect(onArchive).toHaveBeenCalledWith(baseRecord)
    expect(onRequestDelete).toHaveBeenCalledWith(baseRecord)
    await waitFor(() => expect(onEdit).toHaveBeenCalledWith(baseRecord))
  })

  it('stages linked items while adding a record and includes them in the create payload', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn(async (
      _input: RecordInput,
      _protectedInput: ProtectedRecordInput,
      _files: File[],
      _links: LinkCreateRequest[],
    ) => true)
    const linkedRecord: LifeRecord = {
      ...baseRecord,
      id: 'record-2',
      record_type: 'passport',
      title: 'Passport',
    }

    render(
      <RecordForm
        isOpen
        isSaving={false}
        record={null}
        records={[linkedRecord]}
        recordType="general"
        reminders={[]}
        onClose={vi.fn()}
        onCreate={onCreate}
        onUpdate={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('tab', { name: 'Linked items' }))
    await user.click(screen.getByRole('button', { name: 'Link item' }))

    const picker = screen.getByRole('dialog', { name: 'Add linked item' })
    await user.click(within(picker).getByRole('button', { name: /^Record/ }))
    await user.click(within(picker).getByRole('button', { name: /Passport/ }))
    await user.click(within(picker).getByRole('button', { name: 'Link item' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Add linked item' })).not.toBeInTheDocument())
    expect(await screen.findByText('Passport')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Details' }))
    await user.type(screen.getByLabelText('Title'), 'Travel folder')
    await user.click(screen.getByRole('button', { name: /Add record/ }))

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1))
    expect(onCreate.mock.calls[0][3]).toEqual([
      {
        target_type: 'record',
        target_id: 'record-2',
        relationship_type: 'related',
        label: null,
      },
    ])
  })
})

function ReminderFieldsHarness() {
  const [form, setForm] = useReminderFormState()

  return <ReminderFields form={form} setForm={setForm} />
}

function useReminderFormState(): [ReminderInput, Dispatch<SetStateAction<ReminderInput>>] {
  return useState<ReminderInput>(createRenewalReminderInput({
    due_date: '',
    renewal_details: {
      item_name: '',
      renewal_kind: 'renewal',
      owner_name: null,
      provider: null,
      renewal_date: '',
      expiration_date: null,
      renewal_window_days: null,
      review_lead_days: null,
      frequency: null,
    },
  }))
}
