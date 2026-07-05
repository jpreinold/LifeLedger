import type { Reminder } from '../types/reminder'

export function getSmartReminderLabel(reminder: Reminder) {
  if (reminder.reminder_type === 'birthday') {
    return reminder.computed_label ?? reminder.birthday_age_label
  }

  if (reminder.reminder_type === 'renewal') {
    return reminder.computed_label ?? reminder.renewal_status_label ?? reminder.renewal_window_label
  }

  return null
}
