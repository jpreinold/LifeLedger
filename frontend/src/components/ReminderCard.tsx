import { Bell, Cake, CalendarDays, CheckCircle2, Flag, Pencil, RefreshCcw, Repeat2, Trash2, Wrench } from 'lucide-react'

import type { Reminder } from '../types/reminder'
import { formatReminderTiming } from '../lib/reminderSchedule'
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
  const smartLabel = getSmartReminderLabel(reminder)
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
            <span className="category-chip">{reminder.category}</span>
            <span className={`status-chip ${statusClassNames[reminder.status]}`}>{getStatusLabel(reminder)}</span>
          </div>

          <div>
            <h3>{reminder.title}</h3>
            <p className="due-date">
              <CalendarDays size={15} aria-hidden="true" />
              {getDueLabel(reminder)}
            </p>
          </div>

          <div className="reminder-meta-row" aria-label="Reminder details">
            <span>
              <Repeat2 size={14} aria-hidden="true" />
              {reminder.repeat}
            </span>
            <span className={`priority-chip priority-${reminder.priority.toLowerCase()}`}>
              <Flag size={14} aria-hidden="true" />
              {reminder.priority}
            </span>
            <span>
              <Bell size={14} aria-hidden="true" />
              {formatReminderTiming(reminder)}
            </span>
            {smartLabel ? (
              <span className="smart-context-chip">
                <SmartIcon size={14} aria-hidden="true" />
                {smartLabel}
              </span>
            ) : null}
            {reminder.next_due_date && reminder.reminder_type !== 'maintenance' ? (
              <span>Next {formatShortDate(reminder.next_due_date)}</span>
            ) : null}
          </div>
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
          Complete
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

function getStatusLabel(reminder: Reminder) {
  if (reminder.status !== 'Overdue' || reminder.completed) {
    return reminder.status
  }

  const overdueDays = getDaysOverdue(reminder.due_date)

  if (overdueDays >= 14) {
    const weeks = Math.floor(overdueDays / 7)
    return `Overdue by ${weeks} ${weeks === 1 ? 'week' : 'weeks'}`
  }

  return `Overdue by ${overdueDays} ${overdueDays === 1 ? 'day' : 'days'}`
}

function getDaysOverdue(value: string) {
  const dueDate = parseDateOnly(value)
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const difference = today.getTime() - dueDate.getTime()
  const days = Math.ceil(difference / 86_400_000)

  return Math.max(days, 1)
}

function formatDate(value: string) {
  const date = parseDateOnly(value)

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

function formatShortDate(value: string) {
  const date = parseDateOnly(value)

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(date)
}

function getDueLabel(reminder: Reminder) {
  if (reminder.completed) {
    return `Completed ${reminder.completed_at ? formatShortDate(reminder.completed_at) : ''}`.trim()
  }

  if (reminder.status === 'Overdue') {
    return `Due ${formatShortDate(reminder.due_date)}`
  }

  if (reminder.status === 'Due today') {
    return `Due today \u00b7 ${formatShortDate(reminder.due_date)}`
  }

  const daysUntilDue = getDaysUntilDue(reminder.due_date)

  if (daysUntilDue > 0 && daysUntilDue <= 14) {
    return `Due in ${daysUntilDue} ${daysUntilDue === 1 ? 'day' : 'days'} \u00b7 ${formatShortDate(reminder.due_date)}`
  }

  return `Due ${formatDate(reminder.due_date)}`
}

function getDaysUntilDue(value: string) {
  const dueDate = parseDateOnly(value)
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const difference = dueDate.getTime() - today.getTime()
  return Math.ceil(difference / 86_400_000)
}

function parseDateOnly(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}
