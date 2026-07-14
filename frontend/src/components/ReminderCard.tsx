import { Cake, CalendarDays, CheckCircle2, Flag, RefreshCcw, Repeat2, Trash2, Wrench } from 'lucide-react'

import type { Reminder } from '../types/reminder'
import {
  formatReminderAttentionLabel,
  formatReminderDueLabel,
  formatReminderStatusLabel,
  formatRepeatLabel,
  getReminderTypeLabel,
} from '../lib/reminderDisplay'
import { getSmartReminderLabel } from '../lib/smartReminderLabels'
import { getCategoryVisual } from './categoryVisuals'

interface ReminderCardProps {
  reminder: Reminder
  onComplete: (id: string) => Promise<void>
  onDelete: (reminder: Reminder) => void
  onView: (reminder: Reminder) => void
  isActionPending?: boolean
}

const statusClassNames: Record<Reminder['status'], string> = {
  Completed: 'status-completed',
  Overdue: 'status-overdue',
  'Due today': 'status-today',
  Urgent: 'status-urgent',
  Upcoming: 'status-upcoming',
  Scheduled: 'status-scheduled',
}

export function ReminderCard({ reminder, onComplete, onDelete, onView, isActionPending = false }: ReminderCardProps) {
  const { Icon, tone } = getCategoryVisual(reminder.category)
  const smartLabel = reminder.completed ? null : getSmartReminderLabel(reminder)
  const repeatLabel = formatRepeatLabel(reminder.repeat)
  const shouldShowRepeat = repeatLabel && reminder.reminder_type !== 'birthday' && reminder.reminder_type !== 'maintenance'
  const shouldShowPriority = reminder.priority === 'High'
  const attentionLabel = formatReminderAttentionLabel(reminder, { includeDate: false })
  const summaryLabel = smartLabel ?? attentionLabel
  const linkedRecord = reminder.linked_records.find((record) => record.status !== 'archived') ?? reminder.linked_records[0]
  const ownerLine = getReminderOwnerLine(reminder)
  const SmartIcon = reminder.reminder_type === 'maintenance'
    ? Wrench
    : reminder.reminder_type === 'renewal'
      ? RefreshCcw
      : Cake

  return (
    <article className={`reminder-card tone-${tone}`}>
      <span className="reminder-card-accent" aria-hidden="true" />

      <button type="button" className="reminder-card-body-button" onClick={() => onView(reminder)}>
        <div className="reminder-card-main">
          <div className={`category-icon tone-${tone}`} aria-hidden="true">
            <Icon size={24} />
          </div>

          <div className="reminder-card-content">
            <div className="card-topline">
              <span className="card-chip-row">
                <span className="category-chip">{reminder.category}</span>
                <span className="type-chip">{getReminderTypeLabel(reminder.reminder_type)}</span>
              </span>
              <span className={`status-chip ${statusClassNames[reminder.status]}`}>
                {formatReminderStatusLabel(reminder)}
              </span>
            </div>

            <div>
              <h3>{reminder.title}</h3>
              <p className="reminder-summary-line">
                <span>{linkedRecord ? linkedRecord.title : reminder.category}</span>
                <span aria-hidden="true">{`\u2022`}</span>
                <span className={smartLabel ? 'smart-summary-text' : undefined}>
                  {smartLabel ? (
                    <>
                      <SmartIcon size={14} aria-hidden="true" />
                      {smartLabel}
                    </>
                  ) : summaryLabel}
                </span>
              </p>
              <p className="due-date">
                <CalendarDays size={15} aria-hidden="true" />
                {formatReminderDueLabel(reminder)}
              </p>
              {ownerLine ? <p className="reminder-owner-line">{ownerLine}</p> : null}
            </div>

            {shouldShowRepeat || shouldShowPriority ? (
              <div className="reminder-meta-row" aria-label="Reminder details">
                {shouldShowRepeat ? (
                  <span>
                    <Repeat2 size={14} aria-hidden="true" />
                    {repeatLabel}
                  </span>
                ) : null}
                {shouldShowPriority ? (
                  <span className={`priority-chip priority-${reminder.priority.toLowerCase()}`}>
                    <Flag size={14} aria-hidden="true" />
                    {reminder.priority} priority
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        {reminder.notes ? <p className="notes">{reminder.notes}</p> : null}
      </button>

      <div className="card-actions">
        <button
          type="button"
          className="action-button complete-button"
          onClick={() => void onComplete(reminder.id)}
          disabled={reminder.completed || isActionPending}
        >
          <CheckCircle2 size={18} aria-hidden="true" />
          {isActionPending ? 'Saving' : reminder.completed ? 'Completed' : 'Complete'}
        </button>
        <button type="button" className="action-button delete-button" onClick={() => onDelete(reminder)} disabled={isActionPending}>
          <Trash2 size={17} aria-hidden="true" />
          Delete
        </button>
      </div>
    </article>
  )
}

function getReminderOwnerLine(reminder: Reminder) {
  if (reminder.reminder_type === 'birthday') {
    return reminder.birthday_details?.relationship || reminder.birthday_details?.person_name || null
  }

  if (reminder.reminder_type === 'renewal') {
    return [reminder.renewal_details?.owner_name, reminder.renewal_details?.provider].filter(Boolean).join(' - ') || null
  }

  if (reminder.reminder_type === 'maintenance') {
    return reminder.maintenance_details?.item_name ?? null
  }

  return null
}