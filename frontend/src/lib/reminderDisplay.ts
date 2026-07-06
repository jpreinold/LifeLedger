import type { Reminder, ReminderType } from '../types/reminder'

const dayMs = 86_400_000

export type ReminderTypeFilter = 'all' | ReminderType

export type ReminderStatusFilter = 'active' | 'overdue' | 'today' | 'month'

export const reminderStatusFilters: Array<{ id: ReminderStatusFilter; label: string }> = [
  { id: 'active', label: 'All active' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'today', label: 'Due today' },
  { id: 'month', label: 'Due this month' },
]
export const reminderTypeFilters: Array<{ id: ReminderTypeFilter; label: string }> = [
  { id: 'all', label: 'All types' },
  { id: 'generic', label: 'Reminders' },
  { id: 'birthday', label: 'Birthdays' },
  { id: 'renewal', label: 'Renewals' },
  { id: 'maintenance', label: 'Maintenance' },
]

const reminderTypeLabels: Record<ReminderType, string> = {
  generic: 'Reminder',
  birthday: 'Birthday',
  renewal: 'Renewal',
  maintenance: 'Maintenance',
}

export function getReminderTypeLabel(type: ReminderType | null | undefined) {
  return reminderTypeLabels[type ?? 'generic']
}

export function getReminderStatusFilterLabel(filter: ReminderStatusFilter) {
  return reminderStatusFilters.find((item) => item.id === filter)?.label ?? 'All active'
}

export function matchesReminderStatusFilter(reminder: Reminder, filter: ReminderStatusFilter) {
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

  return isDueThisMonth(reminder.due_date)
}

export function getReminderTypeFilterLabel(filter: ReminderTypeFilter) {
  return reminderTypeFilters.find((item) => item.id === filter)?.label ?? 'All types'
}

export function matchesReminderTypeFilter(reminder: Reminder, filter: ReminderTypeFilter) {
  return filter === 'all' || (reminder.reminder_type ?? 'generic') === filter
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

export function formatReminderStatusLabel(reminder: Reminder) {
  if (reminder.completed) {
    return 'Completed'
  }

  if (reminder.status === 'Overdue') {
    return formatOverdueLabel(reminder.due_date)
  }

  return reminder.status
}

export function formatReminderDueLabel(reminder: Reminder, options: { includeDate?: boolean } = {}) {
  if (reminder.completed) {
    return reminder.completed_at ? `Completed ${formatShortDate(reminder.completed_at)}` : 'Completed'
  }

  return formatDueDateLabel(reminder.due_date, options)
}

export function formatDueDateLabel(value: string, options: { includeDate?: boolean } = {}) {
  const includeDate = options.includeDate ?? true
  const daysUntilDue = getDaysUntilDate(value)
  const dateLabel = formatShortDate(value)

  if (daysUntilDue < 0) {
    return formatOverdueLabel(value)
  }

  if (daysUntilDue === 0) {
    return includeDate ? `Due today \u2022 ${dateLabel}` : 'Due today'
  }

  if (daysUntilDue === 1) {
    return includeDate ? `Due tomorrow \u2022 ${dateLabel}` : 'Due tomorrow'
  }

  if (daysUntilDue <= 13) {
    return includeDate
      ? `Due in ${formatCount(daysUntilDue, 'day')} \u2022 ${dateLabel}`
      : `Due in ${formatCount(daysUntilDue, 'day')}`
  }

  if (daysUntilDue < 60 && daysUntilDue % 7 === 0) {
    const weeks = daysUntilDue / 7
    return includeDate
      ? `Due in ${formatCount(weeks, 'week')} \u2022 ${dateLabel}`
      : `Due in ${formatCount(weeks, 'week')}`
  }

  return `Due ${formatLongDate(value)}`
}

export function formatRelativeDatePhrase(value: string, options: { monthApproximation?: boolean } = {}) {
  const daysUntil = getDaysUntilDate(value)

  if (daysUntil === 0) {
    return 'today'
  }

  if (daysUntil === 1) {
    return 'tomorrow'
  }

  if (daysUntil === -1) {
    return 'yesterday'
  }

  if (daysUntil < 0) {
    return `${formatCount(Math.abs(daysUntil), 'day')} ago`
  }

  if (options.monthApproximation && daysUntil >= 45) {
    const months = Math.max(1, Math.round(daysUntil / 30))
    return `in ${formatCount(months, 'month')}`
  }

  return `in ${formatCount(daysUntil, 'day')}`
}

export function formatRepeatLabel(repeat: Reminder['repeat']) {
  if (repeat === 'None') {
    return null
  }

  return `Repeats ${repeat.toLowerCase()}`
}

export function formatCompletionNotice(before: Reminder | undefined, after: Reminder | undefined) {
  if (!after || after.completed) {
    return 'Completed.'
  }

  const nextDueDate = after.due_date ? formatLongDate(after.due_date) : null
  if (!nextDueDate) {
    return 'Completed.'
  }

  const reminderType = before?.reminder_type ?? after.reminder_type

  if (reminderType === 'birthday') {
    return `Completed. Next birthday reminder set for ${nextDueDate}.`
  }

  if (reminderType === 'renewal') {
    return `Completed. Renewal reminder advanced to ${nextDueDate}.`
  }

  if (reminderType === 'maintenance') {
    return `Completed. Next due ${nextDueDate}.`
  }

  return `Completed. Next due ${nextDueDate}.`
}

export function formatOverdueLabel(value: string) {
  const overdueDays = Math.max(Math.abs(getDaysUntilDate(value)), 1)
  return `Overdue by ${formatCount(overdueDays, 'day')}`
}

export function getDaysUntilDate(value: string, today = new Date()) {
  const targetDate = parseDateOnly(value)
  const currentDay = startOfDay(today)

  return Math.ceil((targetDate.getTime() - currentDay.getTime()) / dayMs)
}

export function formatCount(value: number, noun: string) {
  return `${value} ${noun}${value === 1 ? '' : 's'}`
}

export function formatShortDate(value: string) {
  const date = parseDateOnly(value)

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(date)
}

export function formatMonthDay(value: string) {
  return formatShortDate(value)
}

export function formatLongDate(value: string) {
  const date = parseDateOnly(value)

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

export function parseDateOnly(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}
