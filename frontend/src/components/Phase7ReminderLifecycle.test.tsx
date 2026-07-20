import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { getActionCenterGroups } from '../lib/reminderDisplay'
import type { Reminder, ReminderInput } from '../types/reminder'
import { ReminderDetailDrawer } from './ReminderDetailDrawer'
import { ReminderForm } from './ReminderForm'
import { ReminderList } from './ReminderList'

function reminder(overrides: Partial<Reminder>): Reminder {
  return {
    id: 'reminder-1',
    title: 'Reminder',
    category: 'Other',
    due_date: '2026-07-14',
    repeat: 'None',
    priority: 'Medium',
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
    status: 'Scheduled',
    effective_attention_date: '2026-07-14',
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
    ...overrides,
  }
}

describe('Phase 7 reminder lifecycle UI', () => {
  it('keeps existing generic reminder creation working', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn(async () => true)
    const onClose = vi.fn()
    render(
      <ReminderForm
        isOpen
        isSaving={false}
        onBrowseTemplates={vi.fn()}
        onClose={onClose}
        onCreate={onCreate}
        templateDraft={null}
      />,
    )

    await user.type(screen.getByLabelText('Title'), 'Pay annual fee')
    const dueDate = screen.getByLabelText('Due date')
    await user.clear(dueDate)
    await user.type(dueDate, '2026-08-01')
    await user.click(screen.getByRole('button', { name: 'Add reminder' }))

    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Pay annual fee',
      due_date: '2026-08-01',
      reminder_type: 'generic',
    })))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
  it('groups active reminders by lifecycle status and filters archived linked records', () => {
    const groups = getActionCenterGroups([
      reminder({ id: 'older-overdue', title: 'Older overdue', status: 'Overdue', due_date: '2026-06-01', effective_attention_date: '2026-06-01' }),
      reminder({ id: 'recent-overdue', title: 'Recent overdue', status: 'Overdue', due_date: '2026-06-20', effective_attention_date: '2026-06-20' }),
      reminder({ id: 'today', title: 'Due today', status: 'Due today', due_date: '2026-07-14', effective_attention_date: '2026-07-14' }),
      reminder({ id: 'urgent', title: 'Urgent item', status: 'Urgent', due_date: '2026-07-18', effective_attention_date: '2026-07-18' }),
      reminder({ id: 'upcoming', title: 'Upcoming item', status: 'Upcoming', due_date: '2026-08-02', effective_attention_date: '2026-08-02' }),
      reminder({ id: 'later', title: 'Later item', status: 'Scheduled', due_date: '2026-09-01', effective_attention_date: '2026-09-01' }),
      reminder({ id: 'completed', title: 'Completed item', completed: true, status: 'Completed' }),
      reminder({
        id: 'archived-link',
        title: 'Archived record item',
        status: 'Overdue',
        linked_records: [{ id: 'record-1', title: 'Archived record', subtitle: null, record_type: 'general', status: 'archived' }],
      }),
    ])

    expect(groups.find((group) => group.id === 'overdue')?.reminders.map((item) => item.title)).toEqual([
      'Older overdue',
      'Recent overdue',
    ])
    expect(groups.find((group) => group.id === 'today')?.reminders.map((item) => item.title)).toEqual(['Due today'])
    expect(groups.find((group) => group.id === 'soon')?.reminders.map((item) => item.title)).toEqual(['Urgent item', 'Upcoming item'])
    expect(groups.find((group) => group.id === 'later')?.reminders.map((item) => item.title)).toEqual(['Later item'])
  })

  it('renders action center empty states and disables an in-flight reminder action', () => {
    const onComplete = vi.fn(async () => undefined)
    const activeReminder = reminder({ id: 'active', title: 'Renew passport', status: 'Urgent', due_date: '2026-07-18', effective_attention_date: '2026-07-18' })

    render(
      <ReminderList
        reminders={[activeReminder]}
        isLoading={false}
        activeStatusFilter="active"
        activeTypeFilter="all"
        onAddReminder={vi.fn()}
        onBrowseTemplates={vi.fn()}
        onComplete={onComplete}
        onDelete={vi.fn()}
        onEdit={vi.fn()}
        onStatusFilterChange={vi.fn()}
        onTypeFilterChange={vi.fn()}
        onView={vi.fn()}
        pendingActionId="active"
      />,
    )

    expect(screen.getByRole('heading', { name: 'Due soon' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Saving/ })).toBeDisabled()
  })

  it('shows completed history separately from active reminders', () => {
    render(
      <ReminderList
        reminders={[]}
        isLoading={false}
        activeStatusFilter="completed"
        activeTypeFilter="all"
        onAddReminder={vi.fn()}
        onBrowseTemplates={vi.fn()}
        onComplete={vi.fn(async () => undefined)}
        onDelete={vi.fn()}
        onEdit={vi.fn()}
        onStatusFilterChange={vi.fn()}
        onTypeFilterChange={vi.fn()}
        onView={vi.fn()}
      />,
    )

    expect(screen.getByText('No completed reminder history.')).toBeInTheDocument()
  })

  it('submits snooze, clear snooze, and renew actions from reminder detail', async () => {
    const user = userEvent.setup()
    const onClearSnooze = vi.fn(async () => true)
    const onRenew = vi.fn(async () => true)
    const onSnooze = vi.fn(async () => true)
    const renewalReminder = reminder({
      id: 'renewal',
      title: 'Renew car registration',
      category: 'Car',
      due_date: '2026-07-14',
      effective_attention_date: '2026-07-20',
      snoozed_until: '2026-07-20T13:00:00.000Z',
      status: 'Urgent',
      reminder_type: 'renewal',
      repeat: 'Yearly',
      renewal_details: {
        item_name: 'Car registration',
        renewal_kind: 'renewal',
        owner_name: 'Alina',
        provider: 'DMV',
        renewal_date: '2026-07-14',
        expiration_date: null,
        renewal_window_days: 30,
        review_lead_days: null,
        frequency: 'Yearly',
      },
      lifecycle_events: [
        {
          event_id: 'event-1',
          event_type: 'renewed',
          occurred_at: '2026-07-01T12:00:00.000Z',
          summary: 'Renewed from 2025-07-14 to 2026-07-14.',
          actor: 'user',
          previous_due_date: '2025-07-14',
          new_due_date: '2026-07-14',
          snoozed_until: null,
        },
      ],
    })

    render(
      <ReminderDetailDrawer
        reminder={renewalReminder}
        records={[]}
        calendarStatus={null}
        isCalendarStatusLoading={false}
        isAlertEligible={false}
        isActionPending={false}
        onClearSnooze={onClearSnooze}
        onClose={vi.fn()}
        onComplete={vi.fn(async () => undefined)}
        onDisableCalendarSync={vi.fn(async () => true)}
        onDismiss={vi.fn(async () => undefined)}
        onEdit={vi.fn()}
        onEnableCalendarSync={vi.fn(async () => true)}
        onOpenLinkedRecord={vi.fn()}
        onRenew={onRenew}
        onReopen={vi.fn(async () => true)}
        onRequestDelete={vi.fn()}
        onSnooze={onSnooze}
      />,
    )

    await waitFor(() => expect(screen.getByRole('dialog', { name: 'Reminder details' })).toBeVisible())
    const lifecycleSection = screen.getByRole('heading', { name: 'Lifecycle actions' }).closest('section')
    expect(lifecycleSection).not.toBeNull()

    await user.click(within(lifecycleSection as HTMLElement).getByRole('button', { name: 'Snooze' }))
    expect(onSnooze).toHaveBeenCalledWith('renewal', expect.any(String))

    await user.click(within(lifecycleSection as HTMLElement).getByRole('button', { name: 'Clear snooze' }))
    expect(onClearSnooze).toHaveBeenCalledWith('renewal')

    await user.click(within(lifecycleSection as HTMLElement).getByRole('button', { name: 'Review renewal' }))
    expect(onRenew).toHaveBeenCalledWith('renewal', renewalReminder.due_date)
  })

  it('edits reminder values in place and saves from the sticky footer', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn(async (_id: string, _input: ReminderInput) => true)
    const target = reminder({ id: 'inline-edit', title: 'Call Mom' })

    render(
      <ReminderDetailDrawer
        reminder={target}
        records={[]}
        calendarStatus={null}
        isCalendarStatusLoading={false}
        isAlertEligible={false}
        isActionPending={false}
        onClearSnooze={vi.fn(async () => true)}
        onClose={vi.fn()}
        onComplete={vi.fn(async () => undefined)}
        onDisableCalendarSync={vi.fn(async () => true)}
        onDismiss={vi.fn(async () => undefined)}
        onEnableCalendarSync={vi.fn(async () => true)}
        onOpenLinkedRecord={vi.fn()}
        onRenew={vi.fn(async () => true)}
        onReopen={vi.fn(async () => true)}
        onRequestDelete={vi.fn()}
        onSave={onSave}
        onSnooze={vi.fn(async () => true)}
      />,
    )

    await waitFor(() => expect(screen.getByRole('dialog', { name: 'Reminder details' })).toBeVisible())
    await user.click(within(screen.getByLabelText('Reminder actions')).getByRole('button', { name: 'Edit' }))
    const title = screen.getByLabelText('Title')
    await user.clear(title)
    await user.type(title, 'Call Daniel')
    const save = screen.getByRole('button', { name: 'Save changes' })
    expect(save.closest('.sheet-footer')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Discard changes' }).closest('.sheet-footer')).not.toBeNull()
    await user.click(save)

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))
    expect(onSave.mock.calls[0][0]).toBe(target.id)
    expect(onSave.mock.calls[0][1].title).toBe('Call Daniel')
  })
})
