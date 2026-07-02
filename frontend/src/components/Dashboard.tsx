import { AlertTriangle, CalendarCheck, CalendarClock, ListChecks } from 'lucide-react'

import type { Reminder } from '../types/reminder'

interface DashboardProps {
  reminders: Reminder[]
}

export function Dashboard({ reminders }: DashboardProps) {
  const activeCount = reminders.filter((reminder) => !reminder.completed).length
  const overdueCount = reminders.filter((reminder) => reminder.status === 'Overdue').length
  const dueThisWeekCount = reminders.filter((reminder) =>
    ['Due today', 'Due this week'].includes(reminder.status),
  ).length
  const dueThisMonthCount = reminders.filter((reminder) =>
    ['Due today', 'Due this week', 'Due this month'].includes(reminder.status),
  ).length

  const stats = [
    { label: 'Active', value: activeCount, icon: ListChecks },
    { label: 'Overdue', value: overdueCount, icon: AlertTriangle },
    { label: 'This week', value: dueThisWeekCount, icon: CalendarClock },
    { label: 'This month', value: dueThisMonthCount, icon: CalendarCheck },
  ]

  return (
    <section className="dashboard-grid" aria-label="Reminder summary">
      {stats.map((stat) => {
        const Icon = stat.icon

        return (
          <article className="stat-card" key={stat.label}>
            <Icon size={18} aria-hidden="true" />
            <span>{stat.label}</span>
            <strong>{stat.value}</strong>
          </article>
        )
      })}
    </section>
  )
}
