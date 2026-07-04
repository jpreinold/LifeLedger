import { AlertTriangle, CalendarCheck, CalendarClock, ListChecks } from 'lucide-react'

import type { Reminder } from '../types/reminder'

interface DashboardProps {
  reminders: Reminder[]
}

export function Dashboard({ reminders }: DashboardProps) {
  const activeCount = reminders.filter((reminder) => !reminder.completed).length
  const overdueCount = reminders.filter((reminder) => reminder.status === 'Overdue').length
  const dueTodayCount = reminders.filter((reminder) => reminder.status === 'Due today').length
  const dueThisWeekCount = reminders.filter((reminder) =>
    ['Due today', 'Due this week'].includes(reminder.status),
  ).length

  const stats = [
    { label: 'All active', value: activeCount, icon: ListChecks, tone: 'blue' },
    { label: 'Overdue', value: overdueCount, icon: AlertTriangle, tone: 'red' },
    { label: 'Due today', value: dueTodayCount, icon: CalendarClock, tone: 'orange' },
    { label: 'Due this week', value: dueThisWeekCount, icon: CalendarCheck, tone: 'green' },
  ]

  return (
    <section className="dashboard-summary-card" aria-label="Reminder summary">
      {stats.map((stat) => {
        const Icon = stat.icon

        return (
          <article className={`stat-item stat-item-${stat.tone}`} key={stat.label}>
            <Icon size={20} aria-hidden="true" />
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
          </article>
        )
      })}
    </section>
  )
}
