import { getAuthorizationHeaders } from '../auth/session'
import type { LinkCreateRequest, LinkedItemsResponse, LinkedItem } from '../types/linkedItem'

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

export const linkedItemsApi = {
  listRecordLinks: (recordId: string) => request<LinkedItemsResponse>(`/records/${recordId}/links`),

  createRecordLink: (recordId: string, input: LinkCreateRequest) =>
    request<LinkedItem>(`/records/${recordId}/links`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  deleteRecordLink: (recordId: string, linkId: string) =>
    request<void>(`/records/${recordId}/links/${linkId}`, {
      method: 'DELETE',
    }),

  listReminderLinks: (reminderId: string) => request<LinkedItemsResponse>(`/reminders/${reminderId}/links`),

  deleteReminderLink: (reminderId: string, linkId: string) =>
    request<void>(`/reminders/${reminderId}/links/${linkId}`, {
      method: 'DELETE',
    }),
}
