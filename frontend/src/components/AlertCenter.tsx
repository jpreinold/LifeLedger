import { CheckCircle2, Clock3, Eye, X } from 'lucide-react'

import { getAttentionDetail, getAttentionLabel, getAttentionTone } from '../lib/attentionDisplay'
import { getReminderTypeLabel } from '../lib/reminderDisplay'
import { toAttentionReminder, type AttentionReminder } from '../lib/reminderSchedule'
import type { Reminder, ReminderAlert } from '../types/reminder'
import { getCategoryVisual } from './categoryVisuals'
import { SheetDrawer } from './SheetDrawer'

interface AlertCenterProps {
  alerts: ReminderAlert[]
  isLoading: boolean
  isOpen: boolean
  onClose: () => void
  onComplete: (id: string) => Promise<void>
  onDismiss: (id: string) => Promise<void>
  onSnooze: (id: string) => Promise<void>
  onView: (reminder: Reminder) => void
}

export function AlertCenter({
  alerts,
  isLoading,
  isOpen,
  onClose,
  onComplete,
  onDismiss,
  onSnooze,
  onView,
}: AlertCenterProps) {
  const attentionItems = alerts.map(toAttentionReminder)

  return (
    <SheetDrawer className="alerts-dialog" isOpen={isOpen} labelledBy="alerts-heading" onClose={onClose}>
      <div className="sheet-header alerts-header">
        <div>
          <h2 id="alerts-heading">Needs attention</h2>
          <p>{formatAlertCount(alerts.length, isLoading)}</p>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close alerts">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="alerts-body">
        {isLoading ? <p className="alerts-empty-state">Loading alerts...</p> : null}

        {!isLoading && attentionItems.length === 0 ? (
          <div className="alerts-empty-state alerts-empty-card">
            <CheckCircle2 size={24} aria-hidden="true" />
            <p>Nothing needs attention right now.</p>
          </div>
        ) : null}

        {!isLoading && attentionItems.length > 0 ? (
          <div className="alerts-list">
            {attentionItems.map((item) => (
              <AlertItem
                item={item}
                key={item.reminder.id}
                onComplete={onComplete}
                onDismiss={onDismiss}
                onSnooze={onSnooze}
                onView={onView}
              />
            ))}
          </div>
        ) : null}
      </div>
    </SheetDrawer>
  )
}

function AlertItem({
  item,
  onComplete,
  onDismiss,
  onSnooze,
  onView,
}: {
  item: AttentionReminder
  onComplete: (id: string) => Promise<void>
  onDismiss: (id: string) => Promise<void>
  onSnooze: (id: string) => Promise<void>
  onView: (reminder: Reminder) => void
}) {
  const { reminder } = item
  const { Icon, tone } = getCategoryVisual(reminder.category)
  const detail = getAlertDetail(item)

  return (
    <article className={`alert-center-item tone-${tone}`}>
      <button type="button" className="alert-center-main alert-center-main-button" onClick={() => onView(reminder)}>
        <div className={`alert-center-icon tone-${tone}`} aria-hidden="true">
          <Icon size={21} />
        </div>

        <div className="alert-center-copy">
          <span className={`alert-center-reason alert-center-reason-${getAlertTone(item)}`}>
            {getAlertReasonLabel(item)}
          </span>
          <h3>{reminder.title}</h3>
          <p>{detail}</p>
          <small>
            {getReminderTypeLabel(reminder.reminder_type)} {'\u2022'} {reminder.category}
          </small>
        </div>
      </button>

      <div className="alert-center-actions">
        <button type="button" className="secondary-button alert-action-secondary" onClick={() => onView(reminder)}>
          <Eye size={16} aria-hidden="true" />
          View
        </button>
        <button type="button" className="primary-button alert-action-primary" onClick={() => void onComplete(reminder.id)}>
          <CheckCircle2 size={16} aria-hidden="true" />
          Complete
        </button>
        <button type="button" className="small-outline-button alert-action-chip" onClick={() => void onDismiss(reminder.id)}>
          Dismiss for now
        </button>
        <button type="button" className="small-outline-button alert-action-chip" onClick={() => void onSnooze(reminder.id)}>
          <Clock3 size={14} aria-hidden="true" />
          Remind tomorrow
        </button>
      </div>
    </article>
  )
}

function formatAlertCount(count: number, isLoading: boolean) {
  if (isLoading) {
    return 'Checking reminders that need attention.'
  }

  return count === 1 ? '1 reminder needs attention.' : `${count} reminders need attention.`
}

function getAlertReasonLabel(item: AttentionReminder) {
  return getAttentionLabel(item, { windowLabel: 'Reminder window started' })
}

function getAlertDetail(item: AttentionReminder) {
  return getAttentionDetail(item, { windowSeparator: '. ' })
}

const getAlertTone = getAttentionTone

