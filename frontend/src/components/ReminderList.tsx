import { useMemo, useState } from 'react'
import { LayoutTemplate, Plus } from 'lucide-react'

import { ReminderCard } from './ReminderCard'
import {
  getReminderTypeFilterLabel,
  matchesReminderTypeFilter,
  parseDateOnly,
  reminderTypeFilters,
  startOfDay,
  type ReminderTypeFilter,
} from '../lib/reminderDisplay'
import type { Reminder } from '../types/reminder'

type ReminderFilter = 'active' | 'overdue' | 'today' | 'week' | 'month' | 'upcoming' | 'completed'

interface ReminderListProps {
  reminders: Reminder[]
  isLoading: boolean
  onComplete: (id: string) => Promise<void>
  onEdit: (reminder: Reminder) => void
  onDelete: (id: string) => Promise<void>
  onBrowseTemplates: () => void
  onAddReminder: () => void
}

const filters: Array<{ id: ReminderFilter; label: string }> = [
  { id: 'active', label: 'All active' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'today', label: 'Due today' },
  { id: 'week', label: 'Due this week' },
  { id: 'month', label: 'Due this month' },
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'completed', label: 'Completed' },
]

export function ReminderList({
  reminders,
  isLoading,
  onComplete,
  onEdit,
  onDelete,
  onBrowseTemplates,
  onAddReminder,
}: ReminderListProps) {
  const [activeFilter, setActiveFilter] = useState<ReminderFilter>('active')
  const [activeTypeFilter, setActiveTypeFilter] = useState<ReminderTypeFilter>('all')
  const visibleReminders = useMemo(
    () => reminders.filter((reminder) => matchesDateFilter(reminder, activeFilter) && matchesReminderTypeFilter(reminder, activeTypeFilter)),
    [activeFilter, activeTypeFilter, reminders],
  )
  const emptyState = getEmptyState(activeFilter, activeTypeFilter, reminders)

  return (
    <section className="reminders-panel" aria-labelledby="reminders-heading">
      <div className="section-heading sr-only">
        <h2 id="reminders-heading">Reminders</h2>
        <span>{isLoading ? 'Loading' : `${visibleReminders.length} shown`}</span>
      </div>

      <div className="filter-tabs" aria-label="Filter reminders by date or status">
        {filters.map((filter) => {
          const count = reminders.filter(
            (reminder) => matchesDateFilter(reminder, filter.id) && matchesReminderTypeFilter(reminder, activeTypeFilter),
          ).length

          return (
            <button
              type="button"
              className={`filter-tab ${activeFilter === filter.id ? 'active' : ''}`}
              onClick={() => setActiveFilter(filter.id)}
              aria-pressed={activeFilter === filter.id}
              key={filter.id}
            >
              <span>{filter.label}</span>
              <strong>{count}</strong>
            </button>
          )
        })}
      </div>

      <div className="filter-tabs reminder-type-tabs" aria-label="Filter reminders by type">
        {reminderTypeFilters.map((filter) => {
          const count = reminders.filter(
            (reminder) => matchesDateFilter(reminder, activeFilter) && matchesReminderTypeFilter(reminder, filter.id),
          ).length

          return (
            <button
              type="button"
              className={`filter-tab type-filter-tab ${activeTypeFilter === filter.id ? 'active' : ''}`}
              onClick={() => setActiveTypeFilter(filter.id)}
              aria-pressed={activeTypeFilter === filter.id}
              key={filter.id}
            >
              <span>{filter.label}</span>
              <strong>{count}</strong>
            </button>
          )
        })}
      </div>

      {isLoading ? <p className="empty-state">Loading reminders...</p> : null}

      {!isLoading && visibleReminders.length === 0 ? (
        <div className="empty-state empty-state-card">
          <p>{emptyState}</p>
          {reminders.length === 0 && activeFilter === 'active' && activeTypeFilter === 'all' ? (
            <div className="empty-state-actions">
              <button type="button" className="secondary-button empty-template-button" onClick={onBrowseTemplates}>
                <LayoutTemplate size={17} aria-hidden="true" />
                Browse templates
              </button>
              <button type="button" className="primary-button empty-add-button" onClick={onAddReminder}>
                <Plus size={17} aria-hidden="true" />
                Add reminder
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="reminder-list">
        {visibleReminders.map((reminder) => (
          <ReminderCard
            reminder={reminder}
            key={reminder.id}
            onComplete={onComplete}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
      </div>
    </section>
  )
}

function matchesDateFilter(reminder: Reminder, filter: ReminderFilter) {
  if (filter === 'completed') {
    return reminder.completed
  }

  if (reminder.completed) {
    return false
  }

  if (filter === 'active') {
    return true
  }

  if (filter === 'overdue') {
    return reminder.status === 'Overdue'
  }

  if (filter === 'today') {
    return reminder.status === 'Due today'
  }

  if (filter === 'week') {
    return reminder.status === 'Due today' || reminder.status === 'Due this week'
  }

  if (filter === 'month') {
    return isDueThisMonth(reminder.due_date)
  }

  return reminder.status === 'Upcoming'
}

function isDueThisMonth(value: string) {
  const dueDate = parseDateOnly(value)
  const today = startOfDay(new Date())

  return (
    dueDate >= today &&
    dueDate.getFullYear() === today.getFullYear() &&
    dueDate.getMonth() === today.getMonth()
  )
}

function getEmptyState(filter: ReminderFilter, typeFilter: ReminderTypeFilter, reminders: Reminder[]) {
  if (reminders.length === 0 && filter === 'active' && typeFilter === 'all') {
    return 'Add your first reminder or start from a template.'
  }

  const hasType = typeFilter === 'all' || reminders.some((reminder) => matchesReminderTypeFilter(reminder, typeFilter))
  if (!hasType) {
    const typeEmptyStates: Record<Exclude<ReminderTypeFilter, 'all'>, string> = {
      generic: 'Add your first reminder or start from a template.',
      birthday: 'Add a birthday to track important dates and calculate ages.',
      renewal: 'Add a renewal or expiration to keep important dates from sneaking up on you.',
      maintenance: 'Add maintenance reminders for recurring home, vehicle, pet, or personal tasks.',
    }

    return typeEmptyStates[typeFilter as Exclude<ReminderTypeFilter, 'all'>]
  }

  if (typeFilter !== 'all') {
    return `No ${getReminderTypeFilterLabel(typeFilter).toLowerCase()} match this filter.`
  }

  const emptyStates: Record<ReminderFilter, string> = {
    active: 'No active reminders.',
    overdue: 'No overdue reminders.',
    today: 'Nothing due today.',
    week: 'No reminders due this week.',
    month: 'No reminders due this month.',
    upcoming: 'No upcoming reminders.',
    completed: 'No completed reminders yet.',
  }

  return emptyStates[filter]
}
