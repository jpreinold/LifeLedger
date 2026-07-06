import type { Reminder, ReminderAlert, ReminderInput } from '../types/reminder'
import { getAuthorizationHeaders } from '../auth/session'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  const authorizationHeaders = await getAuthorizationHeaders()

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
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

  alerts: () => request<ReminderAlert[]>('/alerts'),

  get: (id: string) => request<Reminder>(`/reminders/${id}`),

  create: (input: ReminderInput) =>
    request<Reminder>('/reminders', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  update: (id: string, input: Partial<ReminderInput>) =>
    request<Reminder>(`/reminders/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    }),

  complete: (id: string) =>
    request<Reminder>(`/reminders/${id}/complete`, {
      method: 'POST',
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

  remove: (id: string) =>
    request<void>(`/reminders/${id}`, {
      method: 'DELETE',
    }),
}
