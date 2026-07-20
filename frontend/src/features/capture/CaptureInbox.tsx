import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronRight, CircleAlert, Inbox, RefreshCcw, Trash2, X } from 'lucide-react'

import { capturesApi } from '../../api/capturesApi'
import type { ActionProposal, Capture, CaptureDetail, CaptureStatus, ProposedAction } from '../../types/capture'
import { QuickCapture } from './QuickCapture'

interface CaptureInboxProps {
  initialDetail?: CaptureDetail | null
  onDataChanged?: () => void
  onManualOrganize?: () => void
  onOpenResult?: (actionType: string, entityId: string) => void
}

const groups: Array<{ title: string; statuses: CaptureStatus[] }> = [
  { title: 'Needs your input', statuses: ['needs_clarification'] },
  { title: 'Ready to review', statuses: ['ready_for_review'] },
  { title: 'Processing', statuses: ['new', 'interpreting', 'executing'] },
  { title: 'Could not organize', statuses: ['failed'] },
  { title: 'Recently completed', statuses: ['completed'] },
]

export function CaptureInbox({ initialDetail = null, onDataChanged, onManualOrganize, onOpenResult }: CaptureInboxProps) {
  const [captures, setCaptures] = useState<Capture[]>([])
  const [selected, setSelected] = useState<CaptureDetail | null>(initialDetail)
  const [isLoading, setIsLoading] = useState(true)
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const page = await capturesApi.list()
      setCaptures(page.items.filter((item) => item.status !== 'dismissed'))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load the Capture Inbox.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])
  useEffect(() => { if (initialDetail) setSelected(initialDetail) }, [initialDetail])

  const byGroup = useMemo(() => groups.map((group) => ({
    ...group,
    captures: captures.filter((capture) => group.statuses.includes(capture.status)),
  })), [captures])

  async function open(capture: Capture) {
    setPending(capture.capture_id)
    setError(null)
    try { setSelected(await capturesApi.get(capture.capture_id)) }
    catch (requestError) { setError(message(requestError)) }
    finally { setPending(null) }
  }

  async function retry(captureId: string) {
    setPending(captureId)
    setError(null)
    try { setSelected(await capturesApi.retry(captureId)); await load() }
    catch (requestError) { setError(message(requestError)) }
    finally { setPending(null) }
  }

  async function dismiss(captureId: string) {
    setPending(captureId)
    try {
      await capturesApi.dismiss(captureId)
      if (selected?.capture.capture_id === captureId) setSelected(null)
      await load()
    } catch (requestError) { setError(message(requestError)) }
    finally { setPending(null) }
  }

  async function approve(proposal: ActionProposal) {
    setPending(proposal.proposal_id)
    setError(null)
    try {
      await capturesApi.approve(proposal.proposal_id)
      setSelected(await capturesApi.get(proposal.capture_id))
      await load()
      onDataChanged?.()
    } catch (requestError) { setError(message(requestError)) }
    finally { setPending(null) }
  }

  async function reject(proposal: ActionProposal) {
    setPending(proposal.proposal_id)
    try {
      await capturesApi.reject(proposal.proposal_id)
      setSelected(null)
      await load()
    } catch (requestError) { setError(message(requestError)) }
    finally { setPending(null) }
  }

  async function answer(proposalId: string, questionId: string, optionId: string) {
    setPending(proposalId)
    setError(null)
    try {
      setSelected(await capturesApi.clarify(proposalId, { [questionId]: optionId }))
      await load()
    } catch (requestError) { setError(message(requestError)) }
    finally { setPending(null) }
  }

  async function edit(proposal: ActionProposal, actionId: string, changes: Record<string, unknown>): Promise<boolean> {
    setPending(proposal.proposal_id)
    setError(null)
    try {
      await capturesApi.updateProposal(proposal.proposal_id, actionId, changes)
      setSelected(await capturesApi.get(proposal.capture_id))
      await load()
      return true
    } catch (requestError) { setError(message(requestError)); return false }
    finally { setPending(null) }
  }

  return (
    <section className="capture-inbox" aria-labelledby="capture-inbox-heading">
      <header className="capture-page-header">
        <div><span className="capture-page-icon"><Inbox size={21} /></span><h2 id="capture-inbox-heading">Capture Inbox</h2></div>
        <p>Unresolved captures stay here until you review, retry, or dismiss them.</p>
      </header>
      <QuickCapture onCaptured={(detail) => { setSelected(detail); void load() }} />
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      {selected ? (
        <CaptureReview
          detail={selected}
          pending={pending}
          onClose={() => setSelected(null)}
          onApprove={approve}
          onReject={reject}
          onAnswer={answer}
          onEdit={edit}
          onRetry={retry}
          onDismiss={dismiss}
          onManualOrganize={onManualOrganize}
          onOpenResult={onOpenResult}
        />
      ) : null}
      {isLoading ? <p className="capture-empty">Loading captures…</p> : null}
      {!isLoading ? byGroup.map((group) => group.captures.length ? (
        <section className="capture-group" key={group.title} aria-labelledby={`capture-${group.title.replaceAll(' ', '-').toLowerCase()}`}>
          <h3 id={`capture-${group.title.replaceAll(' ', '-').toLowerCase()}`}>{group.title}<span>{group.captures.length}</span></h3>
          <div className="capture-list">{group.captures.map((capture) => (
            <button type="button" key={capture.capture_id} className="capture-row" onClick={() => void open(capture)} disabled={pending === capture.capture_id}>
              <span>
                <strong>{capture.original_text}</strong>
                {capture.interpretation_summary ? <span className="capture-row-summary">{capture.interpretation_summary}</span> : null}
                <small>{formatTime(capture.captured_at)} · {statusLabel(capture.status)}{capture.relevant_action ? ` · ${capture.relevant_action}` : ''}</small>
              </span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          ))}</div>
        </section>
      ) : null) : null}
      {!isLoading && captures.length === 0 ? <p className="capture-empty">Your Capture Inbox is clear.</p> : null}
    </section>
  )
}

interface ReviewProps {
  detail: CaptureDetail
  pending: string | null
  onClose: () => void
  onApprove: (proposal: ActionProposal) => Promise<void>
  onReject: (proposal: ActionProposal) => Promise<void>
  onAnswer: (proposalId: string, questionId: string, optionId: string) => Promise<void>
  onEdit: (proposal: ActionProposal, actionId: string, changes: Record<string, unknown>) => Promise<boolean>
  onRetry: (captureId: string) => Promise<void>
  onDismiss: (captureId: string) => Promise<void>
  onManualOrganize?: () => void
  onOpenResult?: (actionType: string, entityId: string) => void
}

function CaptureReview({ detail, pending, onClose, onApprove, onReject, onAnswer, onEdit, onRetry, onDismiss, onManualOrganize, onOpenResult }: ReviewProps) {
  const { capture, proposal, clarification } = detail
  const prohibited = proposal?.proposed_actions.some((action) => action.confirmation_requirement === 'prohibited') ?? false
  const headingRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => { headingRef.current?.focus() }, [capture.capture_id, proposal?.proposal_id, clarification?.clarification_id])
  return (
    <aside className="capture-review" aria-labelledby="capture-review-heading">
      <div className="capture-review-header">
        <div><small>Original statement</small><h3 id="capture-review-heading" ref={headingRef} tabIndex={-1}>{capture.original_text}</h3></div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close capture review"><X size={18} /></button>
      </div>
      {proposal ? <p className="capture-summary">{proposal.user_facing_summary}</p> : null}
      {proposal?.proposed_actions.length ? <div className="capture-actions"><h4>Proposed changes</h4>{proposal.proposed_actions.map((action) => (
        <div className="capture-action" key={action.action_id}>
          {action.confirmation_requirement === 'prohibited' ? <CircleAlert size={18} /> : <Check size={18} />}
          <span>
            <strong>{action.explanation}</strong>
            <small>{riskLabel(action.risk_level, action.confirmation_requirement)}</small>
            {proposal.status === 'ready_for_review' ? (
              <ProposalActionEditor
                action={action}
                disabled={pending === proposal.proposal_id}
                onSave={(changes) => onEdit(proposal, action.action_id, changes)}
              />
            ) : null}
          </span>
        </div>
      ))}</div> : null}
      {proposal?.conflict_warnings.map((warning) => <p className="capture-warning" key={warning}><CircleAlert size={16} />{warning}</p>)}
      {clarification?.status === 'open' ? clarification.questions.map((question) => (
        <fieldset className="capture-question" key={question.question_id}>
          <legend>{question.prompt}</legend>
          {question.options.map((option) => <button type="button" className="capture-question-option" key={option.option_id} disabled={pending === proposal?.proposal_id} onClick={() => proposal && void onAnswer(proposal.proposal_id, question.question_id, option.option_id)}>{option.label}</button>)}
          {question.allow_free_text && proposal ? (
            <ClarificationTextAnswer
              disabled={pending === proposal.proposal_id}
              onSubmit={(value) => onAnswer(proposal.proposal_id, question.question_id, value)}
            />
          ) : null}
        </fieldset>
      )) : null}
      {proposal?.action_results.length ? <div className="capture-results"><h4>What happened</h4>{proposal.action_results.map((result) => (
        <div className="capture-result" key={result.action_id}>
          <p>{result.safe_summary}{result.idempotent_replay ? ' (already saved)' : ''}</p>
          {result.resulting_entity_id && onOpenResult && result.action_type !== 'create_relationship' ? <button type="button" className="text-button" onClick={() => onOpenResult(result.action_type, result.resulting_entity_id!)}>Open result</button> : null}
        </div>
      ))}</div> : null}
      {capture.safe_failure_message ? <p className="capture-warning"><CircleAlert size={16} />{capture.safe_failure_message}</p> : null}
      <div className="capture-review-footer">
        {capture.status === 'failed' ? <button type="button" className="secondary-button" disabled={pending === capture.capture_id} onClick={() => void onRetry(capture.capture_id)}><RefreshCcw size={16} />Retry</button> : null}
        {capture.status === 'failed' && onManualOrganize ? <button type="button" className="secondary-button" onClick={onManualOrganize}>Organize manually</button> : null}
        {proposal && proposal.status === 'ready_for_review' && !prohibited ? <button type="button" className="primary-button" disabled={pending === proposal.proposal_id} onClick={() => void onApprove(proposal)}>Confirm changes</button> : null}
        {proposal && !['completed', 'rejected'].includes(proposal.status) ? <button type="button" className="secondary-button" disabled={pending === proposal.proposal_id} onClick={() => void onReject(proposal)}>Reject</button> : null}
        {capture.status !== 'completed' ? <button type="button" className="text-button danger-text" disabled={pending === capture.capture_id} onClick={() => void onDismiss(capture.capture_id)}><Trash2 size={15} />Dismiss</button> : null}
      </div>
    </aside>
  )
}

type EditInputType = 'text' | 'date' | 'time' | 'datetime-local' | 'textarea'
interface EditField { key: string; label: string; type: EditInputType; required?: boolean; maxLength?: number }

function ProposalActionEditor({ action, disabled, onSave }: { action: ProposedAction; disabled: boolean; onSave: (changes: Record<string, unknown>) => Promise<boolean> }) {
  const fields = editableFields(action)
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState<Record<string, string>>({})
  if (!fields.length) return null

  function begin() {
    setValues(Object.fromEntries(fields.map((field) => {
      const value = action.fields[field.key]
      const displayValue = field.type === 'datetime-local' && typeof value === 'string'
        ? value.replace('Z', '').slice(0, 16)
        : String(value ?? '')
      return [field.key, displayValue]
    })))
    setEditing(true)
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const changes = Object.fromEntries(fields.map((field) => {
      const value = values[field.key]?.trim() ?? ''
      if (field.type === 'datetime-local' && value) return [field.key, new Date(value).toISOString()]
      return [field.key, value || null]
    }))
    if (await onSave(changes)) setEditing(false)
  }

  if (!editing) return <button type="button" className="text-button capture-edit-button" disabled={disabled} onClick={begin}>Edit proposed change</button>
  return (
    <form className="capture-action-editor" onSubmit={(event) => void submit(event)}>
      {fields.map((field) => <label key={field.key}>{field.label}
        {field.type === 'textarea' ? (
          <textarea rows={3} maxLength={field.maxLength} required={field.required} value={values[field.key] ?? ''} disabled={disabled} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} />
        ) : (
          <input type={field.type} maxLength={field.maxLength} required={field.required} value={values[field.key] ?? ''} disabled={disabled} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} />
        )}
      </label>)}
      <div><button type="button" className="text-button" disabled={disabled} onClick={() => setEditing(false)}>Cancel edit</button><button type="submit" className="secondary-button" disabled={disabled}>Save adjustment</button></div>
    </form>
  )
}

function editableFields(action: ProposedAction): EditField[] {
  const byAction: Record<string, EditField[]> = {
    create_item: [{ key: 'title', label: 'Display name', type: 'text', required: true, maxLength: 120 }],
    update_item_detail: [{ key: 'value', label: 'Proposed value', type: 'text', maxLength: 500 }],
    create_responsibility: [
      { key: 'title', label: 'Responsibility title', type: 'text', required: true, maxLength: 120 },
      { key: 'due_date', label: 'Due date', type: 'date', required: true },
      { key: 'reminder_time', label: 'Reminder time', type: 'time' },
      { key: 'notes', label: 'Notes', type: 'textarea', maxLength: 1000 },
    ],
    complete_responsibility: [{ key: 'completed_on', label: 'Completion date', type: 'date' }, { key: 'note', label: 'Completion note', type: 'textarea', maxLength: 500 }],
    renew_responsibility: [{ key: 'new_due_date', label: 'New due date', type: 'date', required: true }, { key: 'renewed_on', label: 'Renewal date', type: 'date' }, { key: 'note', label: 'Renewal note', type: 'textarea', maxLength: 500 }],
    snooze_responsibility: [{ key: 'snoozed_until', label: 'Snooze until', type: 'datetime-local', required: true }],
    add_safe_note: [{ key: 'note', label: 'Safe note', type: 'textarea', required: true, maxLength: 500 }],
  }
  return byAction[action.action_type] ?? []
}

function ClarificationTextAnswer({ disabled, onSubmit }: { disabled: boolean; onSubmit: (value: string) => Promise<void> }) {
  const [value, setValue] = useState('')
  return (
    <form className="capture-question-text" onSubmit={(event) => { event.preventDefault(); if (value.trim()) void onSubmit(value.trim()) }}>
      <label>
        <span>Your answer</span>
        <textarea value={value} onChange={(event) => setValue(event.target.value)} maxLength={500} rows={2} disabled={disabled} placeholder="Add the missing name or detail" />
      </label>
      <button type="submit" className="primary-button" disabled={disabled || !value.trim()}>Continue</button>
    </form>
  )
}

function formatTime(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
function statusLabel(value: CaptureStatus) { return value.replaceAll('_', ' ') }
function riskLabel(risk: string, requirement: string) {
  if (requirement === 'prohibited') return 'Use the normal LifeLedger editor for this change.'
  return risk === 'low' ? 'Review and confirm' : 'Confirmation required'
}
function message(error: unknown) { return error instanceof Error ? error.message : 'LifeLedger could not complete this capture action.' }
