import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import { linkedItemsApi } from '../api/linkedItemsApi'
import type { LinkedItemsResponse } from '../types/linkedItem'
import type { LifeRecord } from '../types/record'
import type { Reminder } from '../types/reminder'
import { LinkedItemsPanel } from './LinkedItemsPanel'

vi.mock('../api/linkedItemsApi', () => ({
  linkedItemsApi: {
    listRecordLinks: vi.fn(),
    listReminderLinks: vi.fn(),
    createRelationship: vi.fn(),
    updateRelationship: vi.fn(),
    deleteRelationship: vi.fn(),
    listCandidates: vi.fn(),
  },
}))

const api = vi.mocked(linkedItemsApi)

const baseRecord: LifeRecord = {
  id: 'record-1',
  record_type: 'pet',
  title: 'Baxter',
  subtitle: null,
  category: 'Pets',
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
  updated_at: '2026-07-01T12:00:00.000Z',
}

const vetRecord: LifeRecord = {
  ...baseRecord,
  id: 'record-2',
  record_type: 'general',
  title: 'Queen City Animal Hospital',
  category: 'Pets',
}

const reminder: Reminder = {
  id: 'reminder-1',
  title: 'Rabies vaccination',
  category: 'Health',
  due_date: '2026-09-18',
  repeat: 'Yearly',
  priority: 'High',
  notes: null,
  reminder_lead_value: null,
  reminder_lead_unit: null,
  reminder_time: null,
  reminder_type: 'generic',
  birthday_details: null,
  renewal_details: null,
  maintenance_details: null,
  completed: false,
  alert_dismissed_until: null,
  alert_last_seen_at: null,
  alert_last_action_at: null,
  alert_snoozed_until: null,
  snoozed_until: null,
  archived_at: null,
  status: 'Upcoming',
  effective_attention_date: '2026-09-18',
  created_at: '2026-07-01T12:00:00.000Z',
  updated_at: '2026-07-01T12:00:00.000Z',
  completed_at: null,
  lifecycle_events: [],
  linked_records: [],
  next_due_date: null,
  computed_label: null,
  birthday_age_label: null,
  renewal_status_label: null,
  renewal_window_label: null,
  maintenance_status_label: null,
  calendar_sync_enabled: false,
  calendar_provider: null,
  calendar_id: null,
  calendar_last_synced_at: null,
  calendar_sync_status: 'not_synced',
  calendar_sync_error: null,
}

const populatedLinks: LinkedItemsResponse = {
  records: [
    {
      link_id: 'link-record',
      relationship_type: 'provided_by',
      label: null,
      direction: 'outbound',
      created_at: '2026-07-01T12:00:00.000Z',
      linked_entity: {
        entity_type: 'record',
        id: 'record-2',
        title: 'Queen City Animal Hospital',
        subtitle: 'Pets',
        record_type: 'general',
        reminder_type: null,
        status: 'active',
        due_date: null,
        date: null,
        document_record_id: null,
        content_type: null,
        size_bytes: null,
      },
    },
  ],
  reminders: [
    {
      link_id: 'link-reminder',
      relationship_type: 'reminder_for',
      label: null,
      direction: 'outbound',
      created_at: '2026-07-01T12:00:00.000Z',
      linked_entity: {
        entity_type: 'reminder',
        id: 'reminder-1',
        title: 'Rabies vaccination',
        subtitle: 'Health',
        record_type: null,
        reminder_type: 'generic',
        status: 'Upcoming',
        due_date: '2026-09-18',
        date: '2026-09-18',
        document_record_id: null,
        content_type: null,
        size_bytes: null,
      },
    },
  ],
  documents: [
    {
      link_id: 'link-document',
      relationship_type: 'document_for',
      label: null,
      direction: 'outbound',
      created_at: '2026-07-01T12:00:00.000Z',
      linked_entity: {
        entity_type: 'document',
        id: 'record-1#attachment-1',
        title: 'Adoption document.pdf',
        subtitle: 'Baxter',
        record_type: null,
        reminder_type: null,
        status: 'available',
        due_date: null,
        date: '2026-07-01',
        document_record_id: 'record-1',
        content_type: 'application/pdf',
        size_bytes: 1234,
      },
    },
  ],
}

describe('LinkedItemsPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    api.listRecordLinks.mockResolvedValue(populatedLinks)
    api.updateRelationship.mockResolvedValue({} as never)
    api.deleteRelationship.mockResolvedValue(undefined)
    api.createRelationship.mockResolvedValue({} as never)
  })

  it('renders linked records, reminders, and documents and opens document owners', async () => {
    const onOpenDocument = vi.fn()

    render(
      <LinkedItemsPanel
        records={[baseRecord, vetRecord]}
        reminders={[reminder]}
        showAdd
        sourceId="record-1"
        sourceTitle="Baxter"
        sourceType="record"
        onOpenDocument={onOpenDocument}
      />,
    )

    expect(screen.getByText('Loading linked items...')).toBeInTheDocument()
    expect(await screen.findByText('Queen City Animal Hospital')).toBeInTheDocument()
    expect(screen.getByText('Rabies vaccination')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Open Adoption document.pdf' }))
    expect(onOpenDocument).toHaveBeenCalledWith('record-1', 'record-1#attachment-1')
  })

  it('edits and removes relationships with clear confirmation text', async () => {
    const user = userEvent.setup()

    render(
      <LinkedItemsPanel
        records={[baseRecord, vetRecord]}
        reminders={[reminder]}
        showAdd
        sourceId="record-1"
        sourceTitle="Baxter"
        sourceType="record"
      />,
    )

    await screen.findByText('Rabies vaccination')
    await user.click(screen.getByRole('button', { name: 'Edit relationship to Rabies vaccination' }))
    const editDialog = screen.getByRole('dialog', { name: 'Edit relationship' })
    await user.click(within(editDialog).getByLabelText('Provided by'))
    await user.type(within(editDialog).getByPlaceholderText('e.g. Primary insurance'), 'Annual visit')
    await user.click(within(editDialog).getByRole('button', { name: 'Save relationship' }))

    await waitFor(() => expect(api.updateRelationship).toHaveBeenCalledWith('link-reminder', {
      relationship_type: 'provided_by',
      custom_label: 'Annual visit',
    }))

    await user.click(screen.getByRole('button', { name: 'Remove link to Adoption document.pdf' }))
    expect(screen.getByText('Remove this link? Baxter and Adoption document.pdf will remain in LifeLedger.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remove link' }))
    expect(api.deleteRelationship).toHaveBeenCalledWith('link-document')
  })

  it('shows duplicate errors from create relationship', async () => {
    const user = userEvent.setup()
    api.listRecordLinks.mockResolvedValue(emptyLinks())
    api.createRelationship.mockRejectedValue(new Error('This item is already linked'))

    render(
      <LinkedItemsPanel
        records={[baseRecord, vetRecord]}
        reminders={[reminder]}
        showAdd
        sourceId="record-1"
        sourceType="record"
      />,
    )

    await screen.findByText(/No linked items yet/)
    await user.click(screen.getByRole('button', { name: 'Add linked item' }))
    const picker = screen.getByRole('dialog', { name: 'Add linked item' })
    await user.click(within(picker).getByRole('button', { name: /^Record/ }))
    await user.click(within(picker).getByRole('button', { name: /Queen City Animal Hospital/ }))
    await user.click(within(picker).getByRole('button', { name: 'Link item' }))

    expect(await within(picker).findByText('This item is already linked')).toBeInTheDocument()
  })
})

function emptyLinks(): LinkedItemsResponse {
  return { records: [], reminders: [], documents: [] }
}
