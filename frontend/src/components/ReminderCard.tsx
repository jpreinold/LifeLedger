import { Cake, CalendarDays, CheckCircle2, Flag, Pencil, RefreshCcw, Repeat2, Trash2, Wrench } from 'lucide-react'

import type { Reminder } from '../types/reminder'
import {
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
  onEdit: (reminder: Reminder) => void
  onDelete: (id: string) => Promise<void>
}

const statusClassNames: Record<Reminder['status'], string> = {
  Completed: 'status-completed',
  Overdue: 'status-overdue',
  'Due today': 'status-today',
  'Due this week': 'status-week',
  'Due this month': 'status-month',
  Upcoming: 'status-upcoming',
}

export function ReminderCard({ reminder, onComplete, onEdit, onDelete }: ReminderCardProps) {
  const { Icon, tone } = getCategoryVisual(reminder.category)
  const smartLabel = reminder.completed ? null : getSmartReminderLabel(reminder)
  const repeatLabel = formatRepeatLabel(reminder.repeat)
  const shouldShowRepeat = repeatLabel && reminder.reminder_type !== 'birthday' && reminder.reminder_type !== 'maintenance'
  const shouldShowPriority = reminder.priority === 'High'
  const summaryLabel = smartLabel ?? formatReminderDueLabel(reminder, { includeDate: false })
  const SmartIcon = reminder.reminder_type === 'maintenance'
    ? Wrench
    : reminder.reminder_type === 'renewal'
      ? RefreshCcw
      : Cake

  return (
    <article className={`reminder-card tone-${tone}`}>
      <span className="reminder-card-accent" aria-hidden="true" />

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
              <span>{reminder.category}</span>
              <span aria-hidden="true">{'\u2022'}</span>
              <span className={smartLabel ? 'smart-summary-text' : undefined}>
                {smartLabel ? (
                  <>
                    <SmartIcon size={14} aria-hidden="true" />
                    {smartLabel}
                  </>
                ) : summaryLabel}
              </span>
            </p>
            {smartLabel ? (
              <p className="due-date">
                <CalendarDays size={15} aria-hidden="true" />
                {formatReminderDueLabel(reminder)}
              </p>
            ) : null}
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

      <div className="card-actions">
        <button
          type="button"
          className="action-button complete-button"
          onClick={() => void onComplete(reminder.id)}
          disabled={reminder.completed}
        >
          <CheckCircle2 size={18} aria-hidden="true" />
          {reminder.completed ? 'Completed' : 'Complete'}
        </button>
        <button type="button" className="action-button edit-button" onClick={() => onEdit(reminder)}>
          <Pencil size={17} aria-hidden="true" />
          Edit
        </button>
        <button type="button" className="action-button delete-button" onClick={() => void onDelete(reminder.id)}>
          <Trash2 size={17} aria-hidden="true" />
          Delete
        </button>
      </div>
    </article>
  )
}
