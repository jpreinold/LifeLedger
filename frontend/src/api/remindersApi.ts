import type { Reminder, ReminderAlert, ReminderInput } from '../types/reminder'
import type { CompleteResponsibilityInput, LifecycleReconciliationResult, RenewResponsibilityInput, ResponsibilityEvent, ResponsibilityHistoryPage } from '../types/responsibilityHistory'
import { getAuthorizationHeaders } from '../auth/session'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  const authorizationHeaders = await getAuthorizationHeaders()

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      cache: 'no-store',
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...authorizationHeaders,
        ...options.headers,
      },
    })
  } catch {
    throw new Error('Unable to reach the LifeLedger API. Make sure the Python backend is running.')
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`

    try {
      const body = await response.json()
      message = typeof body.detail === 'string' ? body.detail : message
    } catch {
      message = response.statusText || message
    }

    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export const remindersApi = {
  list: () => request<Reminder[]>('/reminders'),

  get: (id: string) => request<Reminder>(`/reminders/${id}`),

  alerts: () => request<ReminderAlert[]>('/alerts'),

  create: (input: ReminderInput, idempotencyKey?: string, itemId?: string) =>
    request<Reminder>(`/reminders${itemId ? `?item_id=${encodeURIComponent(itemId)}` : ''}`, {
      method: 'POST',
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
      body: JSON.stringify(input),
    }),

  update: (id: string, input: Partial<ReminderInput>) =>
    request<Reminder>(`/reminders/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    }),

  complete: (id: string, input?: CompleteResponsibilityInput, idempotencyKey?: string) =>
    request<Reminder>(`/reminders/${id}/complete`, {
      method: 'POST',
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
      body: input ? JSON.stringify(input) : undefined,
    }),


  snooze: (id: string, snoozedUntil: string) =>
    request<Reminder>(`/reminders/${id}/snooze`, {
      method: 'POST',
      body: JSON.stringify({ snoozed_until: snoozedUntil }),
    }),

  clearSnooze: (id: string) =>
    request<Reminder>(`/reminders/${id}/snooze/clear`, {
      method: 'POST',
    }),

  renew: (id: string, input: RenewResponsibilityInput, idempotencyKey?: string) =>
    request<Reminder>(`/reminders/${id}/renew`, {
      method: 'POST',
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
      body: JSON.stringify(input),
    }),

  reopen: (id: string, occurrenceId: string | null, idempotencyKey?: string) =>
    request<Reminder>(`/reminders/${id}/reopen${occurrenceId ? `?occurrence_id=${encodeURIComponent(occurrenceId)}` : ''}`, {
      method: 'POST',
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
    }),

  history: (id: string, cursor?: string | null, limit = 10) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (cursor) params.set('cursor', cursor)
    return request<ResponsibilityHistoryPage>(`/reminders/${id}/history?${params.toString()}`)
  },

  reconcileHistory: (id: string, dryRun = false) =>
    request<LifecycleReconciliationResult>(`/reminders/${id}/history/reconcile?dry_run=${dryRun}`, {
      method: 'POST',
    }),

  addEvidence: (id: string, input: { record_id: string; document_id: string; occurrence_id: string | null; related_event_id: string }, idempotencyKey?: string) =>
    request<ResponsibilityEvent>(`/reminders/${id}/history/evidence`, {
      method: 'POST',
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
      body: JSON.stringify(input),
    }),

  dismissAlert: (id: string) =>
    request<Reminder>(`/reminders/${id}/alert/dismiss`, {
      method: 'POST',
    }),

  snoozeAlert: (id: string, snoozedUntil?: string) =>
    request<Reminder>(`/reminders/${id}/alert/snooze`, {
      method: 'POST',
      body: snoozedUntil ? JSON.stringify({ snoozed_until: snoozedUntil }) : undefined,
    }),

  enableCalendarSync: (id: string) =>
    request<Reminder>(`/reminders/${id}/calendar-sync/enable`, {
      method: 'POST',
    }),

  disableCalendarSync: (id: string) =>
    request<Reminder>(`/reminders/${id}/calendar-sync/disable`, {
      method: 'POST',
    }),

  remove: (id: string) =>
    request<void>(`/reminders/${id}`, {
      method: 'DELETE',
    }),
}
