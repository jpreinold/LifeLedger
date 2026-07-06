import { useMemo } from 'react'
import { LayoutTemplate, Plus } from 'lucide-react'

import { ReminderCard } from './ReminderCard'
import {
  getReminderTypeFilterLabel,
  matchesReminderStatusFilter,
  matchesReminderTypeFilter,
  reminderTypeFilters,
  type ReminderStatusFilter,
  type ReminderTypeFilter,
} from '../lib/reminderDisplay'
import type { Reminder } from '../types/reminder'

interface ReminderListProps {
  reminders: Reminder[]
  isLoading: boolean
  activeStatusFilter: ReminderStatusFilter
  activeTypeFilter: ReminderTypeFilter
  onStatusFilterChange: (filter: ReminderStatusFilter) => void
  onTypeFilterChange: (filter: ReminderTypeFilter) => void
  onComplete: (id: string) => Promise<void>
  onEdit: (reminder: Reminder) => void
  onDelete: (reminder: Reminder) => void
  onBrowseTemplates: () => void
  onAddReminder: () => void
}

export function ReminderList({
  reminders,
  isLoading,
  activeStatusFilter,
  activeTypeFilter,
  onStatusFilterChange,
  onTypeFilterChange,
  onComplete,
  onEdit,
  onDelete,
  onBrowseTemplates,
  onAddReminder,
}: ReminderListProps) {
  const visibleReminders = useMemo(
    () => reminders.filter((reminder) => matchesReminderStatusFilter(reminder, activeStatusFilter) && matchesReminderTypeFilter(reminder, activeTypeFilter)),
    [activeStatusFilter, activeTypeFilter, reminders],
  )
  const emptyState = getEmptyState(activeStatusFilter, activeTypeFilter, reminders)
  const hasDefaultFilters = activeStatusFilter === 'active' && activeTypeFilter === 'all'

  function clearFilters() {
    onStatusFilterChange('active')
    onTypeFilterChange('all')
  }

  return (
    <section className="reminders-panel" aria-labelledby="reminders-heading">
      <div className="section-heading sr-only">
        <h2 id="reminders-heading">Reminders</h2>
        <span>{isLoading ? 'Loading' : `${visibleReminders.length} shown`}</span>
      </div>

      <div className="filter-tabs reminder-type-tabs" aria-label="Filter reminders by type">
        {reminderTypeFilters.map((filter) => {
          const count = reminders.filter(
            (reminder) => matchesReminderStatusFilter(reminder, activeStatusFilter) && matchesReminderTypeFilter(reminder, filter.id),
          ).length

          return (
            <button
              type="button"
              className={`filter-tab type-filter-tab ${activeTypeFilter === filter.id ? 'active' : ''}`}
              onClick={() => onTypeFilterChange(filter.id)}
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
          {reminders.length === 0 && hasDefaultFilters ? (
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
          {!hasDefaultFilters ? (
            <div className="empty-state-actions">
              <button type="button" className="secondary-button empty-template-button" onClick={clearFilters}>
                Clear filters
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

function getEmptyState(filter: ReminderStatusFilter, typeFilter: ReminderTypeFilter, reminders: Reminder[]) {
  if (reminders.length === 0 && filter === 'active' && typeFilter === 'all') {
    return 'Add your first reminder or start from a template.'
  }

  const typeNoun = getTypeEmptyNoun(typeFilter)

  if (typeFilter !== 'all') {
    if (filter === 'active') {
      return `No active ${typeNoun}.`
    }

    if (filter === 'overdue') {
      return `No overdue ${typeNoun}.`
    }

    return `No ${typeNoun} ${getStatusEmptyPhrase(filter)}.`
  }

  if (filter === 'active') {
    return 'No active reminders.'
  }

  if (filter === 'overdue') {
    return 'No overdue reminders.'
  }

  if (filter === 'today') {
    return 'Nothing due today.'
  }

  return 'No reminders due this month.'
}

function getTypeEmptyNoun(typeFilter: ReminderTypeFilter) {
  if (typeFilter === 'maintenance') {
    return 'maintenance reminders'
  }

  return getReminderTypeFilterLabel(typeFilter).toLowerCase()
}

function getStatusEmptyPhrase(filter: ReminderStatusFilter) {
  if (filter === 'today') {
    return 'due today'
  }

  if (filter === 'month') {
    return 'due this month'
  }

  return 'matching this filter'
}
