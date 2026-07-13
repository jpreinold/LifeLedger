import {
  AlertTriangle,
  CalendarCheck,
  CalendarClock,
  Check,
  ListChecks,
} from 'lucide-react'

import {
  matchesReminderStatusFilter,
  matchesReminderTypeFilter,
  type ReminderStatusFilter,
  type ReminderTypeFilter,
} from '../lib/reminderDisplay'
import type { Reminder } from '../types/reminder'

interface DashboardProps {
  reminders: Reminder[]
  activeStatusFilter?: ReminderStatusFilter
  activeTypeFilter?: ReminderTypeFilter
  onStatusFilterChange?: (filter: ReminderStatusFilter) => void
}

export function Dashboard({
  reminders,
  activeStatusFilter = 'active',
  activeTypeFilter = 'all',
  onStatusFilterChange,
}: DashboardProps) {
  const scopedReminders = reminders.filter((reminder) => matchesReminderTypeFilter(reminder, activeTypeFilter))
  const stats: Array<{ id: ReminderStatusFilter; label: string; value: number; icon: typeof ListChecks; tone: string }> = [
    {
      id: 'active',
      label: 'All active',
      value: scopedReminders.filter((reminder) => matchesReminderStatusFilter(reminder, 'active')).length,
      icon: ListChecks,
      tone: 'blue',
    },
    {
      id: 'overdue',
      label: 'Overdue',
      value: scopedReminders.filter((reminder) => matchesReminderStatusFilter(reminder, 'overdue')).length,
      icon: AlertTriangle,
      tone: 'red',
    },
    {
      id: 'today',
      label: 'Due today',
      value: scopedReminders.filter((reminder) => matchesReminderStatusFilter(reminder, 'today')).length,
      icon: CalendarClock,
      tone: 'orange',
    },
    {
      id: 'month',
      label: 'Due this month',
      value: scopedReminders.filter((reminder) => matchesReminderStatusFilter(reminder, 'month')).length,
      icon: CalendarCheck,
      tone: 'green',
    },
  ]

  return (
    <section className="dashboard-summary-card" aria-label="Reminder summary">
      {stats.map((stat) => {
        const Icon = stat.icon
        const isSelected = activeStatusFilter === stat.id

        return (
          <button
            type="button"
            className={`stat-item stat-item-${stat.tone} ${isSelected ? 'stat-item-selected' : ''}`}
            key={stat.id}
            onClick={() => onStatusFilterChange?.(stat.id)}
            aria-pressed={isSelected}
          >
            {isSelected ? (
              <span className="stat-selected-indicator" aria-hidden="true">
                <Check size={12} />
              </span>
            ) : null}
            <Icon size={20} aria-hidden="true" />
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
          </button>
        )
      })}
    </section>
  )
}
