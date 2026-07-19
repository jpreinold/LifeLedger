import { expect, test } from '@playwright/test'

const now = '2026-07-18T12:00:00.000Z'
const occurrenceId = 'occurrence-2026'
const createdEvent = historyEvent({
  event_id: 'event-created',
  event_type: 'responsibility_created',
  next_due_date: '2026-09-18',
})

test('completes one cycle and loads friendly durable history on demand', async ({ page }) => {
  let completed = false
  const events = [createdEvent]
  const reminder = reminderResponse()

  await page.route('http://localhost:8000/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/reminders/reminder-1/complete' && request.method() === 'POST') {
      if (!completed) {
        const payload = request.postDataJSON() as { completed_on: string; note: string | null }
        completed = true
        Object.assign(reminder, {
          completed: true,
          completed_at: `${payload.completed_on}T00:00:00Z`,
          status: 'Completed',
          last_lifecycle_event_id: 'event-completed',
        })
        events.unshift(historyEvent({
          event_id: 'event-completed',
          event_type: 'completed',
          effective_date: payload.completed_on,
          note: payload.note,
          previous_due_date: '2026-09-18',
          occurrence_id: occurrenceId,
        }))
      }
      await route.fulfill({ json: reminder })
      return
    }
    if (path === '/reminders/reminder-1/history') {
      await route.fulfill({ json: { items: events, next_cursor: null } })
      return
    }
    if (path === '/reminders') {
      await route.fulfill({ json: [reminder] })
      return
    }
    if (path === '/alerts' || path === '/records') {
      await route.fulfill({ json: [] })
      return
    }
    if (path === '/preferences/digest') {
      await route.fulfill({ json: { digest_enabled: true, digest_time: '09:00', digest_lookahead_days: 30, timezone: 'UTC', digest_last_seen_at: null, updated_at: now } })
      return
    }
    if (path === '/integrations/google-calendar/status') {
      await route.fulfill({ json: { configured: false, connected: false, status: 'disconnected', google_account_email: null, calendar_id: null, calendar_label: null, last_error: null } })
      return
    }
    await route.fulfill({ status: 404, json: { detail: `Unhandled local E2E path: ${path}` } })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Reminders', exact: true }).click()
  const card = page.locator('.reminder-card').filter({ hasText: 'Local ledger acceptance' })
  await card.getByRole('button', { name: 'Complete' }).click()
  await expect(page.getByRole('heading', { name: 'Mark responsibility complete' })).toBeVisible()
  await page.getByLabel('Completion note Optional').fill('Vaccination record confirmed')
  await page.getByRole('button', { name: 'Review' }).click()
  await expect(page.getByText('Previous due date')).toBeVisible()
  await page.getByRole('button', { name: 'Confirm completion' }).click()

  await expect(page.getByText('Responsibility completed.')).toBeVisible()
  await page.getByRole('button', { name: /Completed/ }).first().click()
  await expect(card.getByRole('button', { name: 'Completed', exact: true })).toBeDisabled()
  await card.locator('.reminder-card-body-button').click()
  await page.getByRole('button', { name: 'Show history' }).click()
  await expect(page.getByRole('heading', { name: 'History' })).toBeVisible()
  await expect(page.getByText('Vaccination record confirmed')).toBeVisible()
  await expect(page.getByText('responsibility_created')).toHaveCount(0)
})

test('captures and reviews a deterministic proposal at 320px', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  const capture = {
    capture_id: 'capture-1', source: 'lifeledger_web', input_type: 'text',
    original_text: 'Remind me tomorrow at 4 to call Mom.', captured_at: now,
    client_timestamp: now, timezone: 'UTC', locale: 'en-US', status: 'ready_for_review',
    interpreter: 'deterministic', active_proposal_id: 'proposal-1', clarification_session_id: null,
    interpretation_summary: 'Create one reminder for your request.', relevant_action: 'Create a reminder to call Mom.',
    failure_category: null, safe_failure_message: null, attempt_count: 1,
  }
  const detail = {
    capture,
    proposal: {
      proposal_id: 'proposal-1', capture_id: 'capture-1', status: 'ready_for_review',
      proposed_actions: [{ action_id: 'action-1', action_type: 'create_responsibility', fields: { title: 'Call Mom', due_date: '2026-07-20', reminder_time: '16:00' }, explanation: 'Create a reminder to call Mom.', risk_level: 'medium', confirmation_requirement: 'always' }],
      action_results: [], ambiguity_reasons: [], conflict_warnings: [], missing_information: [],
      user_facing_summary: 'Create one reminder for your request.', interpreter: 'deterministic', expires_at: '2026-07-25T12:00:00.000Z',
    },
    clarification: null,
  }

  await page.route('http://localhost:8000/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/captures' && request.method() === 'POST') return route.fulfill({ json: capture })
    if (path === '/captures/capture-1/interpret' && request.method() === 'POST') return route.fulfill({ json: detail })
    if (path === '/captures' && request.method() === 'GET') return route.fulfill({ json: { items: [capture], next_cursor: null } })
    if (path === '/reminders' || path === '/alerts' || path === '/records') return route.fulfill({ json: [] })
    if (path === '/preferences/digest') return route.fulfill({ json: { digest_enabled: true, digest_time: '09:00', digest_lookahead_days: 30, timezone: 'UTC', digest_last_seen_at: null, updated_at: now } })
    if (path === '/integrations/google-calendar/status') return route.fulfill({ json: { configured: false, connected: false, status: 'disconnected', google_account_email: null, calendar_id: null, calendar_label: null, last_error: null } })
    return route.fulfill({ status: 404, json: { detail: `Unhandled local E2E path: ${path}` } })
  })

  await page.goto('/')
  await page.getByLabel('Capture text').fill(capture.original_text)
  await page.getByRole('button', { name: 'Save to Inbox' }).click()
  await expect(page.locator('#capture-inbox-heading')).toBeVisible()
  await expect(page.getByRole('heading', { name: capture.original_text })).toBeFocused()
  await expect(page.getByText('Create a reminder to call Mom.').first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Confirm changes' })).toBeVisible()
  expect(page.url()).not.toContain('Mom')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

function reminderResponse() {
  return {
    id: 'reminder-1', title: 'Local ledger acceptance', category: 'Health', due_date: '2026-09-18', repeat: 'None',
    priority: 'High', notes: null, reminder_lead_value: null, reminder_lead_unit: null, reminder_time: null,
    reminder_type: 'generic', birthday_details: null, renewal_details: null, maintenance_details: null, workflow_id: null,
    completed: false, alert_dismissed_until: null, alert_last_seen_at: null, alert_last_action_at: null,
    alert_snoozed_until: null, snoozed_until: null, archived_at: null, status: 'Scheduled',
    effective_attention_date: '2026-09-18', created_at: now, updated_at: now, completed_at: null,
    current_occurrence_id: occurrenceId, lifecycle_reconciliation_status: 'consistent', last_lifecycle_event_id: 'event-created',
    lifecycle_events: [], linked_records: [], next_due_date: null, computed_label: null, birthday_age_label: null,
    renewal_status_label: null, renewal_window_label: null, maintenance_status_label: null,
    calendar_sync_enabled: false, calendar_provider: null, calendar_id: null, calendar_last_synced_at: null,
    calendar_sync_status: 'not_synced', calendar_sync_error: null,
  }
}

function historyEvent(overrides: Record<string, unknown>) {
  return {
    event_id: 'event', reminder_id: 'reminder-1', item_id: null, occurrence_id: occurrenceId,
    event_type: 'completed', occurred_at: now, effective_date: null, previous_due_date: null, next_due_date: null,
    completed_at: null, note: null, source: 'user', schema_version: 1, created_at: now,
    responsibility_title_snapshot: 'Local ledger acceptance', item_title_snapshot: null, item_type_snapshot: null,
    related_event_id: null, reconciliation_status: 'consistent', search_sync_status: 'consistent',
    document_reference_status: 'consistent', documents: [], ...overrides,
  }
}
