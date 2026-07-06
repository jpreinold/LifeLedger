import type { Reminder } from '../types/reminder'
import { getMaintenanceCardSmartLabel } from './maintenanceUx'
import { getRenewalCardSmartLabel } from './renewalUx'

export function getSmartReminderLabel(reminder: Reminder) {
  if (reminder.reminder_type === 'birthday') {
    return cleanSmartLabel(reminder.computed_label ?? reminder.birthday_age_label)
  }

  if (reminder.reminder_type === 'renewal') {
    return cleanSmartLabel(getRenewalCardSmartLabel(reminder))
  }

  if (reminder.reminder_type === 'maintenance') {
    return cleanSmartLabel(getMaintenanceCardSmartLabel(reminder))
  }

  return null
}

function cleanSmartLabel(value: string | null | undefined) {
  const label = value?.trim()
  if (!label || /(_label|next_due_date|reminder_type|computed label|interval months=)/i.test(label)) {
    return null
  }

  return label
}
