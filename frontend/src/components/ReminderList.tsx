import { ReminderCard } from './ReminderCard'
import type { Reminder } from '../types/reminder'

interface ReminderListProps {
  reminders: Reminder[]
  isLoading: boolean
  onComplete: (id: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
  onBrowseTemplates: () => void
}

export function ReminderList({ reminders, isLoading, onComplete, onDelete, onBrowseTemplates }: ReminderListProps) {
  return (
    <section className="list-panel" aria-labelledby="reminders-heading">
      <div className="section-heading">
        <h2 id="reminders-heading">Reminders</h2>
        <span>{isLoading ? 'Loading' : `${reminders.length} total`}</span>
      </div>

      {isLoading ? <p className="empty-state">Loading reminders...</p> : null}

      {!isLoading && reminders.length === 0 ? (
        <div className="empty-state">
          <p>Start with a life admin template like vehicle registration, annual checkup, or subscription review.</p>
          <button type="button" className="secondary-button empty-template-button" onClick={onBrowseTemplates}>
            Browse templates
          </button>
        </div>
      ) : null}

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
