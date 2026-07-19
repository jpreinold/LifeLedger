import { apiRequest as request } from './apiClient'

export interface PushConfiguration {
  configured: boolean
}

export interface PushStatus {
  configured: boolean
  active_subscription_count: number
  last_success_at: string | null
  last_failure_at: string | null
  failure_count: number
  digest_enabled: boolean
  digest_time: string
  timezone: string | null
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

export interface PushTestResult {
  sent: number
}

export const pushApi = {
  getConfig: () => request<PushConfiguration>('/push/config'),

  getStatus: () => request<PushStatus>('/push/status'),

  sendTestPush: () =>
    request<PushTestResult>('/push/test', {
      method: 'POST',
    }),

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
