import { formatReminderDueLabel } from './reminderDisplay'
import type { AttentionReminder } from './reminderSchedule'
import { getSmartReminderLabel } from './smartReminderLabels'

export function getAttentionTone(item: AttentionReminder) {
  if (item.reason === 'Overdue') {
    return 'danger'
  }

  if (item.reason === 'Due today') {
    return 'warning'
  }

  return 'primary'
}

export function getAttentionLabel(item: AttentionReminder, options: { windowLabel?: string } = {}) {
  if (item.reason === 'Reminder window') {
    return options.windowLabel ?? 'Reminder window'
  }

  return item.reason
}

export function getAttentionDetail(item: AttentionReminder, options: { windowSeparator?: string } = {}) {
  const smartLabel = getSmartReminderLabel(item.reminder)
  if (smartLabel) {
    return smartLabel
  }

  if (item.reason === 'Reminder window') {
    return `Reminder started${options.windowSeparator ?? ' • '}${formatReminderDueLabel(item.reminder, { includeDate: false })}`
  }

  return formatReminderDueLabel(item.reminder, { includeDate: false })
}
