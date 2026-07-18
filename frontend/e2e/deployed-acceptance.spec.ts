import { expect, request as playwrightRequest, test, type Page } from '@playwright/test'

const requiredEnvironment = [
  'E2E_BASE_URL',
  'E2E_API_BASE_URL',
  'E2E_USERNAME',
  'E2E_PASSWORD',
] as const

test('authenticated deployed responsibility, protected detail, document scan, history, and cleanup', async ({ page }) => {
  test.skip(process.env.E2E_MODE !== 'deployed', 'Run with npm run test:e2e:deployed.')
  const missing = requiredEnvironment.filter((name) => !process.env[name])
  expect(missing, `Missing deployed E2E environment variables: ${missing.join(', ')}`).toEqual([])

  const apiBase = process.env.E2E_API_BASE_URL!.replace(/\/$/, '')
  const prefix = `E2E-P12-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
  let bearerToken = ''
  let itemId = ''
  let reminderId = ''
  let documentId = ''
  const cleanupFailures: string[] = []

  const tokenPromise = new Promise<string>((resolve) => {
    page.on('request', (request) => {
      if (!request.url().startsWith(apiBase)) return
      const authorization = request.headers().authorization
      if (authorization?.startsWith('Bearer ')) resolve(authorization)
    })
  })

  await page.goto('/')
  await page.getByLabel(/email/i).fill(process.env.E2E_USERNAME!)
  await page.getByLabel(/password/i).fill(process.env.E2E_PASSWORD!)
  await page.getByRole('button', { name: /sign in/i }).click()
  bearerToken = await Promise.race([
    tokenPromise,
    page.waitForTimeout(30_000).then(() => { throw new Error('Authenticated API traffic did not begin within 30 seconds.') }),
  ])
  await expect(page.getByRole('button', { name: 'Reminders' })).toBeVisible()

  try {
    const item = await browserApi(page, apiBase, bearerToken, '/records', {
      method: 'POST',
      body: {
        record_type: 'pet',
        title: `${prefix} pet`,
        category: 'Pets',
        notes: null,
        tags: ['e2e-phase-12'],
      },
    })
    expect(item.status).toBe(201)
    itemId = item.body.id as string

    const protectedSecret = `${prefix}-protected-secret`
    const protectedResult = await browserApi(page, apiBase, bearerToken, `/records/${itemId}/protected`, {
      method: 'PUT',
      body: { sensitive_notes: protectedSecret },
    })
    expect(protectedResult.status).toBe(200)

    const reminder = await browserApi(page, apiBase, bearerToken, `/reminders?item_id=${encodeURIComponent(itemId)}`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `${prefix}:responsibility` },
      body: {
        title: `${prefix} vaccination`,
        category: 'Health',
        due_date: todayDateKey(),
        repeat: 'Yearly',
        priority: 'High',
        notes: null,
        reminder_lead_value: 2,
        reminder_lead_unit: 'weeks',
        reminder_time: '09:00',
        reminder_type: 'maintenance',
        workflow_id: 'pet_vaccination',
        maintenance_details: {
          item_name: `${prefix} pet`, maintenance_area: 'pet', last_completed_date: null,
          interval_value: 1, interval_unit: 'years', next_due_date: todayDateKey(), instructions: null,
        },
      },
    })
    expect(reminder.status).toBe(201)
    reminderId = reminder.body.id as string

    const link = await browserApi(page, apiBase, bearerToken, `/records/${itemId}/links`, {
      method: 'POST',
      body: { target_type: 'reminder', target_id: reminderId, relationship_type: 'reminder_for' },
    })
    expect(link.status).toBe(201)

    const completion = await browserApi(page, apiBase, bearerToken, `/reminders/${reminderId}/complete`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `${prefix}:complete` },
      body: { completed_on: todayDateKey(), occurrence_id: reminder.body.current_occurrence_id, note: `${prefix} completion note` },
    })
    expect(completion.status).toBe(200)

    const intent = await browserApi(page, apiBase, bearerToken, `/records/${itemId}/attachments/upload-intent`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `${prefix}:document` },
      body: { filename: `${prefix}.pdf`, content_type: 'application/pdf', size_bytes: allowedPdf.length },
    })
    expect(intent.status).toBe(201)
    documentId = intent.body.attachment_id as string
    const uploadContext = await playwrightRequest.newContext()
    const upload = await uploadContext.post(intent.body.upload.url as string, {
      multipart: {
        ...(intent.body.upload.fields as Record<string, string>),
        file: { name: `${prefix}.pdf`, mimeType: 'application/pdf', buffer: allowedPdf },
      },
    })
    expect(upload.ok()).toBeTruthy()
    await uploadContext.dispose()

    const completedUpload = await browserApi(page, apiBase, bearerToken, `/records/${itemId}/attachments/${documentId}/complete`, { method: 'POST' })
    expect(completedUpload.status).toBe(200)
    const evidence = await browserApi(page, apiBase, bearerToken, `/reminders/${reminderId}/history/evidence`, {
      method: 'POST',
      headers: { 'Idempotency-Key': `${prefix}:evidence` },
      body: {
        record_id: itemId,
        document_id: documentId,
        occurrence_id: reminder.body.current_occurrence_id,
        related_event_id: completion.body.last_lifecycle_event_id,
      },
    })
    expect(evidence.status).toBe(201)

    const finalStatus = await pollDocument(page, apiBase, bearerToken, itemId, documentId)
    expect(finalStatus).toBe('available')

    const exactDocument = await browserApi(page, apiBase, bearerToken, `/records/${itemId}/attachments/${documentId}/download-url`, { method: 'POST' })
    expect(exactDocument.status).toBe(200)
    expect(exactDocument.body.download_url || exactDocument.body.url).toBeTruthy()

    const ledger = await browserApi(page, apiBase, bearerToken, `/reminders/${reminderId}/history?limit=20`)
    expect(ledger.status).toBe(200)
    expect(ledger.body.items.map((entry: { event_type: string }) => entry.event_type)).toEqual(
      expect.arrayContaining(['responsibility_created', 'completed', 'supporting_document_added']),
    )
    expect(JSON.stringify(ledger.body)).not.toContain(protectedSecret)
    const normalItem = await browserApi(page, apiBase, bearerToken, `/records/${itemId}`)
    expect(JSON.stringify(normalItem.body)).not.toContain(protectedSecret)

    const unauthorized = await playwrightRequest.newContext()
    const unauthorizedResponse = await unauthorized.get(`${apiBase}/reminders`)
    expect(unauthorizedResponse.status()).toBe(401)
    await unauthorized.dispose()
  } finally {
    if (reminderId) {
      const result = await browserApi(page, apiBase, bearerToken, `/reminders/${reminderId}`, { method: 'DELETE' }).catch(() => null)
      if (!result || result.status !== 204) cleanupFailures.push(`responsibility ${reminderId}`)
    }
    if (itemId) {
      const result = await browserApi(page, apiBase, bearerToken, `/records/${itemId}`, { method: 'DELETE' }).catch(() => null)
      if (!result || result.status !== 204) cleanupFailures.push(`item ${itemId}`)
    }
  }

  expect(cleanupFailures, `Cleanup failed for: ${cleanupFailures.join(', ')}`).toEqual([])
})

async function browserApi(
  page: Page,
  apiBase: string,
  authorization: string,
  path: string,
  options: { method?: string; headers?: Record<string, string>; body?: unknown } = {},
) {
  return page.evaluate(async ({ apiBase, authorization, path, options }) => {
    const response = await fetch(`${apiBase}${path}`, {
      method: options.method ?? 'GET',
      cache: 'no-store',
      headers: {
        Authorization: authorization,
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
    let body: any = null
    if (response.status !== 204) body = await response.json()
    return { status: response.status, body }
  }, { apiBase, authorization, path, options })
}

async function pollDocument(page: Page, apiBase: string, authorization: string, itemId: string, documentId: string) {
  const deadline = Date.now() + 120_000
  while (Date.now() < deadline) {
    const response = await browserApi(page, apiBase, authorization, `/records/${itemId}/attachments`)
    const document = response.body.find((entry: { attachment_id: string }) => entry.attachment_id === documentId)
    if (document?.status === 'available' || document?.status === 'rejected' || document?.status === 'scan_failed') return document.status as string
    await page.waitForTimeout(3_000)
  }
  throw new Error('Document scan did not reach a terminal state within 120 seconds.')
}

function todayDateKey() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

const allowedPdf = Buffer.from(
  '%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF',
)
