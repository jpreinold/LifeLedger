import type {
  MaintenanceArea,
  MaintenanceDetails,
  MaintenanceDetailsInput,
  MaintenanceIntervalUnit,
  PriorityOption,
  Reminder,
  ReminderCategory,
  ReminderInput,
  ReminderLeadUnit,
  RepeatOption,
} from '../types/reminder'
import { formatReminderTiming } from './reminderSchedule'

interface MaintenanceAreaOption {
  area: MaintenanceArea
  label: string
}

interface MaintenanceDefaults {
  category: ReminderCategory
  interval_value: number
  interval_unit: MaintenanceIntervalUnit
  repeat: RepeatOption
  priority: PriorityOption
  reminder_lead_value: number
  reminder_lead_unit: ReminderLeadUnit
  reminder_time: string
}

interface MaintenancePreview {
  primary: string
  reminder: string | null
  card: string | null
}

type MaintenanceDetailsLike = MaintenanceDetails | MaintenanceDetailsInput

export const maintenanceAreaOptions: MaintenanceAreaOption[] = [
  { area: 'home', label: 'Home' },
  { area: 'vehicle', label: 'Vehicle' },
  { area: 'pet', label: 'Pet' },
  { area: 'health', label: 'Health' },
  { area: 'other', label: 'Other' },
]

const areaDefaults: Record<MaintenanceArea, MaintenanceDefaults> = {
  home: {
    category: 'Home',
    interval_value: 3,
    interval_unit: 'months',
    repeat: 'Quarterly',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'weeks',
    reminder_time: '09:00',
  },
  vehicle: {
    category: 'Car',
    interval_value: 6,
    interval_unit: 'months',
    repeat: 'None',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'weeks',
    reminder_time: '09:00',
  },
  pet: {
    category: 'Family',
    interval_value: 1,
    interval_unit: 'months',
    repeat: 'Monthly',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'weeks',
    reminder_time: '09:00',
  },
  health: {
    category: 'Health',
    interval_value: 6,
    interval_unit: 'months',
    repeat: 'None',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'weeks',
    reminder_time: '09:00',
  },
  other: {
    category: 'Other',
    interval_value: 1,
    interval_unit: 'months',
    repeat: 'Monthly',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'weeks',
    reminder_time: '09:00',
  },
}

export function getMaintenanceDefaults(area: MaintenanceArea): MaintenanceDefaults {
  return areaDefaults[area]
}

export function getMaintenanceAreaLabel(area: MaintenanceArea | null | undefined) {
  return maintenanceAreaOptions.find((option) => option.area === area)?.label ?? 'Other'
}

export function getMaintenanceTitle(itemName: string) {
  const trimmedName = itemName.trim()
  return trimmedName || 'Maintenance reminder'
}

export function isAutoMaintenanceTitle(currentTitle: string, previousItemName: string) {
  const trimmedTitle = currentTitle.trim()
  const previousName = previousItemName.trim()

  if (!trimmedTitle || trimmedTitle === 'Maintenance reminder') {
    return true
  }

  if (!previousName) {
    return false
  }

  return trimmedTitle === previousName || trimmedTitle === `${previousName} reminder`
}

export function getMaintenanceRepeat(details: MaintenanceDetailsLike): RepeatOption {
  if (details.interval_value === 1 && details.interval_unit === 'weeks') {
    return 'Weekly'
  }

  if (details.interval_value === 1 && details.interval_unit === 'months') {
    return 'Monthly'
  }

  if (details.interval_value === 3 && details.interval_unit === 'months') {
    return 'Quarterly'
  }

  if (
    (details.interval_value === 1 && details.interval_unit === 'years') ||
    (details.interval_value === 12 && details.interval_unit === 'months')
  ) {
    return 'Yearly'
  }

  return 'None'
}

export function getMaintenanceDueDate(details: MaintenanceDetailsLike, fallbackDate = '') {
  if (details.next_due_date) {
    return details.next_due_date
  }

  if (details.last_completed_date && details.interval_value && details.interval_unit) {
    return addMaintenanceInterval(details.last_completed_date, details.interval_value, details.interval_unit)
  }

  return fallbackDate
}

export function getCalculatedMaintenanceDueDate(details: MaintenanceDetailsLike) {
  if (details.last_completed_date && details.interval_value && details.interval_unit) {
    return addMaintenanceInterval(details.last_completed_date, details.interval_value, details.interval_unit)
  }

  return ''
}

export function getMaintenancePreview(input: ReminderInput): MaintenancePreview {
  const details = input.maintenance_details
  if (!details) {
    return {
      primary: 'Enter an item and schedule to preview this maintenance reminder.',
      reminder: null,
      card: null,
    }
  }

  const itemName = details.item_name.trim()
  const dueDate = getMaintenanceDueDate(details, input.due_date)
  const schedule = getMaintenanceSchedulePhrase(details)

  if (!itemName || (!schedule && !dueDate)) {
    return {
      primary: 'Enter an item and schedule to preview this maintenance reminder.',
      reminder: null,
      card: null,
    }
  }

  const primary = schedule && dueDate
    ? `${itemName} is due ${schedule}. Next due ${formatFullDate(dueDate)}.`
    : dueDate
      ? `${itemName} is next due ${formatFullDate(dueDate)}.`
      : `${itemName} uses a maintenance schedule.`
  const title = input.title.trim() || getMaintenanceTitle(itemName)
  const cardLabel = getMaintenanceCardLabelFromParts(details, dueDate)

  return {
    primary,
    reminder: `LifeLedger will remind you ${formatReminderTiming(input)}.`,
    card: cardLabel ? `Card: ${title} - ${cardLabel}` : `Card: ${title}`,
  }
}

export function getMaintenanceValidationMessage(input: ReminderInput) {
  if (input.reminder_type !== 'maintenance') {
    return null
  }

  const details = input.maintenance_details
  if (!details?.item_name.trim()) {
    return 'Enter an item name.'
  }

  if (!details.interval_value || !details.interval_unit) {
    return 'Choose the maintenance interval.'
  }

  if (!getMaintenanceDueDate(details, input.due_date)) {
    return 'Choose the next due date.'
  }

  if (containsSensitiveText([input.title, input.notes, details.item_name, details.instructions])) {
    return 'This field should not include sensitive numbers or passwords.'
  }

  return null
}

export function getMaintenanceCardSmartLabel(reminder: Reminder) {
  const details = reminder.maintenance_details
  if (!details) {
    return reminder.computed_label ?? reminder.maintenance_status_label
  }

  return getMaintenanceCardLabelFromParts(details, getMaintenanceDueDate(details, reminder.due_date))
    ?? reminder.computed_label
    ?? reminder.maintenance_status_label
}

export function getMaintenanceAreaCategory(area: MaintenanceArea): ReminderCategory {
  return getMaintenanceDefaults(area).category
}

export function addMaintenanceInterval(value: string, amount: number, unit: MaintenanceIntervalUnit) {
  const date = parseDateOnly(value)

  if (unit === 'days') {
    date.setDate(date.getDate() + amount)
    return formatDateOnly(date)
  }

  if (unit === 'weeks') {
    date.setDate(date.getDate() + amount * 7)
    return formatDateOnly(date)
  }

  if (unit === 'months') {
    return formatDateOnly(addMonths(date, amount))
  }

  return formatDateOnly(addMonths(date, amount * 12))
}

function getMaintenanceCardLabelFromParts(details: MaintenanceDetailsLike, dueDate: string | null | undefined) {
  const parts = [getMaintenanceAreaLabel(details.maintenance_area)]
  const cadence = getMaintenanceCadenceLabel(details)
  const dueLabel = dueDate ? getMaintenanceDueLabel(dueDate) : null

  if (cadence) {
    parts.push(cadence)
  }

  if (dueLabel) {
    parts.push(dueLabel)
  }

  return parts.length > 1 ? parts.join(' \u2022 ') : null
}

function getMaintenanceSchedulePhrase(details: MaintenanceDetailsLike) {
  if (!details.interval_value || !details.interval_unit) {
    return null
  }

  if (details.interval_value === 1) {
    return `every ${details.interval_unit.slice(0, -1)}`
  }

  return `every ${details.interval_value} ${details.interval_unit}`
}

function getMaintenanceCadenceLabel(details: MaintenanceDetailsLike) {
  if (!details.interval_value || !details.interval_unit) {
    return null
  }

  if (details.interval_value === 1 && details.interval_unit === 'days') {
    return 'Daily'
  }

  if (details.interval_value === 1 && details.interval_unit === 'weeks') {
    return 'Weekly'
  }

  if (details.interval_value === 1 && details.interval_unit === 'months') {
    return 'Monthly'
  }

  if (details.interval_value === 1 && details.interval_unit === 'years') {
    return 'Yearly'
  }

  return `Every ${details.interval_value} ${details.interval_unit}`
}

function getMaintenanceDueLabel(value: string) {
  const targetDate = parseDateOnly(value)
  const today = startOfDay(new Date())
  const daysUntil = Math.ceil((targetDate.getTime() - today.getTime()) / 86_400_000)

  if (daysUntil === 0) {
    return 'Due today'
  }

  if (daysUntil === 1) {
    return 'Due tomorrow'
  }

  if (daysUntil < 0) {
    const daysPast = Math.abs(daysUntil)
    return `Overdue by ${daysPast} ${daysPast === 1 ? 'day' : 'days'}`
  }

  if (daysUntil <= 13) {
    return `Due in ${daysUntil} ${daysUntil === 1 ? 'day' : 'days'}`
  }

  if (daysUntil < 60) {
    const weeks = Math.max(2, Math.round(daysUntil / 7))
    return `Due in ${weeks} ${weeks === 1 ? 'week' : 'weeks'}`
  }

  return `Due ${formatMonthDay(value)}`
}

function containsSensitiveText(values: Array<string | null | undefined>) {
  const text = values.filter(Boolean).join(' ')

  return (
    /\b(password|passcode|account number|policy number|card number|credit card|ssn|social security|passport number|license number|vin)\b/i.test(text) ||
    /\b\d{3}-\d{2}-\d{4}\b/.test(text) ||
    /\b(?:\d[ -]?){13,19}\b/.test(text) ||
    /\d{9,}/.test(text)
  )
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

function parseDateOnly(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function formatDateOnly(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatFullDate(value: string) {
  const date = parseDateOnly(value)

  return new Intl.DateTimeFormat(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

function formatMonthDay(value: string) {
  const date = parseDateOnly(value)

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(date)
}