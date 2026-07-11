import { getAuthorizationHeaders } from '../auth/session'
import type { LifeRecord, RecordInput } from '../types/record'

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

export const recordsApi = {
  list: (includeArchived = false) =>
    request<LifeRecord[]>(`/records${includeArchived ? '?include_archived=true' : ''}`),

  get: (id: string) => request<LifeRecord>(`/records/${id}`),

  create: (input: RecordInput) =>
    request<LifeRecord>('/records', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  update: (id: string, input: RecordInput) =>
    request<LifeRecord>(`/records/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    }),

  archive: (id: string) =>
    request<LifeRecord>(`/records/${id}/archive`, {
      method: 'POST',
    }),

  restore: (id: string) =>
    request<LifeRecord>(`/records/${id}/restore`, {
      method: 'POST',
    }),

  remove: (id: string) =>
    request<void>(`/records/${id}`, {
      method: 'DELETE',
    }),
}
