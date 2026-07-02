import { ReminderCard } from './ReminderCard'
import type { Reminder } from '../types/reminder'

interface ReminderListProps {
  reminders: Reminder[]
  isLoading: boolean
  onComplete: (id: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
}

export function ReminderList({ reminders, isLoading, onComplete, onDelete }: ReminderListProps) {
  return (
    <section className="list-panel" aria-labelledby="reminders-heading">
      <div className="section-heading">
        <h2 id="reminders-heading">Reminders</h2>
        <span>{isLoading ? 'Loading' : `${reminders.length} total`}</span>
      </div>

      {isLoading ? <p className="empty-state">Loading reminders...</p> : null}

      {!isLoading && reminders.length === 0 ? <p className="empty-state">No reminders yet.</p> : null}

      <div className="reminder-list">
        {reminders.map((reminder) => (
          <ReminderCard
            reminder={reminder}
            key={reminder.id}
            onComplete={onComplete}
            onDelete={onDelete}
          />
        ))}
      </div>
    </section>
  )
}
