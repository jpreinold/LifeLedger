import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { capturesApi } from '../../api/capturesApi'
import { AISettingsSection } from './AISettingsSection'

vi.mock('../../api/capturesApi', () => ({
  capturesApi: {
    settings: vi.fn(),
    updateSettings: vi.fn(),
  },
}))

describe('AI settings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(capturesApi.settings).mockResolvedValue({
      settings: {
        ai_enabled: true,
        monthly_budget_usd: 5,
        daily_request_limit: 50,
        deterministic_first: true,
        allow_model_escalation: true,
      },
      usage: {
        billing_month: '2026-07',
        estimated_cost_usd: 1.25,
        request_count: 4,
        monthly_budget_usd: 5,
        remaining_budget_usd: 3.75,
        daily_request_count: 2,
        daily_request_limit: 50,
      },
      provider_configured: false,
      default_model: 'gpt-5.6-luna',
      escalation_model: 'gpt-5.6-terra',
    })
  })

  it('shows estimated spend, remaining budget, and provider availability', async () => {
    render(<AISettingsSection />)

    expect(await screen.findByText(/Estimated spend: \$1\.2500/)).toHaveTextContent('Remaining: $3.7500')
    expect(screen.getByText(/provider access is not configured/i)).toBeInTheDocument()
    expect(screen.getByText('2 of 50 used today')).toBeInTheDocument()
  })
})
