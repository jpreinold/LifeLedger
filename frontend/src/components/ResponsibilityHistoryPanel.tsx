import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Clock3, FileText, RefreshCcw, RotateCcw } from 'lucide-react'

import { recordsApi } from '../api/recordsApi'
import { remindersApi } from '../api/remindersApi'
import { formatLongDate } from '../lib/reminderDisplay'
import type { ResponsibilityEvent, ResponsibilityEventType } from '../types/responsibilityHistory'

interface ResponsibilityHistoryPanelProps {
  entityId: string
  mode: 'reminder' | 'item'
  onOpenDocument?: (recordId: string, documentId: string) => void
  onOpenReminder?: (reminderId: string) => void
}

export default function ResponsibilityHistoryPanel({ entityId, mode, onOpenDocument, onOpenReminder }: ResponsibilityHistoryPanelProps) {
  const [events, setEvents] = useState<ResponsibilityEvent[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [isReconciling, setIsReconciling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (nextCursor?: string | null) => {
    const page = mode === 'reminder'
      ? await remindersApi.history(entityId, nextCursor)
      : await recordsApi.activity(entityId, nextCursor)
    setEvents((current) => nextCursor ? [...current, ...page.items] : page.items)
    setCursor(page.next_cursor)
  }, [entityId, mode])

  useEffect(() => {
    let active = true
    setIsLoading(true)
    setError(null)
    void load().catch((requestError) => {
      if (active) setError(requestError instanceof Error ? requestError.message : 'Unable to load history.')
    }).finally(() => {
      if (active) setIsLoading(false)
    })
    return () => { active = false }
  }, [load])

  async function loadMore() {
    if (!cursor || isLoadingMore) return
    setIsLoadingMore(true)
    setError(null)
    try {
      await load(cursor)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load more history.')
    } finally {
      setIsLoadingMore(false)
    }
  }

  async function reconcile() {
    if (mode !== 'reminder' || isReconciling) return
    setIsReconciling(true)
    setError(null)
    try {
      const result = await remindersApi.reconcileHistory(entityId)
      await load()
      if (result.remaining > 0) setError('Some connected item, search, or document updates still need attention. Your history is preserved.')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to retry connected updates.')
    } finally {
      setIsReconciling(false)
    }
  }

  const needsReconciliation = events.some((event) =>
    event.reconciliation_status === 'needs_attention' || event.search_sync_status === 'needs_attention',
  )

  return (
    <section className="detail-section responsibility-history-panel" aria-labelledby={`${mode}-history-heading`}>
      <div className="responsibility-history-heading">
        <div>
          <h3 id={`${mode}-history-heading`}>{mode === 'reminder' ? 'History' : 'Activity'}</h3>
          <p>{mode === 'reminder' ? 'Meaningful changes to this responsibility, newest first.' : 'Lifecycle activity from responsibilities connected to this item.'}</p>
        </div>
      </div>
      <div className="history-loading-announcement" role="status" aria-live="polite">
        {isLoading ? 'Loading history...' : isLoadingMore ? 'Loading more history...' : ''}
      </div>
      {error ? <div className="form-error" role="alert">{error}</div> : null}
      {!isLoading && events.length === 0 ? (
        <p className="linked-items-state">{mode === 'reminder' ? 'History tracking begins with the next lifecycle action. No earlier actions are inferred.' : 'Completed renewals, services, vaccinations, and other responsibility activity will appear here.'}</p>
      ) : null}
      {events.length > 0 ? (
        <ol className="responsibility-history-list">
          {events.map((event) => (
            <HistoryEntry event={event} key={event.event_id} mode={mode} onOpenDocument={onOpenDocument} onOpenReminder={onOpenReminder} />
          ))}
        </ol>
      ) : null}
      {needsReconciliation ? (
        <div className="history-reconciliation" role="status">
          <p>A connected item date or search update needs attention. The lifecycle entry is safely preserved.</p>
          {mode === 'reminder' ? <button type="button" className="small-outline-button" disabled={isReconciling} onClick={() => void reconcile()}>{isReconciling ? 'Retrying…' : 'Retry updates'}</button> : null}
        </div>
      ) : null}
      {cursor ? <button type="button" className="secondary-button history-load-more" disabled={isLoadingMore} onClick={() => void loadMore()}>{isLoadingMore ? 'Loading...' : 'Load more'}</button> : null}
    </section>
  )
}

function HistoryEntry({ event, mode, onOpenDocument, onOpenReminder }: {
  event: ResponsibilityEvent
  mode: 'reminder' | 'item'
  onOpenDocument?: (recordId: string, documentId: string) => void
  onOpenReminder?: (reminderId: string) => void
}) {
  const Icon = eventIcon(event.event_type)
  const description = eventDescription(event)
  return (
    <li>
      <span className="responsibility-history-icon" aria-hidden="true"><Icon size={17} /></span>
      <div className="responsibility-history-copy">
        <div className="responsibility-history-title-row">
          <strong>{eventLabel(event.event_type)}</strong>
          <time dateTime={event.occurred_at}>{formatTimestamp(event.occurred_at)}</time>
        </div>
        {mode === 'item' && event.responsibility_title_snapshot ? (
          onOpenReminder
            ? <button type="button" className="history-reminder-link" onClick={() => onOpenReminder(event.reminder_id)}>{event.responsibility_title_snapshot}</button>
            : <span>{event.responsibility_title_snapshot}</span>
        ) : null}
        {description ? <p>{description}</p> : null}
        {event.note ? <p className="responsibility-history-note"><span>Note</span>{event.note}</p> : null}
        {event.documents.length > 0 ? (
          <div className="responsibility-history-documents" aria-label="Supporting documents">
            {event.documents.map((document) => document.available && document.record_id && onOpenDocument ? (
              <button type="button" className="small-outline-button" key={document.document_id} onClick={() => onOpenDocument(document.record_id!, document.document_id)}><FileText size={14} aria-hidden="true" />{document.display_name}</button>
            ) : (
              <span className="history-document-status" key={document.document_id}><FileText size={14} aria-hidden="true" />{document.display_name} — {friendlyDocumentStatus(document.status)}</span>
            ))}
          </div>
        ) : null}
      </div>
    </li>
  )
}

function eventLabel(type: ResponsibilityEventType) {
  const labels: Record<ResponsibilityEventType, string> = {
    responsibility_created: 'Responsibility created',
    completed: 'Completed',
    renewed: 'Renewed',
    snoozed: 'Snoozed',
    snooze_cleared: 'Snooze cleared',
    reopened: 'Reopened',
    due_date_changed: 'Due date changed',
    supporting_document_added: 'Supporting document added',
    history_tracking_started: 'History tracking started',
  }
  return labels[type]
}

function eventDescription(event: ResponsibilityEvent) {
  if (event.event_type === 'renewed' || event.event_type === 'due_date_changed') {
    if (event.previous_due_date && event.next_due_date) return `Date changed from ${formatLongDate(event.previous_due_date)} to ${formatLongDate(event.next_due_date)}.`
  }
  if (event.event_type === 'completed') {
    return event.next_due_date ? `Next due ${formatLongDate(event.next_due_date)}.` : event.effective_date ? `Completed on ${formatLongDate(event.effective_date)}.` : null
  }
  if (event.event_type === 'snoozed' && event.effective_date) return `Remind again ${formatLongDate(event.effective_date)}.`
  if (event.event_type === 'responsibility_created' && event.next_due_date) return `First tracked due date ${formatLongDate(event.next_due_date)}.`
  if (event.event_type === 'reopened') return 'A new completion cycle was opened; earlier completion history remains unchanged.'
  if (event.event_type === 'history_tracking_started') return 'Earlier lifecycle actions were not inferred.'
  return null
}

function eventIcon(type: ResponsibilityEventType) {
  if (type === 'renewed' || type === 'due_date_changed') return RefreshCcw
  if (type === 'reopened') return RotateCcw
  if (type === 'snoozed' || type === 'snooze_cleared') return Clock3
  if (type === 'supporting_document_added') return FileText
  return CheckCircle2
}

function formatTimestamp(value: string) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) return 'Date unavailable'
  return timestamp.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function friendlyDocumentStatus(status: string) {
  if (status === 'scanning' || status === 'uploaded' || status === 'pending_upload') return 'Scan pending'
  if (status === 'rejected' || status === 'scan_failed') return 'Not accepted as evidence'
  if (status === 'unavailable' || status === 'deleted') return 'Document no longer available'
  return status.replaceAll('_', ' ')
}
