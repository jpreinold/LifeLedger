import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Capture, CaptureDetail } from '../../types/capture'
import { CaptureInbox } from './CaptureInbox'
import { QuickCapture } from './QuickCapture'
import { capturesApi } from '../../api/capturesApi'

vi.mock('../../api/capturesApi', () => ({
  capturesApi: {
    submit: vi.fn(), list: vi.fn(), get: vi.fn(), retry: vi.fn(), dismiss: vi.fn(),
    approve: vi.fn(), reject: vi.fn(), clarify: vi.fn(), updateProposal: vi.fn(),
  },
}))

const capture: Capture = {
  capture_id: 'capture-internal-id', source: 'lifeledger_web', input_type: 'text',
  original_text: "It's my friend Alex's birthday.", captured_at: '2026-07-18T16:00:00Z',
  client_timestamp: null, timezone: 'UTC', locale: 'en-US', status: 'ready_for_review',
  interpreter: 'deterministic', active_proposal_id: 'proposal-internal-id', clarification_session_id: null,
  interpretation_summary: 'Create Alex as a Person and add an annual birthday reminder.', relevant_action: 'Create Alex as a Person.',
  failure_category: null, safe_failure_message: null, attempt_count: 1,
}

const detail: CaptureDetail = {
  capture,
  proposal: {
    proposal_id: 'proposal-internal-id', capture_id: capture.capture_id, status: 'ready_for_review',
    proposed_actions: [{ action_id: 'action-internal-id', action_type: 'create_item', fields: { title: 'Alex', details: {} }, explanation: 'Create Alex as a Person.', risk_level: 'medium', confirmation_requirement: 'always' }],
    action_results: [], ambiguity_reasons: [], conflict_warnings: [], missing_information: [],
    user_facing_summary: 'Create Alex as a Person and add an annual birthday reminder.',
    interpreter: 'deterministic', expires_at: '2026-07-25T16:00:00Z',
  },
  clarification: null,
}

describe('Phase 14 Capture Inbox', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(capturesApi.list).mockResolvedValue({ items: [capture], next_cursor: null })
    vi.mocked(capturesApi.get).mockResolvedValue(detail)
  })

  it('creates plain-text capture and shows protected-data guidance', async () => {
    vi.mocked(capturesApi.submit).mockResolvedValue(detail)
    const onCaptured = vi.fn()
    render(<QuickCapture onCaptured={onCaptured} />)
    expect(screen.getByText(/Don’t enter passwords, codes, payment-card details/i)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Capture text'), 'Remind me tomorrow at 4 to call Mom.')
    await userEvent.click(screen.getByRole('button', { name: 'Save to Inbox' }))
    await waitFor(() => expect(capturesApi.submit).toHaveBeenCalledWith('Remind me tomorrow at 4 to call Mom.'))
    expect(onCaptured).toHaveBeenCalledWith(detail)
  })

  it('groups original text in the Inbox and opens review in user-facing language', async () => {
    render(<CaptureInbox initialDetail={detail} />)
    expect(await screen.findByText('Ready to review')).toBeInTheDocument()
    expect(screen.getAllByText("It's my friend Alex's birthday.").length).toBeGreaterThan(0)
    expect(screen.getByText('Create Alex as a Person.')).toBeInTheDocument()
    expect(screen.queryByText('proposal-internal-id')).not.toBeInTheDocument()
    expect(screen.queryByText('action-internal-id')).not.toBeInTheDocument()
    expect(screen.queryByText(/"action_type"/)).not.toBeInTheDocument()
  })

  it('requires an explicit confirm and reports durable action results', async () => {
    const completed: CaptureDetail = {
      ...detail,
      capture: { ...capture, status: 'completed' },
      proposal: {
        ...detail.proposal!, status: 'completed',
        action_results: [{ action_id: 'action-internal-id', action_type: 'create_item', status: 'completed', resulting_entity_id: 'person-id', safe_summary: 'Created Alex.', idempotent_replay: false, reconciliation_required: false, correction_available: true }],
      },
    }
    vi.mocked(capturesApi.approve).mockResolvedValue(completed.proposal!)
    vi.mocked(capturesApi.get).mockResolvedValue(completed)
    render(<CaptureInbox initialDetail={detail} />)
    await userEvent.click(screen.getByRole('button', { name: 'Confirm changes' }))
    await waitFor(() => expect(capturesApi.approve).toHaveBeenCalledWith('proposal-internal-id'))
    expect(await screen.findByText('Created Alex.')).toBeInTheDocument()
  })

  it('shows failed captures as recoverable and never puts capture text in a URL', async () => {
    const failed = { ...capture, status: 'failed' as const, safe_failure_message: 'AI-assisted interpretation is disabled.' }
    vi.mocked(capturesApi.list).mockResolvedValue({ items: [failed], next_cursor: null })
    vi.mocked(capturesApi.get).mockResolvedValue({ capture: failed, proposal: null, clarification: null })
    vi.mocked(capturesApi.retry).mockResolvedValue(detail)
    render(<CaptureInbox />)
    const row = await screen.findByRole('button', { name: /friend Alex/i })
    await userEvent.click(row)
    expect(await screen.findByText('AI-assisted interpretation is disabled.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Retry/i }))
    await waitFor(() => expect(capturesApi.retry).toHaveBeenCalledWith('capture-internal-id'))
    expect(window.location.href).not.toContain('Alex')
  })

  it('presents focused clarification choices without exposing IDs', async () => {
    const clarification: CaptureDetail = {
      ...detail,
      capture: { ...capture, status: 'needs_clarification' },
      proposal: { ...detail.proposal!, status: 'needs_clarification' },
      clarification: {
        clarification_id: 'clarification-id', proposal_id: 'proposal-internal-id', status: 'open', answers: {}, expires_at: '2026-07-25T16:00:00Z',
        questions: [{ question_id: 'question-id', prompt: 'Which Alex did you mean?', allow_free_text: false, options: [{ option_id: 'option-private-a', label: 'Alex Morgan' }, { option_id: 'option-private-b', label: 'Alex Smith' }] }],
      },
    }
    vi.mocked(capturesApi.clarify).mockResolvedValue(detail)
    render(<CaptureInbox initialDetail={clarification} />)
    fireEvent.click(screen.getByRole('button', { name: 'Alex Morgan' }))
    await waitFor(() => expect(capturesApi.clarify).toHaveBeenCalledWith('proposal-internal-id', { 'question-id': 'option-private-a' }))
    expect(screen.queryByText('option-private-a')).not.toBeInTheDocument()
  })

  it('submits a bounded free-text clarification without adding it to the URL', async () => {
    const clarification: CaptureDetail = {
      ...detail,
      capture: { ...capture, status: 'needs_clarification' },
      proposal: { ...detail.proposal!, status: 'needs_clarification' },
      clarification: {
        clarification_id: 'clarification-id', proposal_id: 'proposal-internal-id', status: 'open', answers: {}, expires_at: '2026-07-25T16:00:00Z',
        questions: [{ question_id: 'question-id', prompt: 'What date should the reminder use?', allow_free_text: true, options: [] }],
      },
    }
    vi.mocked(capturesApi.clarify).mockResolvedValue(detail)
    render(<CaptureInbox initialDetail={clarification} />)
    expect(screen.getByText('Your answer')).toBeVisible()
    await userEvent.type(screen.getByLabelText('Your answer'), 'August 1')
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(capturesApi.clarify).toHaveBeenCalledWith('proposal-internal-id', { 'question-id': 'August 1' }))
    expect(window.location.href).not.toContain('August')
  })

  it('moves focus into review and does not persist sensitive capture text in browser storage', async () => {
    localStorage.clear()
    sessionStorage.clear()
    vi.mocked(capturesApi.submit).mockResolvedValue(detail)
    render(<QuickCapture onCaptured={() => {}} />)
    await userEvent.type(screen.getByLabelText('Capture text'), 'My private reminder text')
    await userEvent.click(screen.getByRole('button', { name: 'Save to Inbox' }))
    expect(JSON.stringify({ ...localStorage })).not.toContain('private reminder')
    expect(JSON.stringify({ ...sessionStorage })).not.toContain('private reminder')

    render(<CaptureInbox initialDetail={detail} />)
    await waitFor(() => expect(screen.getByRole('heading', { name: capture.original_text })).toHaveFocus())
  })

  it('edits a supported proposal value before approval without exposing field keys', async () => {
    vi.mocked(capturesApi.updateProposal).mockResolvedValue(detail.proposal!)
    render(<CaptureInbox initialDetail={detail} />)
    await userEvent.click(screen.getByRole('button', { name: 'Edit proposed change' }))
    const name = screen.getByLabelText('Display name')
    await userEvent.clear(name)
    await userEvent.type(name, 'Alexandra')
    await userEvent.click(screen.getByRole('button', { name: 'Save adjustment' }))
    await waitFor(() => expect(capturesApi.updateProposal).toHaveBeenCalledWith(
      'proposal-internal-id', 'action-internal-id', { title: 'Alexandra' },
    ))
    expect(screen.queryByText('title')).not.toBeInTheDocument()
  })
})
