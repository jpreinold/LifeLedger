import { getAuthorizationHeaders } from '../auth/session'
import type { DigestPreferences, DigestPreferencesUpdate } from '../types/preferences'

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

  return response.json() as Promise<T>
}

export const preferencesApi = {
  getDigest: () => request<DigestPreferences>('/preferences/digest'),

  updateDigest: (input: DigestPreferencesUpdate) =>
    request<DigestPreferences>('/preferences/digest', {
      method: 'PUT',
      body: JSON.stringify(input),
    }),
}
