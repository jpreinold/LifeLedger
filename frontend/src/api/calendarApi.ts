import { getAuthorizationHeaders } from '../auth/session'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export type GoogleCalendarConnectionStatus = 'connected' | 'disconnected' | 'needs_reconnect'

export interface GoogleCalendarStatus {
  configured: boolean
  connected: boolean
  status: GoogleCalendarConnectionStatus
  google_account_email: string | null
  calendar_id: string | null
  calendar_label: string | null
  last_error: string | null
}

export interface GoogleCalendarOption {
  id: string
  label: string
  primary: boolean
  access_role: string
  selected: boolean
}

export interface GoogleCalendarConnectResult {
  authorization_url: string
}

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

export const calendarApi = {
  getStatus: () => request<GoogleCalendarStatus>('/integrations/google-calendar/status'),

  listCalendars: () => request<GoogleCalendarOption[]>('/integrations/google-calendar/calendars'),

  selectCalendar: (input: { calendar_id: string }) =>
    request<GoogleCalendarStatus>('/integrations/google-calendar/calendar', {
      method: 'PUT',
      body: JSON.stringify(input),
    }),

  connect: () =>
    request<GoogleCalendarConnectResult>('/integrations/google-calendar/connect', {
      method: 'POST',
    }),

  callback: (input: { code: string; state: string }) =>
    request<GoogleCalendarStatus>('/integrations/google-calendar/callback', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  disconnect: () =>
    request<void>('/integrations/google-calendar/disconnect', {
      method: 'DELETE',
    }),
}
