import { Check, Pencil, Trash2 } from 'lucide-react'

import type { Reminder } from '../types/reminder'

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
  const completeLabel = reminder.completed
    ? 'Completed'
    : reminder.repeat === 'None'
      ? 'Complete'
      : 'Complete & advance'

  return (
    <article className="reminder-card">
      <div className="card-topline">
        <span className="category-chip">{reminder.category}</span>
        <span className={`status-chip ${statusClassNames[reminder.status]}`}>{getStatusLabel(reminder)}</span>
      </div>

      <div>
        <h3>{reminder.title}</h3>
        <p className="due-date">{formatDate(reminder.due_date)}</p>
      </div>

      <dl className="metadata-grid">
        <div>
          <dt>Repeat</dt>
          <dd>{reminder.repeat}</dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>{reminder.priority}</dd>
        </div>
        {reminder.next_due_date ? (
          <div>
            <dt>Next</dt>
            <dd>{formatDate(reminder.next_due_date)}</dd>
          </div>
        ) : null}
      </dl>

      {reminder.notes ? <p className="notes">{reminder.notes}</p> : null}

      <div className="card-actions">
        <button
          type="button"
          className="secondary-button complete-button"
          onClick={() => void onComplete(reminder.id)}
          disabled={reminder.completed}
        >
          <Check size={17} aria-hidden="true" />
          {completeLabel}
        </button>
        <button type="button" className="secondary-button" onClick={() => onEdit(reminder)}>
          <Pencil size={17} aria-hidden="true" />
          Edit
        </button>
        <button type="button" className="danger-button" onClick={() => void onDelete(reminder.id)}>
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

function parseDateOnly(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}
