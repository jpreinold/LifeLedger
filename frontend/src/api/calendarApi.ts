import { apiRequest as request } from './apiClient'

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
