import type { Reminder } from '../types/reminder'
import { getRenewalCardSmartLabel } from './renewalUx'

export function getSmartReminderLabel(reminder: Reminder) {
  if (reminder.reminder_type === 'birthday') {
    return reminder.computed_label ?? reminder.birthday_age_label
  }

  if (reminder.reminder_type === 'renewal') {
    return getRenewalCardSmartLabel(reminder)
  }

  return null
}

