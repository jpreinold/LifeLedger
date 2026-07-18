import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { LifeRecord, RecordType } from '../types/record'
import type { Reminder } from '../types/reminder'
import { AddTypeSelector } from './AddTypeSelector'
import { RecordDetailDrawer } from './RecordDetailDrawer'
import { RecordForm } from './RecordForm'
import { RecordsView } from './RecordsView'

vi.mock('../api/recordsApi', () => ({
  recordsApi: {
    listAttachments: vi.fn(async () => []),
    createAttachmentPreviewUrl: vi.fn(),
  },
}))

vi.mock('../api/linkedItemsApi', () => ({
  linkedItemsApi: {
    listRecordLinks: vi.fn(async () => ({ records: [], reminders: [], documents: [] })),
    listReminderLinks: vi.fn(async () => ({ records: [], reminders: [], documents: [] })),
    listCandidates: vi.fn(async () => ({ items: [], next_cursor: null })),
    createRecordLink: vi.fn(),
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
  category: 'Pet',
  owner_name: 'Jamie',
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

const vaccinationReminder: Reminder = {
  id: 'reminder-1',
  title: 'Rabies vaccination',
  category: 'Family',
  due_date: '2026-08-18',
  repeat: 'Yearly',
  priority: 'Medium',
  notes: null,
  reminder_lead_value: 2,
  reminder_lead_unit: 'weeks',
  reminder_time: null,
  reminder_type: 'renewal',
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
  status: 'Scheduled',
  effective_attention_date: '2026-08-18',
  created_at: '2026-07-01T12:00:00.000Z',
  updated_at: '2026-07-18T12:00:00.000Z',
  completed_at: null,
  lifecycle_events: [],
  linked_records: [{ id: petRecord.id, title: petRecord.title, subtitle: petRecord.subtitle, record_type: 'pet', status: 'active' }],
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

describe('Phase 10 product language and item flows', () => {
  beforeEach(() => vi.clearAllMocks())

  it('asks what to track, exposes real item choices, and never offers coming-soon cards', async () => {
    const user = userEvent.setup()
    const onChooseItem = vi.fn<(type: RecordType) => void>()
    render(
      <AddTypeSelector
        isOpen
        onBrowseItemTypes={vi.fn()}
        onChooseBirthday={vi.fn()}
        onChooseItem={onChooseItem}
        onChooseMaintenance={vi.fn()}
        onChooseReminder={vi.fn()}
        onChooseRenewal={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('dialog', { name: 'What would you like to keep track of?' })).toBeVisible()
    expect(screen.getByText('A pet')).toBeInTheDocument()
    expect(screen.getByText('A vehicle')).toBeInTheDocument()
    expect(screen.getByText('Something else')).toBeInTheDocument()
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add pet' }))
    await waitFor(() => expect(onChooseItem).toHaveBeenCalledWith('pet'))
  })

  it('renders pet suggestions from the registry and keeps technical field-source language out of the advanced flow', async () => {
    const user = userEvent.setup()
    render(
      <RecordForm
        isOpen
        isSaving={false}
        record={null}
        records={[]}
        recordType="pet"
        reminders={[]}
        onClose={vi.fn()}
        onCreate={vi.fn(async () => true)}
        onUpdate={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Pet name')).toBeInTheDocument()
    expect(screen.getByLabelText('Breed')).toBeInTheDocument()
    expect(screen.getByLabelText('Birthday')).toHaveAttribute('type', 'date')
    expect(screen.getByLabelText('Veterinarian')).toBeInTheDocument()
    expect(screen.getByLabelText('Microchip number')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add another detail' }))
    const detailEditor = screen.getByRole('dialog', { name: 'Add another detail' })
    expect(within(detailEditor).getByLabelText('Detail name')).toBeInTheDocument()
    expect(within(detailEditor).getByLabelText('Value format')).toBeInTheDocument()
    expect(within(detailEditor).getByRole('option', { name: 'Yes or no' })).toBeInTheDocument()
    expect(within(detailEditor).getByRole('option', { name: 'Choice list' })).toBeInTheDocument()
    expect(within(detailEditor).queryByText(/field source/i)).not.toBeInTheDocument()
    expect(within(detailEditor).getByRole('switch', { name: 'Protect this detail' })).toBeInTheDocument()
  })

  it('renders vehicle-specific fields including protected VIN support', () => {
    render(
      <RecordForm
        isOpen
        isSaving={false}
        record={null}
        records={[]}
        recordType="vehicle"
        reminders={[]}
        onClose={vi.fn()}
        onCreate={vi.fn(async () => true)}
        onUpdate={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Vehicle name')).toBeInTheDocument()
    expect(screen.getByLabelText('Make')).toBeInTheDocument()
    expect(screen.getByLabelText('Model')).toBeInTheDocument()
    expect(screen.getByLabelText('Year')).toHaveAttribute('type', 'number')
    expect(screen.getByLabelText('License plate')).toBeInTheDocument()
    expect(screen.getByLabelText('VIN')).toHaveAttribute('type', 'password')
  })

  it('preserves the generic Other item form and Items collection language', () => {
    const { unmount } = render(
      <RecordForm
        isOpen
        isSaving={false}
        record={null}
        records={[]}
        recordType="general"
        reminders={[]}
        onClose={vi.fn()}
        onCreate={vi.fn(async () => true)}
        onUpdate={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Item name')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add other item' })).toBeInTheDocument()
    unmount()

    render(
      <RecordsView
        activeFilter="all"
        isLoading={false}
        records={[]}
        showArchived={false}
        onAddRecord={vi.fn()}
        onFilterChange={vi.fn()}
        onShowArchivedChange={vi.fn()}
        onViewRecord={vi.fn()}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Items' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Add item' }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('heading', { name: 'Records' })).not.toBeInTheDocument()
  })

  it('shows the specific item type and connected reminders as responsibilities', async () => {
    const user = userEvent.setup()
    const onAddResponsibility = vi.fn()
    render(
      <RecordDetailDrawer
        record={petRecord}
        records={[petRecord]}
        reminders={[vaccinationReminder]}
        onAddResponsibility={onAddResponsibility}
        onArchive={vi.fn(async () => undefined)}
        onClose={vi.fn()}
        onEdit={vi.fn()}
        onOpenLinkedRecord={vi.fn()}
        onOpenLinkedReminder={vi.fn()}
        onProtectedStatusChange={vi.fn()}
        onRecordChange={vi.fn()}
        onRequestDelete={vi.fn()}
        onRestore={vi.fn(async () => undefined)}
      />,
    )

    const dialog = await screen.findByRole('dialog', { name: 'Item details' })
    expect(within(dialog).getByText('Pet', { selector: '.type-chip' })).toBeInTheDocument()
    expect(within(dialog).queryByText('Category', { selector: 'dt' })).not.toBeInTheDocument()
    expect(within(dialog).getByRole('tab', { name: 'Documents' })).toBeInTheDocument()
    expect(within(dialog).getByRole('tab', { name: 'Related items' })).toBeInTheDocument()

    await user.click(within(dialog).getByRole('tab', { name: 'Responsibilities' }))
    expect(within(dialog).getByRole('button', { name: /Rabies vaccination/ })).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Annual vaccination' }))
    expect(onAddResponsibility).toHaveBeenCalledWith(petRecord, expect.objectContaining({ label: 'Annual vaccination' }))
  })

  it('keeps unsupported legacy item data visible as Other item', async () => {
    const legacyRecord = { ...petRecord, id: 'legacy-1', record_type: 'legacy_kind' as RecordType, title: 'Imported keepsake', category: 'Legacy imports' }
    render(
      <RecordDetailDrawer
        record={legacyRecord}
        records={[legacyRecord]}
        reminders={[]}
        onAddResponsibility={vi.fn()}
        onArchive={vi.fn(async () => undefined)}
        onClose={vi.fn()}
        onEdit={vi.fn()}
        onOpenLinkedRecord={vi.fn()}
        onOpenLinkedReminder={vi.fn()}
        onProtectedStatusChange={vi.fn()}
        onRecordChange={vi.fn()}
        onRequestDelete={vi.fn()}
        onRestore={vi.fn(async () => undefined)}
      />,
    )

    const dialog = await screen.findByRole('dialog', { name: 'Item details' })
    expect(within(dialog).getByText('Other item', { selector: '.type-chip' })).toBeInTheDocument()
    expect(within(dialog).getByText('Imported keepsake')).toBeInTheDocument()
    expect(within(dialog).getByText('Legacy imports')).toBeInTheDocument()
  })
})
