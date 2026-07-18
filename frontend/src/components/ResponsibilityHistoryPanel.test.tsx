import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { recordsApi } from '../api/recordsApi'
import { remindersApi } from '../api/remindersApi'
import type { ResponsibilityEvent } from '../types/responsibilityHistory'
import ResponsibilityHistoryPanel from './ResponsibilityHistoryPanel'

vi.mock('../api/remindersApi', () => ({ remindersApi: { history: vi.fn(), reconcileHistory: vi.fn() } }))
vi.mock('../api/recordsApi', () => ({ recordsApi: { activity: vi.fn() } }))

const completed = event({
  event_id: 'completed',
  event_type: 'completed',
  effective_date: '2026-09-18',
  next_due_date: '2027-09-18',
  note: 'Annual visit completed',
})

describe('ResponsibilityHistoryPanel', () => {
  beforeEach(() => vi.resetAllMocks())

  it('loads reminder history incrementally with friendly labels and private notes', async () => {
    vi.mocked(remindersApi.history)
      .mockResolvedValueOnce({ items: [completed], next_cursor: 'page-2' })
      .mockResolvedValueOnce({ items: [event({ event_id: 'created', event_type: 'responsibility_created' })], next_cursor: null })

    render(<ResponsibilityHistoryPanel entityId="reminder-1" mode="reminder" />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading history')
    expect(await screen.findByText('Annual visit completed')).toBeVisible()
    expect(screen.getByText('Next due Sep 18, 2027.')).toBeVisible()
    expect(screen.queryByText('responsibility_created')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Load more' }))
    expect(await screen.findByText('Responsibility created')).toBeVisible()
    expect(remindersApi.history).toHaveBeenNthCalledWith(2, 'reminder-1', 'page-2')
  })

  it('shows scanning and deleted evidence accurately', async () => {
    vi.mocked(remindersApi.history).mockResolvedValue({
      items: [
        event({
          event_id: 'pending', event_type: 'supporting_document_added',
          documents: [{ document_id: 'doc-1', record_id: 'record-1', display_name: 'receipt.pdf', status: 'scanning', available: false }],
        }),
        event({
          event_id: 'deleted', event_type: 'supporting_document_added',
          documents: [{ document_id: 'doc-2', record_id: 'record-1', display_name: 'Document no longer available', status: 'unavailable', available: false }],
        }),
      ],
      next_cursor: null,
    })

    render(<ResponsibilityHistoryPanel entityId="reminder-1" mode="reminder" />)
    expect(await screen.findByText(/receipt\.pdf — Scan pending/)).toBeVisible()
    expect(screen.getByText(/Document no longer available — Document no longer available/)).toBeVisible()
  })

  it('aggregates item activity at mobile width and opens the connected responsibility', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 320 })
    vi.mocked(recordsApi.activity).mockResolvedValue({ items: [completed], next_cursor: null })
    const onOpenReminder = vi.fn()

    render(<ResponsibilityHistoryPanel entityId="record-1" mode="item" onOpenReminder={onOpenReminder} />)
    const responsibility = await screen.findByRole('button', { name: 'Vaccination' })
    await userEvent.click(responsibility)
    expect(onOpenReminder).toHaveBeenCalledWith('reminder-1')
    expect(recordsApi.activity).toHaveBeenCalledWith('record-1', undefined)
  })

  it('surfaces and safely retries persisted reconciliation work', async () => {
    vi.mocked(remindersApi.history)
      .mockResolvedValueOnce({ items: [event({ reconciliation_status: 'needs_attention' })], next_cursor: null })
      .mockResolvedValueOnce({ items: [event({ reconciliation_status: 'consistent' })], next_cursor: null })
    vi.mocked(remindersApi.reconcileHistory).mockResolvedValue({
      reminder_id: 'reminder-1', dry_run: false, inspected: 1, repaired: 1, remaining: 0, results: [],
    })

    render(<ResponsibilityHistoryPanel entityId="reminder-1" mode="reminder" />)
    await userEvent.click(await screen.findByRole('button', { name: 'Retry updates' }))
    expect(remindersApi.reconcileHistory).toHaveBeenCalledWith('reminder-1')
    await screen.findByText('Completed')
    expect(screen.queryByRole('button', { name: 'Retry updates' })).not.toBeInTheDocument()
  })
})

function event(overrides: Partial<ResponsibilityEvent>): ResponsibilityEvent {
  return {
    event_id: 'event-1', reminder_id: 'reminder-1', item_id: 'record-1', occurrence_id: 'occurrence-1',
    event_type: 'completed', occurred_at: '2026-09-18T12:00:00Z', effective_date: null,
    previous_due_date: '2026-09-18', next_due_date: null, completed_at: null, note: null,
    source: 'user', schema_version: 1, created_at: '2026-09-18T12:00:00Z',
    responsibility_title_snapshot: 'Vaccination', item_title_snapshot: 'Baxter', item_type_snapshot: 'pet',
    related_event_id: null, reconciliation_status: 'consistent', search_sync_status: 'consistent',
    document_reference_status: 'consistent', documents: [], ...overrides,
  }
}
