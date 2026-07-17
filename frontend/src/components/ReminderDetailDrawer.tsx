import { useCallback, useEffect, useRef, useState } from 'react'
import { Cake, CalendarCheck, CalendarPlus, CalendarX, CheckCircle2, Clock3, Pencil, RefreshCcw, Trash2, Wrench } from 'lucide-react'

import { getMaintenanceAreaLabel, getMaintenanceDueDate } from '../lib/maintenanceUx'
import {
  formatLongDate,
  formatMonthDay,
  formatReminderAttentionLabel,
  formatReminderStatusLabel,
  formatRepeatLabel,
  getReminderTypeLabel,
} from '../lib/reminderDisplay'
import { formatReminderTiming } from '../lib/reminderSchedule'
import {
  getRelevantRenewalDate,
  getRenewalDateLabel,
  getRenewalDisplayKind,
  getRenewalKindLabel,
} from '../lib/renewalUx'
import { getSmartReminderLabel } from '../lib/smartReminderLabels'
import type { GoogleCalendarStatus } from '../api/calendarApi'
import type { Reminder } from '../types/reminder'
import type { LifeRecord } from '../types/record'
import { getCategoryVisual } from './categoryVisuals'
import { DetailSection, type DetailRow } from './DetailSection'
import { LinkedItemsPanel } from './LinkedItemsPanel'
import { SheetDrawer } from './SheetDrawer'

const drawerCloseMs = 220

interface ReminderDetailDrawerProps {
  reminder: Reminder
  records: LifeRecord[]
  calendarStatus: GoogleCalendarStatus | null
  isCalendarStatusLoading: boolean
  isAlertEligible: boolean
  onClose: () => void
  onClearSnooze: (id: string) => Promise<boolean>
  onComplete: (id: string) => Promise<void>
  onDisableCalendarSync: (id: string) => Promise<boolean>
  onEnableCalendarSync: (id: string) => Promise<boolean>
  onDismiss: (id: string) => Promise<void>
  onEdit: (reminder: Reminder) => void
  onOpenLinkedDocument?: (recordId: string, documentId: string) => void
  onOpenLinkedRecord: (recordId: string) => void
  onRenew: (id: string, newDueDate: string) => Promise<boolean>
  onRequestDelete: (reminder: Reminder) => void
  onSnooze: (id: string, snoozedUntil: string) => Promise<boolean>
  isActionPending: boolean
}

export function ReminderDetailDrawer({
  reminder,
  records,
  calendarStatus,
  isCalendarStatusLoading,
  isAlertEligible,
  onClose,
  onClearSnooze,
  onComplete,
  onDisableCalendarSync,
  onEnableCalendarSync,
  onDismiss,
  onEdit,
  onOpenLinkedDocument,
  onOpenLinkedRecord,
  onRenew,
  onRequestDelete,
  onSnooze,
  isActionPending,
}: ReminderDetailDrawerProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [isCalendarSyncSaving, setIsCalendarSyncSaving] = useState(false)
  const [customSnoozeDate, setCustomSnoozeDate] = useState(() => addDaysDateOnly(3))
  const [renewDate, setRenewDate] = useState(reminder.due_date)
  const closeTimerRef = useRef<number | null>(null)
  const detailBodyRef = useRef<HTMLDivElement | null>(null)
  const openFrameRef = useRef<number | null>(null)
  const { Icon, tone } = getCategoryVisual(reminder.category)
  const smartLabel = getSmartReminderLabel(reminder)
  const TypeIcon = getTypeIcon(reminder.reminder_type)
  const typeRows = getTypeSpecificRows(reminder)
  const note = getNotes(reminder)
  const heroLabel = smartLabel ?? formatReminderAttentionLabel(reminder)
  const resetDetailScroll = useCallback(() => {
    detailBodyRef.current?.scrollTo({ top: 0 })
  }, [])

  useEffect(() => {
    setCustomSnoozeDate(addDaysDateOnly(3))
    setRenewDate(reminder.due_date)
    setIsDrawerOpen(false)
    resetDetailScroll()
    openFrameRef.current = window.requestAnimationFrame(() => {
      resetDetailScroll()
      setIsDrawerOpen(true)
      openFrameRef.current = null
    })

    return () => {
      if (openFrameRef.current !== null) {
        window.cancelAnimationFrame(openFrameRef.current)
      }
    }
  }, [reminder.due_date, reminder.id, resetDetailScroll])

  useEffect(() => {
    if (!isDrawerOpen) {
      return
    }

    const frame = window.requestAnimationFrame(() => {
      resetDetailScroll()
    })

    return () => window.cancelAnimationFrame(frame)
  }, [isDrawerOpen, reminder.id, resetDetailScroll])

  useEffect(() => {
    if (!isDrawerOpen || !detailBodyRef.current) {
      return
    }

    const observer = new ResizeObserver(() => resetDetailScroll())
    observer.observe(detailBodyRef.current)

    return () => observer.disconnect()
  }, [isDrawerOpen, resetDetailScroll])

  useEffect(() => {
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current)
      }
    }
  }, [])

  const requestClose = useCallback(() => {
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onClose()
    }, drawerCloseMs)
  }, [onClose])

  function handleEdit() {
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onEdit(reminder)
    }, drawerCloseMs)
  }

  async function handleComplete() {
    await onComplete(reminder.id)
    requestClose()
  }

  async function handleDismiss() {
    await onDismiss(reminder.id)
    requestClose()
  }

  async function handleQuickSnooze(days: number) {
    const snoozed = await onSnooze(reminder.id, dateOnlyToSnoozeIso(addDaysDateOnly(days)))
    if (snoozed) {
      requestClose()
    }
  }

  async function handleCustomSnooze() {
    if (!customSnoozeDate) {
      return
    }

    await onSnooze(reminder.id, dateOnlyToSnoozeIso(customSnoozeDate))
  }

  async function handleClearSnooze() {
    await onClearSnooze(reminder.id)
  }

  async function handleRenew() {
    if (!renewDate) {
      return
    }

    await onRenew(reminder.id, renewDate)
  }
  async function handleCalendarSyncToggle() {
    setIsCalendarSyncSaving(true)
    try {
      if (reminder.calendar_sync_enabled) {
        await onDisableCalendarSync(reminder.id)
      } else {
        await onEnableCalendarSync(reminder.id)
      }
    } finally {
      setIsCalendarSyncSaving(false)
    }
  }

  return (
    <SheetDrawer
      bodyClassName="detail-body"
      bodyRef={detailBodyRef}
      className="detail-dialog"
      closeLabel="Close reminder details"
      footer={(
        <section className="detail-actions reminder-detail-actions" aria-label="Reminder actions">
          <button type="button" className="secondary-button" onClick={handleEdit} disabled={isActionPending}>
            <Pencil size={17} aria-hidden="true" />
            Edit
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={() => void handleComplete()}
            disabled={reminder.completed || isActionPending}
          >
            <CheckCircle2 size={17} aria-hidden="true" />
            {isActionPending ? 'Saving' : reminder.completed ? 'Completed' : 'Complete'}
          </button>
          {!reminder.completed ? (
            <button type="button" className="small-outline-button" onClick={() => void handleQuickSnooze(1)} disabled={isActionPending}>
              <Clock3 size={14} aria-hidden="true" />
              Tomorrow
            </button>
          ) : null}
          {isAlertEligible ? (
            <button type="button" className="small-outline-button" onClick={() => void handleDismiss()} disabled={isActionPending}>
              Dismiss for now
            </button>
          ) : null}
          <button type="button" className="text-danger-button detail-delete-button" onClick={() => onRequestDelete(reminder)} disabled={isActionPending}>
            <Trash2 size={16} aria-hidden="true" />
            Delete
          </button>
        </section>
      )}
      headerClassName="detail-header"
      isOpen={isDrawerOpen}
      labelledBy="reminder-detail-heading"
      onClose={requestClose}
      subtitle="Review the reminder before taking action."
      title="Reminder details"
    >
        <section className={`detail-hero tone-${tone}`} aria-labelledby="detail-title">
          <div className={`category-icon category-icon-large tone-${tone}`} aria-hidden="true">
            <Icon size={30} />
          </div>
          <div className="detail-hero-copy">
            <div className="card-chip-row">
              <span className="type-chip">{getReminderTypeLabel(reminder.reminder_type)}</span>
              <span className="category-chip">{reminder.category}</span>
            </div>
            <h3 id="detail-title">{reminder.title}</h3>
            <p className="detail-smart-label">
              <TypeIcon size={15} aria-hidden="true" />
              {heroLabel}
            </p>
            <div className="detail-hero-meta" aria-label="Reminder summary">
              <span className="detail-hero-pill">{formatReminderStatusLabel(reminder)}</span>
              <span className="detail-hero-pill">{formatLongDate(reminder.due_date)}</span>
              <span className="detail-hero-pill">{formatReminderTiming(reminder)}</span>
            </div>
          </div>
        </section>

        <DetailSection
          title={getDetailSectionTitle(reminder)}
          rows={[
            { label: 'Priority', value: `${reminder.priority} priority` },
            ...typeRows,
          ]}
        />

        <DetailSection
          title="Schedule"
          className="detail-schedule-section"
          rows={[
            { label: 'Due date', value: formatLongDate(reminder.due_date) },
            { label: 'Reminder timing', value: formatReminderTiming(reminder) },
            { label: 'Repeat', value: formatRepeatLabel(reminder.repeat) ?? 'Does not repeat' },
            { label: 'Status', value: formatReminderStatusLabel(reminder) },
            { label: 'Effective attention', value: reminder.effective_attention_date !== reminder.due_date ? formatLongDate(reminder.effective_attention_date) : null },
          ]}
        />


        <LifecycleActionsSection
          customSnoozeDate={customSnoozeDate}
          isSaving={isActionPending}
          reminder={reminder}
          renewDate={renewDate}
          onClearSnooze={() => void handleClearSnooze()}
          onCustomSnooze={() => void handleCustomSnooze()}
          onQuickSnooze={(days) => void handleQuickSnooze(days)}
          onRenew={() => void handleRenew()}
          onRenewDateChange={setRenewDate}
          onSnoozeDateChange={setCustomSnoozeDate}
        />

        <LifecycleHistorySection reminder={reminder} />
        <CalendarSyncSection
          reminder={reminder}
          calendarStatus={calendarStatus}
          isCalendarStatusLoading={isCalendarStatusLoading}
          isSaving={isCalendarSyncSaving}
          onToggle={() => void handleCalendarSyncToggle()}
        />

        <LinkedItemsPanel
          records={records}
          reminders={[]}
          showAdd
          sourceId={reminder.id}
          sourceTitle={reminder.title}
          sourceType="reminder"
          title="Linked items"
          onOpenDocument={onOpenLinkedDocument}
          onOpenRecord={onOpenLinkedRecord}
        />

        {note ? (
          <section className="detail-section" aria-labelledby="detail-notes-heading">
            <h3 id="detail-notes-heading">{reminder.reminder_type === 'maintenance' ? 'Notes & Instructions' : 'Notes'}</h3>
            <p className="detail-note">{note}</p>
          </section>
        ) : null}
    </SheetDrawer>
  )
}



function LifecycleActionsSection({
  customSnoozeDate,
  isSaving,
  onClearSnooze,
  onCustomSnooze,
  onQuickSnooze,
  onRenew,
  onRenewDateChange,
  onSnoozeDateChange,
  reminder,
  renewDate,
}: {
  customSnoozeDate: string
  isSaving: boolean
  reminder: Reminder
  renewDate: string
  onClearSnooze: () => void
  onCustomSnooze: () => void
  onQuickSnooze: (days: number) => void
  onRenew: () => void
  onRenewDateChange: (value: string) => void
  onSnoozeDateChange: (value: string) => void
}) {
  if (reminder.completed) {
    return null
  }

  const canRenew = canRenewReminder(reminder)
  const hasSnooze = Boolean(reminder.snoozed_until || reminder.alert_snoozed_until)

  return (
    <section className="detail-section lifecycle-actions-section" aria-labelledby="lifecycle-actions-heading">
      <h3 id="lifecycle-actions-heading">Lifecycle actions</h3>
      <div className="lifecycle-action-grid">
        <div className="lifecycle-action-panel">
          <strong>Snooze</strong>
          <p>Defer attention without changing the important date.</p>
          <div className="lifecycle-button-row">
            <button type="button" className="small-outline-button" disabled={isSaving} onClick={() => onQuickSnooze(1)}>Tomorrow</button>
            <button type="button" className="small-outline-button" disabled={isSaving} onClick={() => onQuickSnooze(3)}>3 days</button>
            <button type="button" className="small-outline-button" disabled={isSaving} onClick={() => onQuickSnooze(7)}>1 week</button>
          </div>
          <label className="lifecycle-date-field">
            <span>Custom date</span>
            <input type="date" value={customSnoozeDate} onChange={(event) => onSnoozeDateChange(event.target.value)} />
          </label>
          <div className="lifecycle-button-row">
            <button type="button" className="secondary-button" disabled={isSaving || !customSnoozeDate} onClick={onCustomSnooze}>
              {isSaving ? 'Saving...' : 'Snooze'}
            </button>
            {hasSnooze ? (
              <button type="button" className="small-outline-button" disabled={isSaving} onClick={onClearSnooze}>Clear snooze</button>
            ) : null}
          </div>
        </div>

        {canRenew ? (
          <div className="lifecycle-action-panel">
            <strong>Renew</strong>
            <p>Record this cycle and set the next active date.</p>
            <label className="lifecycle-date-field">
              <span>New date</span>
              <input type="date" value={renewDate} onChange={(event) => onRenewDateChange(event.target.value)} />
            </label>
            <button type="button" className="primary-button lifecycle-renew-button" disabled={isSaving || !renewDate} onClick={onRenew}>
              <RefreshCcw size={16} aria-hidden="true" />
              {isSaving ? 'Saving...' : 'Renew'}
            </button>
          </div>
        ) : null}
      </div>
    </section>
  )
}

function LifecycleHistorySection({ reminder }: { reminder: Reminder }) {
  const events = [...reminder.lifecycle_events].reverse()

  return (
    <section className="detail-section lifecycle-history-section" aria-labelledby="lifecycle-history-heading">
      <h3 id="lifecycle-history-heading">History</h3>
      {events.length === 0 ? <p className="linked-items-state">No lifecycle history yet.</p> : null}
      {events.length > 0 ? (
        <ol className="lifecycle-history-list">
          {events.map((event) => (
            <li key={event.event_id}>
              <strong>{formatLifecycleEventType(event.event_type)}</strong>
              <span>{event.summary}</span>
              <time dateTime={event.occurred_at}>{formatLifecycleTimestamp(event.occurred_at)}</time>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  )
}
function CalendarSyncSection({
  reminder,
  calendarStatus,
  isCalendarStatusLoading,
  isSaving,
  onToggle,
}: {
  reminder: Reminder
  calendarStatus: GoogleCalendarStatus | null
  isCalendarStatusLoading: boolean
  isSaving: boolean
  onToggle: () => void
}) {
  const syncState = getCalendarSyncState(reminder, calendarStatus, isCalendarStatusLoading)
  const canToggle = calendarStatus?.connected === true && !isCalendarStatusLoading && !isSaving
  const SyncIcon = reminder.calendar_sync_enabled ? CalendarCheck : CalendarPlus

  return (
    <section className="detail-section detail-calendar-sync-section" aria-labelledby="detail-calendar-sync-heading">
      <h3 id="detail-calendar-sync-heading">Calendar Sync</h3>
      <div className="detail-calendar-sync-summary">
        <CalendarCheck size={17} aria-hidden="true" />
        <div>
          <strong>{syncState.label}</strong>
          <span>{syncState.description}</span>
        </div>
      </div>

      {reminder.calendar_last_synced_at ? (
        <dl className="detail-list detail-calendar-sync-list">
          <div className="detail-row">
            <dt>Last synced</dt>
            <dd>{formatCalendarSyncTimestamp(reminder.calendar_last_synced_at)}</dd>
          </div>
        </dl>
      ) : null}

      {calendarStatus?.connected ? (
        <button
          type="button"
          className={reminder.calendar_sync_enabled ? 'secondary-button detail-calendar-sync-button' : 'primary-button detail-calendar-sync-button'}
          disabled={!canToggle}
          onClick={onToggle}
        >
          {reminder.calendar_sync_enabled ? <CalendarX size={17} aria-hidden="true" /> : <SyncIcon size={17} aria-hidden="true" />}
          {isSaving
            ? 'Saving...'
            : reminder.calendar_sync_enabled
              ? 'Stop syncing'
              : 'Sync to Google Calendar'}
        </button>
      ) : null}
    </section>
  )
}

function getCalendarSyncState(
  reminder: Reminder,
  calendarStatus: GoogleCalendarStatus | null,
  isCalendarStatusLoading: boolean,
) {
  if (isCalendarStatusLoading) {
    return {
      label: 'Checking calendar connection',
      description: 'Checking Google Calendar setup.',
    }
  }

  if (!calendarStatus?.configured) {
    return {
      label: 'Calendar sync not configured',
      description: 'Calendar sync is not configured for this environment.',
    }
  }

  if (!calendarStatus.connected) {
    return {
      label: 'Google Calendar not connected',
      description: 'Connect Google Calendar in Settings to sync this reminder.',
    }
  }

  if (reminder.calendar_sync_status === 'needs_attention' || reminder.calendar_sync_status === 'error') {
    return {
      label: 'Calendar sync needs attention',
      description: reminder.calendar_sync_error ?? 'Reconnect Google Calendar in Settings.',
    }
  }

  if (reminder.calendar_sync_enabled && reminder.calendar_sync_status === 'synced') {
    return {
      label: 'Synced to Google Calendar',
      description: 'This reminder is synced as an all-day event on Google Calendar.',
    }
  }

  return {
    label: 'Not synced',
    description: 'Sync this reminder as an all-day event on your selected Google Calendar.',
  }
}

function formatCalendarSyncTimestamp(value: string) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) {
    return 'Not recorded'
  }

  return timestamp.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function getDetailSectionTitle(reminder: Reminder) {
  if (reminder.reminder_type === 'birthday') {
    return 'Birthday details'
  }

  if (reminder.reminder_type === 'renewal') {
    return 'Renewal details'
  }

  if (reminder.reminder_type === 'maintenance') {
    return 'Maintenance details'
  }

  return 'Reminder details'
}

function getTypeSpecificRows(reminder: Reminder): DetailRow[] {
  if (reminder.reminder_type === 'birthday') {
    const details = reminder.birthday_details
    if (!details) {
      return []
    }

    return [
      { label: 'Person', value: details.person_name },
      { label: 'Birthday', value: formatBirthday(details.birth_month, details.birth_day) },
      { label: 'Birth year', value: details.birth_year?.toString() },
      { label: 'Turning', value: details.age_turning_next_birthday?.toString() },
      { label: 'Relationship', value: details.relationship },
    ]
  }

  if (reminder.reminder_type === 'renewal') {
    const details = reminder.renewal_details
    if (!details) {
      return []
    }

    const displayKind = getRenewalDisplayKind(details, { title: reminder.title, category: reminder.category })
    const relevantDate = getRelevantRenewalDate(details, reminder.due_date)

    return [
      { label: 'Item', value: details.item_name },
      { label: 'Renewal kind', value: getRenewalKindLabel(displayKind) },
      { label: getRenewalDateLabel(displayKind), value: relevantDate ? formatLongDate(relevantDate) : null },
      { label: 'Provider', value: details.provider },
      { label: 'Owner', value: details.owner_name },
      { label: 'Renewal window', value: details.renewal_window_days ? `${details.renewal_window_days} days` : null },
      { label: 'Review lead', value: details.review_lead_days ? `${details.review_lead_days} days` : null },
    ]
  }

  if (reminder.reminder_type === 'maintenance') {
    const details = reminder.maintenance_details
    if (!details) {
      return []
    }

    const nextDueDate = getMaintenanceDueDate(details, reminder.due_date)

    return [
      { label: 'Item', value: details.item_name },
      { label: 'Area', value: getMaintenanceAreaLabel(details.maintenance_area) },
      { label: 'Interval', value: formatInterval(details.interval_value, details.interval_unit) },
      { label: 'Last completed', value: details.last_completed_date ? formatLongDate(details.last_completed_date) : null },
      { label: 'Next due', value: nextDueDate ? formatLongDate(nextDueDate) : null },
    ]
  }

  return []
}

function getNotes(reminder: Reminder) {
  if (reminder.reminder_type === 'maintenance' && reminder.maintenance_details?.instructions) {
    return reminder.notes ? `${reminder.notes}\n\n${reminder.maintenance_details.instructions}` : reminder.maintenance_details.instructions
  }

  return reminder.notes
}

function getTypeIcon(type: Reminder['reminder_type']) {
  if (type === 'maintenance') {
    return Wrench
  }

  if (type === 'renewal') {
    return RefreshCcw
  }

  if (type === 'birthday') {
    return Cake
  }

  return Clock3
}

function canRenewReminder(reminder: Reminder) {
  return reminder.reminder_type === 'renewal' || reminder.reminder_type === 'maintenance' || reminder.repeat !== 'None'
}

function addDaysDateOnly(days: number) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return formatDateOnly(date)
}

function dateOnlyToSnoozeIso(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day, 9, 0, 0, 0).toISOString()
}

function formatDateOnly(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatLifecycleEventType(type: Reminder['lifecycle_events'][number]['event_type']) {
  const labels: Record<Reminder['lifecycle_events'][number]['event_type'], string> = {
    created: 'Created',
    edited: 'Edited',
    date_changed: 'Date changed',
    snoozed: 'Snoozed',
    snooze_cleared: 'Snooze cleared',
    completed: 'Completed',
    renewed: 'Renewed',
    archived: 'Archived',
    restored: 'Restored',
  }

  return labels[type]
}

function formatLifecycleTimestamp(value: string) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) {
    return 'Time not recorded'
  }

  return timestamp.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}
function formatBirthday(month: number, day: number) {
  const value = `2000-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  return formatMonthDay(value)
}

function formatInterval(value: number | null, unit: string | null) {
  if (!value || !unit) {
    return null
  }

  const unitLabel = value === 1 ? unit.slice(0, -1) : unit
  return `Every ${value} ${unitLabel}`
}

