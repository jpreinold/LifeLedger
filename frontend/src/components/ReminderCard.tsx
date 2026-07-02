import { Check, Trash2 } from 'lucide-react'

import type { Reminder } from '../types/reminder'

interface ReminderCardProps {
  reminder: Reminder
  onComplete: (id: string) => Promise<void>
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

export function ReminderCard({ reminder, onComplete, onDelete }: ReminderCardProps) {
  return (
    <article className="reminder-card">
      <div className="card-topline">
        <span className="category-chip">{reminder.category}</span>
        <span className={`status-chip ${statusClassNames[reminder.status]}`}>{reminder.status}</span>
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
          className="secondary-button"
          onClick={() => void onComplete(reminder.id)}
          disabled={reminder.completed}
        >
          <Check size={17} aria-hidden="true" />
          {reminder.completed ? 'Completed' : 'Complete'}
        </button>
        <button type="button" className="danger-button" onClick={() => void onDelete(reminder.id)}>
          <Trash2 size={17} aria-hidden="true" />
          Delete
        </button>
      </div>
    </article>
  )
}

function formatDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(year, month - 1, day))
}
