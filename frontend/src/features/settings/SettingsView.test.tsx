import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { accountApi } from '../../api/accountApi'
import { calendarApi } from '../../api/calendarApi'
import { pushApi } from '../../api/pushApi'
import { defaultDigestPreferences } from '../../types/preferences'
import { SettingsView } from './SettingsView'


vi.mock('../../api/accountApi', () => ({
  accountApi: {
    getStatus: vi.fn(),
    createExport: vi.fn(),
    getExport: vi.fn(),
    createDownload: vi.fn(),
    requestDeletion: vi.fn(),
    getDeletion: vi.fn(),
  },
}))

vi.mock('../../api/calendarApi', () => ({
  calendarApi: {
    connect: vi.fn(),
    listCalendars: vi.fn(),
    selectCalendar: vi.fn(),
    disconnect: vi.fn(),
    getStatus: vi.fn(),
  },
}))

vi.mock('../../api/pushApi', () => ({
  pushApi: {
    getStatus: vi.fn(),
    listSubscriptions: vi.fn(),
    saveSubscription: vi.fn(),
    removeSubscription: vi.fn(),
    sendTestPush: vi.fn(),
  },
}))

describe('SettingsView feature boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(accountApi.getStatus).mockResolvedValue({ state: 'active', current_operation: null })
    vi.mocked(calendarApi.listCalendars).mockResolvedValue([])
    vi.mocked(pushApi.getStatus).mockResolvedValue({
      configured: false,
      active_subscription_count: 0,
      last_success_at: null,
      last_failure_at: null,
      failure_count: 0,
      digest_enabled: false,
      digest_time: '08:00',
      timezone: 'America/New_York',
    })
    vi.mocked(pushApi.listSubscriptions).mockResolvedValue([])
  })

  it('keeps account, calendar, push, and digest settings in one focused surface', async () => {
    render(
      <SettingsView
        calendarStatus={{
          configured: true,
          connected: false,
          status: 'disconnected',
          google_account_email: null,
          calendar_id: null,
          calendar_label: null,
          last_error: null,
        }}
        calendarStatusError={null}
        digestPreferences={defaultDigestPreferences()}
        isCalendarStatusLoading={false}
        isDigestPreferencesLoading={false}
        isSavingDigestPreferences={false}
        userLabel="Dedicated user"
        onCalendarStatusRefresh={vi.fn(async () => undefined)}
        onCalendarStatusUpdate={vi.fn()}
        onSignOut={vi.fn()}
        onUpdateDigestPreferences={vi.fn(async () => true)}
      />,
    )

    expect(await screen.findByRole('heading', { name: 'Data and account' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Google Calendar' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /push notifications/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument()
  })
})
