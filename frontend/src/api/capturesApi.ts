import { apiRequest } from './apiClient'
import type {
  AISettingsResponse,
  ActionProposal,
  Capture,
  CaptureDetail,
  CapturePage,
  AIUsageSummary,
} from '../types/capture'

function idempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `capture-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const capturesApi = {
  async create(originalText: string): Promise<Capture> {
    return apiRequest('/captures', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey() },
      body: JSON.stringify({
        original_text: originalText,
        client_timestamp: new Date().toISOString(),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
        locale: navigator.language || 'en-US',
        source: 'lifeledger_web',
      }),
    })
  },
  list(cursor?: string | null): Promise<CapturePage> {
    const query = new URLSearchParams({ limit: '50' })
    if (cursor) query.set('cursor', cursor)
    return apiRequest(`/captures?${query.toString()}`)
  },
  get(captureId: string): Promise<CaptureDetail> {
    return apiRequest(`/captures/${encodeURIComponent(captureId)}`)
  },
  updateProposal(proposalId: string, actionId: string, changes: Record<string, unknown>): Promise<ActionProposal> {
    return apiRequest(`/proposals/${encodeURIComponent(proposalId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ action_id: actionId, changes }),
    })
  },
  interpret(captureId: string): Promise<CaptureDetail> {
    return apiRequest(`/captures/${encodeURIComponent(captureId)}/interpret`, { method: 'POST' })
  },
  async submit(originalText: string): Promise<CaptureDetail> {
    const capture = await this.create(originalText)
    return this.interpret(capture.capture_id)
  },
  retry(captureId: string): Promise<CaptureDetail> {
    return apiRequest(`/captures/${encodeURIComponent(captureId)}/retry`, { method: 'POST' })
  },
  dismiss(captureId: string): Promise<Capture> {
    return apiRequest(`/captures/${encodeURIComponent(captureId)}/dismiss`, { method: 'POST' })
  },
  approve(proposalId: string): Promise<ActionProposal> {
    return apiRequest(`/proposals/${encodeURIComponent(proposalId)}/approve`, { method: 'POST' })
  },
  reject(proposalId: string): Promise<ActionProposal> {
    return apiRequest(`/proposals/${encodeURIComponent(proposalId)}/reject`, { method: 'POST' })
  },
  clarify(proposalId: string, answers: Record<string, string>): Promise<CaptureDetail> {
    return apiRequest(`/proposals/${encodeURIComponent(proposalId)}/clarifications`, {
      method: 'POST',
      body: JSON.stringify({ answers }),
    })
  },
  usage(): Promise<AIUsageSummary> {
    return apiRequest('/ai-usage')
  },
  settings(): Promise<AISettingsResponse> {
    return apiRequest('/ai-settings')
  },
  updateSettings(input: Partial<AISettingsResponse['settings']>): Promise<AISettingsResponse> {
    return apiRequest('/ai-settings', { method: 'PUT', body: JSON.stringify(input) })
  },
}
