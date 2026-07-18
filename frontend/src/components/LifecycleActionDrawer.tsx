import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, FileUp, RefreshCcw, ShieldCheck, X } from 'lucide-react'

import { recordsApi } from '../api/recordsApi'
import { remindersApi } from '../api/remindersApi'
import { attachmentAccept, formatAttachmentSize, validateAttachmentFile } from '../lib/attachmentFiles'
import { formatLongDate, formatRepeatLabel } from '../lib/reminderDisplay'
import type { LifeRecord } from '../types/record'
import type { Reminder } from '../types/reminder'
import { SheetDrawer } from './SheetDrawer'

export type LifecycleActionKind = 'complete' | 'renew'

interface LifecycleActionDrawerProps {
  action: LifecycleActionKind
  reminder: Reminder
  records: LifeRecord[]
  onClose: () => void
  onSaved: (reminder: Reminder, message: string) => void
}

export function LifecycleActionDrawer({ action, reminder, records, onClose, onSaved }: LifecycleActionDrawerProps) {
  const [step, setStep] = useState<'details' | 'review'>('details')
  const [actionDate, setActionDate] = useState(todayDateKey())
  const [newDueDate, setNewDueDate] = useState(() => defaultRenewalDate(reminder))
  const [note, setNote] = useState('')
  const [documentFile, setDocumentFile] = useState<File | null>(null)
  const [recordId, setRecordId] = useState(() => activeLinkedRecords(reminder, records)[0]?.id ?? '')
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [completedAction, setCompletedAction] = useState<Reminder | null>(null)
  const [uploadedDocument, setUploadedDocument] = useState<{ attachment_id: string; status: string } | null>(null)
  const operationKeyRef = useRef(crypto.randomUUID())
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const linkedRecords = activeLinkedRecords(reminder, records)
  const isRenew = action === 'renew'
  const nextDuePreview = isRenew ? newDueDate : previewCompletionNextDue(reminder, actionDate)

  useEffect(() => {
    setStep('details')
    setActionDate(todayDateKey())
    setNewDueDate(defaultRenewalDate(reminder))
    setNote('')
    setDocumentFile(null)
    setRecordId(activeLinkedRecords(reminder, records)[0]?.id ?? '')
    setError(null)
    setCompletedAction(null)
    setUploadedDocument(null)
    operationKeyRef.current = crypto.randomUUID()
  }, [action, records, reminder])

  function chooseFile(file: File | null) {
    if (!file) return
    const validation = validateAttachmentFile(file, 0)
    if (validation) {
      setError(validation)
      return
    }
    setDocumentFile(file)
    setError(null)
  }

  function review() {
    if (!actionDate) {
      setError(`Choose the ${isRenew ? 'renewal' : 'completion'} date.`)
      return
    }
    if (isRenew && (!newDueDate || newDueDate < actionDate)) {
      setError('Choose a new due date on or after the renewal date.')
      return
    }
    setError(null)
    setStep('review')
  }

  async function save() {
    if (isSaving) return
    setIsSaving(true)
    setError(null)
    const operationKey = operationKeyRef.current
    try {
      const updated = completedAction ?? (isRenew
        ? await remindersApi.renew(reminder.id, {
            new_due_date: newDueDate,
            renewed_on: actionDate,
            occurrence_id: reminder.current_occurrence_id ?? null,
            note: note.trim() || null,
          }, operationKey)
        : await remindersApi.complete(reminder.id, {
            completed_on: actionDate,
            occurrence_id: reminder.current_occurrence_id ?? null,
            note: note.trim() || null,
          }, operationKey))
      setCompletedAction(updated)

      let message = completionMessage(action, updated)
      if (updated.lifecycle_reconciliation_status === 'needs_attention') {
        message += ' The responsibility was saved, but an item date or search update needs attention.'
      }

      if (documentFile && recordId) {
        try {
          const document = uploadedDocument ?? await recordsApi.uploadRecordAttachment(recordId, documentFile, `${operationKey}:document`)
          setUploadedDocument({ attachment_id: document.attachment_id, status: document.status })
          if (!updated.last_lifecycle_event_id) {
            throw new Error('The lifecycle entry could not be linked to the document.')
          }
          await remindersApi.addEvidence(reminder.id, {
            record_id: recordId,
            document_id: document.attachment_id,
            occurrence_id: reminder.current_occurrence_id ?? null,
            related_event_id: updated.last_lifecycle_event_id,
          }, `${operationKey}:evidence`)
          message += document.status === 'available'
            ? ' The supporting document is available.'
            : ' The supporting document is being scanned.'
        } catch (documentError) {
          setError(documentError instanceof Error
            ? `The responsibility was saved, but the optional document did not finish: ${documentError.message}. Retry only the document below.`
            : 'The responsibility was saved, but the optional document did not finish. Retry only the document below.')
          return
        }
      }
      onSaved(updated, message)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : `Unable to ${isRenew ? 'renew' : 'complete'} this responsibility.`)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <SheetDrawer
      className="lifecycle-action-dialog"
      footer={(
        <div className="lifecycle-action-footer">
          {step === 'review' && !completedAction ? <button type="button" className="secondary-button" onClick={() => setStep('details')} disabled={isSaving}>Back</button> : <span />}
          <button type="button" className="primary-button" onClick={step === 'details' ? review : () => void save()} disabled={isSaving}>
            {step === 'details' ? 'Review' : isSaving ? 'Saving...' : completedAction ? 'Retry document' : isRenew ? 'Confirm renewal' : 'Confirm completion'}
          </button>
        </div>
      )}
      isOpen
      labelledBy="lifecycle-action-heading"
      onClose={onClose}
      subtitle={isRenew ? 'Preserve the previous date and set what is current now.' : 'Record what happened without changing prior history.'}
      title={isRenew ? 'Renew responsibility' : 'Mark responsibility complete'}
    >
      {error ? <div className="form-error" role="alert">{error}</div> : null}
      {step === 'details' ? (
        <div className="lifecycle-action-form">
          <section className="detail-section" aria-labelledby="lifecycle-current-heading">
            <h3 id="lifecycle-current-heading">Current cycle</h3>
            <dl className="lifecycle-review-list">
              <div><dt>Responsibility</dt><dd>{reminder.title}</dd></div>
              <div><dt>Current due date</dt><dd>{formatLongDate(reminder.due_date)}</dd></div>
              <div><dt>Repeat</dt><dd>{formatRepeatLabel(reminder.repeat) ?? 'Does not repeat'}</dd></div>
            </dl>
          </section>
          <label className="form-field">
            <span>{isRenew ? 'Renewed on' : 'Completed on'}</span>
            <input type="date" max={todayDateKey()} value={actionDate} onChange={(event) => setActionDate(event.target.value)} />
          </label>
          {isRenew ? (
            <label className="form-field">
              <span>New expiration or due date</span>
              <input type="date" value={newDueDate} min={actionDate} onChange={(event) => setNewDueDate(event.target.value)} />
            </label>
          ) : null}
          <label className="form-field">
            <span>Completion note <small>Optional</small></span>
            <textarea maxLength={500} rows={3} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Add brief private context" />
            <small>This note stays in history and is not included in search.</small>
          </label>
          {linkedRecords.length > 0 ? (
            <section className="detail-section lifecycle-evidence-picker" aria-labelledby="lifecycle-evidence-heading">
              <div className="lifecycle-evidence-heading">
                <ShieldCheck size={20} aria-hidden="true" />
                <div><h3 id="lifecycle-evidence-heading">Supporting document</h3><p>Optional. PDF, JPEG, and PNG files use the existing secure scan flow.</p></div>
              </div>
              {linkedRecords.length > 1 ? (
                <label className="form-field"><span>Attach to item</span><select value={recordId} onChange={(event) => setRecordId(event.target.value)}>{linkedRecords.map((record) => <option value={record.id} key={record.id}>{record.title}</option>)}</select></label>
              ) : null}
              {documentFile ? (
                <div className="guided-document-file">
                  <FileUp size={18} aria-hidden="true" />
                  <span><strong>{documentFile.name}</strong><small>{formatAttachmentSize(documentFile.size)}</small></span>
                  <button type="button" className="icon-button ghost-icon-button" onClick={() => setDocumentFile(null)} aria-label={`Remove ${documentFile.name}`}><X size={16} aria-hidden="true" /></button>
                </div>
              ) : <button type="button" className="secondary-button" onClick={() => fileInputRef.current?.click()}><FileUp size={16} aria-hidden="true" /> Add document</button>}
              <input ref={fileInputRef} className="attachment-file-input" type="file" accept={attachmentAccept} onChange={(event) => chooseFile(event.target.files?.[0] ?? null)} />
            </section>
          ) : <p className="linked-items-state">Connect this responsibility to an item to add optional supporting evidence.</p>}
        </div>
      ) : (
        <section className="detail-section lifecycle-review" aria-labelledby="lifecycle-review-heading">
          <div className="lifecycle-review-heading"><span aria-hidden="true">{isRenew ? <RefreshCcw size={20} /> : <CheckCircle2 size={20} />}</span><div><h3 id="lifecycle-review-heading">Review before saving</h3><p>Current state will change; this history entry will remain.</p></div></div>
          <dl className="lifecycle-review-list">
            <div><dt>{isRenew ? 'Renewed on' : 'Completed on'}</dt><dd>{formatLongDate(actionDate)}</dd></div>
            <div><dt>Previous due date</dt><dd>{formatLongDate(reminder.due_date)}</dd></div>
            <div><dt>Next due date</dt><dd>{nextDuePreview ? formatLongDate(nextDuePreview) : 'Remains completed'}</dd></div>
            {note.trim() ? <div><dt>Note</dt><dd>{note.trim()}</dd></div> : null}
            <div><dt>Document</dt><dd>{documentFile?.name ?? 'Skipped'}</dd></div>
          </dl>
        </section>
      )}
    </SheetDrawer>
  )
}

function activeLinkedRecords(reminder: Reminder, records: LifeRecord[]) {
  const ids = new Set(reminder.linked_records.filter((record) => record.status !== 'archived').map((record) => record.id))
  return records.filter((record) => ids.has(record.id) && record.status !== 'archived')
}

function completionMessage(action: LifecycleActionKind, reminder: Reminder) {
  if (action === 'renew') return `Renewed. Next due ${formatLongDate(reminder.due_date)}.`
  if (!reminder.completed) return `Completed. Next due ${formatLongDate(reminder.due_date)}.`
  return 'Responsibility completed.'
}

function previewCompletionNextDue(reminder: Reminder, completedOn: string) {
  if (reminder.maintenance_details?.interval_value && reminder.maintenance_details.interval_unit) {
    return addInterval(completedOn, reminder.maintenance_details.interval_value, reminder.maintenance_details.interval_unit)
  }
  if (reminder.repeat === 'None') return null
  return addInterval(reminder.due_date, 1, reminder.repeat.toLowerCase().replace('ly', '') as 'week' | 'month' | 'quarter' | 'year')
}

function defaultRenewalDate(reminder: Reminder) {
  if (reminder.repeat !== 'None') return previewCompletionNextDue(reminder, todayDateKey()) ?? reminder.due_date
  return addInterval(reminder.due_date, 1, 'year')
}

function addInterval(value: string, amount: number, unit: 'days' | 'weeks' | 'months' | 'years' | 'week' | 'month' | 'quarter' | 'year') {
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  if (unit === 'days') date.setUTCDate(date.getUTCDate() + amount)
  else if (unit === 'weeks' || unit === 'week') date.setUTCDate(date.getUTCDate() + amount * 7)
  else {
    const targetMonth = unit === 'quarter' ? month - 1 + amount * 3 : unit === 'months' || unit === 'month' ? month - 1 + amount : null
    if (targetMonth !== null) {
      const targetYear = year + Math.floor(targetMonth / 12)
      const normalizedMonth = ((targetMonth % 12) + 12) % 12
      const lastDay = new Date(Date.UTC(targetYear, normalizedMonth + 1, 0)).getUTCDate()
      date.setUTCFullYear(targetYear, normalizedMonth, Math.min(day, lastDay))
    } else {
      const targetYear = year + amount
      const lastDay = new Date(Date.UTC(targetYear, month, 0)).getUTCDate()
      date.setUTCFullYear(targetYear, month - 1, Math.min(day, lastDay))
    }
  }
  return date.toISOString().slice(0, 10)
}

function todayDateKey() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}
