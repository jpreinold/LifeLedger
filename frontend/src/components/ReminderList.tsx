import { useMemo } from 'react'
import { LayoutTemplate, Plus } from 'lucide-react'

import { ReminderCard } from './ReminderCard'
import {
  getActionCenterGroups,
  getReminderTypeFilterLabel,
  matchesReminderStatusFilter,
  matchesReminderTypeFilter,
  reminderTypeFilters,
  sortActionCenterReminders,
  type ActionCenterGroup,
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
  onDelete: (reminder: Reminder) => void
  onView: (reminder: Reminder) => void
  onBrowseTemplates: () => void
  onAddReminder: () => void
  pendingActionId?: string | null
}

export function ReminderList({
  reminders,
  isLoading,
  activeStatusFilter,
  activeTypeFilter,
  onStatusFilterChange,
  onTypeFilterChange,
  onComplete,
  onDelete,
  onView,
  onBrowseTemplates,
  onAddReminder,
  pendingActionId = null,
}: ReminderListProps) {
  const typedReminders = useMemo(
    () => reminders.filter((reminder) => matchesReminderTypeFilter(reminder, activeTypeFilter)),
    [activeTypeFilter, reminders],
  )
  const visibleReminders = useMemo(
    () => typedReminders
      .filter((reminder) => matchesReminderStatusFilter(reminder, activeStatusFilter))
      .sort(sortActionCenterReminders),
    [activeStatusFilter, typedReminders],
  )
  const actionGroups = useMemo(
    () => activeStatusFilter === 'active'
      ? getActionCenterGroups(typedReminders).filter((group) => group.reminders.length > 0)
      : [],
    [activeStatusFilter, typedReminders],
  )
  const emptyState = getEmptyState(activeStatusFilter, activeTypeFilter, reminders)
  const hasDefaultFilters = activeStatusFilter === 'active' && activeTypeFilter === 'all'

  function clearFilters() {
    onStatusFilterChange('active')
    onTypeFilterChange('all')
  }

  return (
    <section className="reminders-panel action-center-panel" aria-labelledby="reminders-heading">
      <div className="section-heading action-center-heading">
        <div>
          <h2 id="reminders-heading">Action Center</h2>
          <p>{activeStatusFilter === 'completed' ? 'Completed reminder history.' : 'Reminders that need attention, grouped by urgency.'}</p>
        </div>
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

      {!isLoading && activeStatusFilter === 'active' && actionGroups.length > 0 ? (
        <div className="action-center-groups">
          {actionGroups.map((group) => (
            <ActionCenterGroupSection
              group={group}
              key={group.id}
              onComplete={onComplete}
              onDelete={onDelete}
              onView={onView}
              pendingActionId={pendingActionId}
            />
          ))}
        </div>
      ) : null}

      {!isLoading && activeStatusFilter !== 'active' && visibleReminders.length > 0 ? (
        <div className="reminder-list">
          {visibleReminders.map((reminder) => (
            <ReminderCard
              reminder={reminder}
              key={reminder.id}
              isActionPending={pendingActionId === reminder.id}
              onComplete={onComplete}
              onDelete={onDelete}
              onView={onView}
            />
          ))}
        </div>
      ) : null}
    </section>
  )
}

function ActionCenterGroupSection({
  group,
  onComplete,
  onDelete,
  onView,
  pendingActionId,
}: {
  group: ActionCenterGroup
  onComplete: (id: string) => Promise<void>
  onDelete: (reminder: Reminder) => void
  onView: (reminder: Reminder) => void
  pendingActionId: string | null
}) {
  return (
    <section className={`action-center-group action-center-group-${group.id}`} aria-labelledby={`action-group-${group.id}`}>
      <div className="action-center-group-heading">
        <h3 id={`action-group-${group.id}`}>{group.title}</h3>
        <span>{group.reminders.length}</span>
      </div>
      <div className="reminder-list">
        {group.reminders.map((reminder) => (
          <ReminderCard
            reminder={reminder}
            key={reminder.id}
            isActionPending={pendingActionId === reminder.id}
            onComplete={onComplete}
            onDelete={onDelete}
            onView={onView}
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

    if (filter === 'completed') {
      return `No completed ${typeNoun}.`
    }

    return `No upcoming ${typeNoun}.`
  }

  if (filter === 'active') {
    return 'No active reminders.'
  }

  if (filter === 'overdue') {
    return 'No overdue reminders.'
  }

  if (filter === 'completed') {
    return 'No completed reminder history.'
  }

  return 'No upcoming reminders.'
}

function getTypeEmptyNoun(typeFilter: ReminderTypeFilter) {
  if (typeFilter === 'maintenance') {
    return 'maintenance reminders'
  }

  return getReminderTypeFilterLabel(typeFilter).toLowerCase()
}