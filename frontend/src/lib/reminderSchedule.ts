import type { Reminder, ReminderAlert, ReminderAlertReason, ReminderInput, ReminderLeadUnit } from '../types/reminder'

export const DEFAULT_REMINDER_LEAD_VALUE = 1
export const DEFAULT_REMINDER_LEAD_UNIT: ReminderLeadUnit = 'days'
export const DEFAULT_REMINDER_TIME = '09:00'

export type ReminderLeadPreset = 'same-day' | 'one-day' | 'one-week' | 'one-month' | 'custom'
export type AttentionReason = ReminderAlertReason

export interface ReminderTimingFields {
  reminder_lead_value: number | null
  reminder_lead_unit: ReminderLeadUnit | null
  reminder_time: string | null
}

export interface AttentionReminder {
  reminder: Reminder
  reason: AttentionReason
  rank: number
  reminderDate: string | null
}

interface ReminderLeadOption {
  id: Exclude<ReminderLeadPreset, 'custom'>
  label: string
  value: number
  unit: ReminderLeadUnit
}

const attentionRanks: Record<AttentionReason, number> = {
  Overdue: 0,
  'Due today': 1,
  'Reminder window': 2,
}

export const reminderLeadOptions: ReminderLeadOption[] = [
  { id: 'same-day', label: 'Same day', value: 0, unit: 'days' },
  { id: 'one-day', label: '1 day before', value: 1, unit: 'days' },
  { id: 'one-week', label: '1 week before', value: 1, unit: 'weeks' },
  { id: 'one-month', label: '1 month before', value: 1, unit: 'months' },
]

export function defaultReminderTiming(): ReminderTimingFields {
  return {
    reminder_lead_value: DEFAULT_REMINDER_LEAD_VALUE,
    reminder_lead_unit: DEFAULT_REMINDER_LEAD_UNIT,
    reminder_time: DEFAULT_REMINDER_TIME,
  }
}

export function withDefaultReminderTiming(input: Partial<ReminderTimingFields>): ReminderTimingFields {
  return {
    ...input,
    reminder_lead_value: input.reminder_lead_value ?? DEFAULT_REMINDER_LEAD_VALUE,
    reminder_lead_unit: input.reminder_lead_unit ?? DEFAULT_REMINDER_LEAD_UNIT,
    reminder_time: input.reminder_time ?? DEFAULT_REMINDER_TIME,
  }
}

export function getReminderLeadPreset(input: ReminderTimingFields): ReminderLeadPreset {
  const timing = withDefaultReminderTiming(input)
  const matchingOption = reminderLeadOptions.find(
    (option) => option.value === timing.reminder_lead_value && option.unit === timing.reminder_lead_unit,
  )

  return matchingOption?.id ?? 'custom'
}

export function getPresetTiming(preset: ReminderLeadPreset, current: ReminderTimingFields): ReminderTimingFields {
  const option = reminderLeadOptions.find((item) => item.id === preset)

  if (!option) {
    return withDefaultReminderTiming(current)
  }

  return {
    reminder_lead_value: option.value,
    reminder_lead_unit: option.unit,
    reminder_time: current.reminder_time ?? DEFAULT_REMINDER_TIME,
  }
}

export function buildReminderInputWithDefaultTiming(
  input: Omit<ReminderInput, keyof ReminderTimingFields | 'reminder_type' | 'birthday_details' | 'renewal_details' | 'maintenance_details'> &
    Partial<ReminderTimingFields> &
    Partial<Pick<ReminderInput, 'reminder_type' | 'birthday_details' | 'renewal_details' | 'maintenance_details'>>,
): ReminderInput {
  const reminderType = input.reminder_type ?? 'generic'

  return {
    ...input,
    reminder_type: reminderType,
    birthday_details: reminderType === 'birthday' ? input.birthday_details ?? null : null,
    renewal_details: reminderType === 'renewal' ? input.renewal_details ?? null : null,
    maintenance_details: reminderType === 'maintenance' ? input.maintenance_details ?? null : null,
    ...withDefaultReminderTiming({
      reminder_lead_value: input.reminder_lead_value ?? null,
      reminder_lead_unit: input.reminder_lead_unit ?? null,
      reminder_time: input.reminder_time ?? null,
    }),
  }
}

export function formatReminderTiming(input: ReminderTimingFields) {
  const timing = withDefaultReminderTiming(input)
  const leadValue = timing.reminder_lead_value ?? DEFAULT_REMINDER_LEAD_VALUE
  const leadUnit = timing.reminder_lead_unit ?? DEFAULT_REMINDER_LEAD_UNIT
  const time = formatReminderTime(timing.reminder_time ?? DEFAULT_REMINDER_TIME)

  if (leadValue === 0) {
    return `Same day at ${time}`
  }

  const unitLabel = leadValue === 1 ? leadUnit.slice(0, -1) : leadUnit
  return `${leadValue} ${unitLabel} before at ${time}`
}

export function toAttentionReminder(alert: ReminderAlert): AttentionReminder {
  return {
    reminder: alert,
    reason: alert.alert_reason,
    rank: attentionRanks[alert.alert_reason],
    reminderDate: alert.alert_reminder_start_date,
  }
}

export function getNeedsAttention(reminders: Reminder[], today = new Date()): AttentionReminder[] {
  const currentTime = today
  const currentDay = startOfDay(today)

  return reminders
    .flatMap((reminder): AttentionReminder[] => {
      if (reminder.completed || isAlertMuted(reminder, currentTime)) {
        return []
      }

      const dueDate = parseDateOnly(reminder.due_date)

      if (reminder.status === 'Overdue' || dueDate < currentDay) {
        return [{ reminder, reason: 'Overdue', rank: attentionRanks.Overdue, reminderDate: null }]
      }

      if (reminder.status === 'Due today' || sameDate(dueDate, currentDay)) {
        return [{ reminder, reason: 'Due today', rank: attentionRanks['Due today'], reminderDate: formatDateOnly(currentDay) }]
      }

      if (hasReminderTiming(reminder)) {
        const reminderDate = getReminderStartDate(reminder)
        if (reminderDate <= currentDay && dueDate >= currentDay) {
          return [{ reminder, reason: 'Reminder window', rank: attentionRanks['Reminder window'], reminderDate: formatDateOnly(reminderDate) }]
        }
      }

      return []
    })
    .sort((left, right) => {
      if (left.rank !== right.rank) {
        return left.rank - right.rank
      }

      const dueDifference =
        parseDateOnly(left.reminder.due_date).getTime() - parseDateOnly(right.reminder.due_date).getTime()
      if (dueDifference !== 0) {
        return dueDifference
      }

      return left.reminder.title.localeCompare(right.reminder.title)
    })
}

export function getReminderStartDate(input: ReminderTimingFields & { due_date: string }) {
  const timing = withDefaultReminderTiming(input)
  const dueDate = parseDateOnly(input.due_date)

  if (timing.reminder_lead_unit === 'weeks') {
    return addDays(dueDate, -7 * (timing.reminder_lead_value ?? DEFAULT_REMINDER_LEAD_VALUE))
  }

  if (timing.reminder_lead_unit === 'months') {
    return addMonths(dueDate, -(timing.reminder_lead_value ?? DEFAULT_REMINDER_LEAD_VALUE))
  }

  return addDays(dueDate, -(timing.reminder_lead_value ?? DEFAULT_REMINDER_LEAD_VALUE))
}

function hasReminderTiming(input: ReminderTimingFields) {
  return input.reminder_lead_value !== null && input.reminder_lead_unit !== null
}

function isAlertMuted(reminder: Reminder, now: Date) {
  return isFutureDateTime(reminder.alert_dismissed_until, now) || isFutureDateTime(reminder.alert_snoozed_until, now)
}

function isFutureDateTime(value: string | null, now: Date) {
  if (!value) {
    return false
  }

  const target = new Date(value)
  return !Number.isNaN(target.getTime()) && target.getTime() > now.getTime()
}

function formatReminderTime(value: string) {
  const [hour = '9', minute = '00'] = value.split(':')
  const date = new Date(2000, 0, 1, Number(hour), Number(minute))

  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

function parseDateOnly(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function addDays(value: Date, days: number) {
  const next = new Date(value)
  next.setDate(next.getDate() + days)
  return startOfDay(next)
}

function addMonths(value: Date, months: number) {
  const targetMonth = value.getMonth() + months
  const firstOfTargetMonth = new Date(value.getFullYear(), targetMonth, 1)
  const lastDayOfTargetMonth = new Date(
    firstOfTargetMonth.getFullYear(),
    firstOfTargetMonth.getMonth() + 1,
    0,
  ).getDate()

  return new Date(
    firstOfTargetMonth.getFullYear(),
    firstOfTargetMonth.getMonth(),
    Math.min(value.getDate(), lastDayOfTargetMonth),
  )
}

function sameDate(left: Date, right: Date) {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  )
}

function formatDateOnly(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
