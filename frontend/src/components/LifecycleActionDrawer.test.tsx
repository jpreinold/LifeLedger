import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { recordsApi } from '../api/recordsApi'
import { remindersApi } from '../api/remindersApi'
import type { LifeRecord } from '../types/record'
import type { Reminder } from '../types/reminder'
import { LifecycleActionDrawer } from './LifecycleActionDrawer'

vi.mock('../api/remindersApi', () => ({ remindersApi: { complete: vi.fn(), renew: vi.fn(), addEvidence: vi.fn() } }))
vi.mock('../api/recordsApi', () => ({ recordsApi: { uploadRecordAttachment: vi.fn() } }))

describe('LifecycleActionDrawer', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reviews and completes a one-time responsibility without requiring a note or document', async () => {
    const reminder = baseReminder()
    vi.mocked(remindersApi.complete).mockResolvedValue({ ...reminder, completed: true, status: 'Completed', completed_at: '2026-07-18T00:00:00Z' })
    const onSaved = vi.fn()
    render(<LifecycleActionDrawer action="complete" reminder={reminder} records={[]} onClose={vi.fn()} onSaved={onSaved} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Review' }))
    expect(screen.getByText('Previous due date')).toBeVisible()
    expect(screen.getByText('Remains completed')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm completion' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(remindersApi.complete).toHaveBeenCalledWith(
      'reminder-1',
      expect.objectContaining({ occurrence_id: 'occurrence-1', note: null }),
      expect.any(String),
    )
    expect(recordsApi.uploadRecordAttachment).not.toHaveBeenCalled()
  })

  it('shows recurring next-due behavior and renewal date transitions before confirmation', async () => {
    const recurring = baseReminder({ repeat: 'Yearly', due_date: '2026-09-18' })
    const { unmount } = render(<LifecycleActionDrawer action="complete" reminder={recurring} records={[]} onClose={vi.fn()} onSaved={vi.fn()} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Review' }))
    expect(screen.getByText('Sep 18, 2027')).toBeVisible()
    unmount()

    const renewal = baseReminder({ reminder_type: 'renewal', due_date: '2027-03-31' })
    render(<LifecycleActionDrawer action="renew" reminder={renewal} records={[]} onClose={vi.fn()} onSaved={vi.fn()} />)
    const nextDate = await screen.findByLabelText('New expiration or due date')
    await userEvent.clear(nextDate)
    await userEvent.type(nextDate, '2028-03-31')
    await userEvent.click(screen.getByRole('button', { name: 'Review' }))
    expect(screen.getByText('Mar 31, 2027')).toBeVisible()
    expect(screen.getByText('Mar 31, 2028')).toBeVisible()
  })

  it('retries a failed optional document without repeating the completion event', async () => {
    const reminder = baseReminder({ linked_records: [{ id: 'record-1', title: 'Baxter', subtitle: null, record_type: 'pet', status: 'active' }] })
    const completed = { ...reminder, completed: true, status: 'Completed' as const, last_lifecycle_event_id: 'event-completed' }
    vi.mocked(remindersApi.complete).mockResolvedValue(completed)
    vi.mocked(recordsApi.uploadRecordAttachment)
      .mockRejectedValueOnce(new Error('upload interrupted'))
      .mockResolvedValueOnce({ attachment_id: 'document-1', status: 'scanning' } as never)
    vi.mocked(remindersApi.addEvidence).mockResolvedValue({ event_id: 'evidence-1' } as never)
    const onSaved = vi.fn()
    render(<LifecycleActionDrawer action="complete" reminder={reminder} records={[record()]} onClose={vi.fn()} onSaved={onSaved} />)

    const file = new File(['%PDF-1.4'], 'vaccination.pdf', { type: 'application/pdf' })
    await userEvent.upload(document.querySelector('input[type="file"]') as HTMLInputElement, file)
    await userEvent.click(screen.getByRole('button', { name: 'Review' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm completion' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Retry only the document')
    expect(remindersApi.complete).toHaveBeenCalledTimes(1)
    expect(onSaved).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Retry document' }))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(remindersApi.complete).toHaveBeenCalledTimes(1)
    expect(recordsApi.uploadRecordAttachment).toHaveBeenCalledTimes(2)
    expect(remindersApi.addEvidence).toHaveBeenCalledTimes(1)
  })
})

function baseReminder(overrides: Partial<Reminder> = {}): Reminder {
  return {
    id: 'reminder-1', title: 'Vaccination', category: 'Health', due_date: '2026-09-18', repeat: 'None',
    priority: 'High', notes: null, reminder_lead_value: null, reminder_lead_unit: null, reminder_time: null,
    reminder_type: 'generic', birthday_details: null, renewal_details: null, maintenance_details: null,
    completed: false, alert_dismissed_until: null, alert_last_seen_at: null, alert_last_action_at: null,
    alert_snoozed_until: null, snoozed_until: null, archived_at: null, status: 'Scheduled',
    effective_attention_date: '2026-09-18', created_at: '2026-07-18T12:00:00Z', updated_at: '2026-07-18T12:00:00Z',
    completed_at: null, current_occurrence_id: 'occurrence-1', lifecycle_events: [], linked_records: [], next_due_date: null,
    computed_label: null, birthday_age_label: null, renewal_status_label: null, renewal_window_label: null,
    maintenance_status_label: null, calendar_sync_enabled: false, calendar_provider: null, calendar_id: null,
    calendar_last_synced_at: null, calendar_sync_status: 'not_synced', calendar_sync_error: null,
    ...overrides,
  }
}

function record(): LifeRecord {
  return {
    id: 'record-1', record_type: 'pet', title: 'Baxter', subtitle: null, category: 'Pets', owner_name: null,
    provider_or_brand: null, start_date: null, issue_date: null, expiration_date: null, purchase_date: null,
    renewal_date: null, location_hint: null, notes: null, tags: [], status: 'active', has_protected_data: false,
    protected_field_names: [], dynamic_fields: [],
    created_at: '2026-07-18T12:00:00Z', updated_at: '2026-07-18T12:00:00Z',
  }
}
