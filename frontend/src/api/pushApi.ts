import { getAuthorizationHeaders } from '../auth/session'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export interface PushConfiguration {
  configured: boolean
}

export interface PushSubscriptionSummary {
  subscription_id: string
  endpoint: string
  user_agent: string | null
  created_at: string
  updated_at: string
  disabled_at: string | null
  last_success_at: string | null
  last_failure_at: string | null
  failure_count: number
}

export interface PushSubscriptionInput {
  endpoint: string
  keys: {
    p256dh: string
    auth: string
  }
  user_agent?: string
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

export const pushApi = {
  getConfig: () => request<PushConfiguration>('/push/config'),

  listSubscriptions: () => request<PushSubscriptionSummary[]>('/push/subscriptions'),

  saveSubscription: (input: PushSubscriptionInput) =>
    request<PushSubscriptionSummary>('/push/subscriptions', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  removeSubscription: (subscriptionId: string) =>
    request<void>(`/push/subscriptions/${subscriptionId}`, {
      method: 'DELETE',
    }),
}
