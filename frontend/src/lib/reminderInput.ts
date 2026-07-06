import { buildReminderInputWithDefaultTiming } from './reminderSchedule'
import type { BirthdayDetailsInput, MaintenanceDetailsInput, ReminderInput, RenewalDetailsInput } from '../types/reminder'
import {
  getBackendRenewalKind,
  getRenewalDefaults,
  getRenewalDisplayKind,
  getRenewalValidationMessage,
  getRelevantRenewalDate,
  withRenewalDisplayKind,
} from './renewalUx'
import {
  getMaintenanceDefaults,
  getMaintenanceDueDate,
  getMaintenanceRepeat,
  getMaintenanceValidationMessage,
} from './maintenanceUx'

const today = new Date().toISOString().slice(0, 10)

export function emptyBirthdayDetails(): BirthdayDetailsInput {
  return {
    person_name: '',
    birth_month: null,
    birth_day: null,
    birth_year: null,
    age_turning_next_birthday: null,
    inferred_birth_year: false,
    relationship: null,
  }
}

export function emptyRenewalDetails(): RenewalDetailsInput {
  return {
    item_name: '',
    renewal_kind: 'renewal',
    owner_name: null,
    provider: null,
    renewal_date: null,
    expiration_date: null,
    renewal_window_days: null,
    review_lead_days: null,
    frequency: null,
  }
}

export function emptyMaintenanceDetails(): MaintenanceDetailsInput {
  const defaults = getMaintenanceDefaults('home')

  return {
    item_name: '',
    maintenance_area: 'home',
    last_completed_date: null,
    interval_value: defaults.interval_value,
    interval_unit: defaults.interval_unit,
    next_due_date: null,
    instructions: null,
  }
}

export function createBirthdayReminderInput(overrides: Partial<ReminderInput> = {}): ReminderInput {
  const birthdayDetails = {
    ...emptyBirthdayDetails(),
    ...(overrides.birthday_details ?? {}),
  }

  return buildReminderInputWithDefaultTiming({
    title: 'Birthday reminder',
    category: 'Family',
    due_date: today,
    repeat: 'Yearly',
    priority: 'Medium',
    notes: null,
    reminder_lead_value: 1,
    reminder_lead_unit: 'weeks',
    reminder_time: '09:00',
    reminder_type: 'birthday',
    ...overrides,
    birthday_details: birthdayDetails,
  })
}

export function createRenewalReminderInput(overrides: Partial<ReminderInput> = {}): ReminderInput {
  const mergedRenewalDetails = {
    ...emptyRenewalDetails(),
    ...(overrides.renewal_details ?? {}),
  }
  const displayKind = getRenewalDisplayKind(mergedRenewalDetails)
  const renewalDetails = withRenewalDisplayKind(mergedRenewalDetails, displayKind)
  const defaults = getRenewalDefaults(displayKind)
  const dueDate = getRelevantRenewalDate(renewalDetails, overrides.due_date ?? '')

  return buildReminderInputWithDefaultTiming({
    title: 'Renewal reminder',
    category: defaults.category ?? 'Other',
    repeat: defaults.repeat,
    priority: defaults.priority,
    notes: null,
    reminder_lead_value: defaults.reminder_lead_value,
    reminder_lead_unit: defaults.reminder_lead_unit,
    reminder_time: defaults.reminder_time,
    reminder_type: 'renewal',
    ...overrides,
    due_date: dueDate,
    renewal_details: renewalDetails,
  })
}

export function createMaintenanceReminderInput(overrides: Partial<ReminderInput> = {}): ReminderInput {
  const mergedDetails = {
    ...emptyMaintenanceDetails(),
    ...(overrides.maintenance_details ?? {}),
  }
  const defaults = getMaintenanceDefaults(mergedDetails.maintenance_area)
  const dueDate = getMaintenanceDueDate(mergedDetails, overrides.due_date ?? '')

  return buildReminderInputWithDefaultTiming({
    title: 'Maintenance reminder',
    category: defaults.category,
    repeat: getMaintenanceRepeat(mergedDetails),
    priority: defaults.priority,
    notes: null,
    reminder_lead_value: defaults.reminder_lead_value,
    reminder_lead_unit: defaults.reminder_lead_unit,
    reminder_time: defaults.reminder_time,
    reminder_type: 'maintenance',
    ...overrides,
    due_date: dueDate,
    maintenance_details: mergedDetails,
  })
}

export function isReminderReady(form: ReminderInput) {
  if (!form.title.trim()) {
    return false
  }

  if (form.reminder_type === 'birthday') {
    const details = form.birthday_details
    return Boolean(details?.person_name.trim() && details.birth_month && details.birth_day)
  }

  if (form.reminder_type === 'renewal') {
    return getRenewalValidationMessage(form) === null
  }

  if (form.reminder_type === 'maintenance') {
    return getMaintenanceValidationMessage(form) === null
  }

  return true
}

export function buildReminderSubmitInput(form: ReminderInput): ReminderInput {
  const baseInput = buildReminderInputWithDefaultTiming({
    ...form,
    title: form.title.trim(),
    notes: form.notes?.trim() || null,
  })

  if (baseInput.reminder_type === 'birthday') {
    return buildBirthdaySubmitInput(baseInput)
  }

  if (baseInput.reminder_type === 'renewal') {
    return buildRenewalSubmitInput(baseInput)
  }

  if (baseInput.reminder_type === 'maintenance') {
    return buildMaintenanceSubmitInput(baseInput)
  }

  return {
    ...baseInput,
    birthday_details: null,
    renewal_details: null,
    maintenance_details: null,
  }
}

function buildBirthdaySubmitInput(baseInput: ReminderInput): ReminderInput {
  const details = baseInput.birthday_details ?? emptyBirthdayDetails()
  const isTurningAgeSource = details.inferred_birth_year
  const birthYear = isTurningAgeSource ? null : toOptionalNumber(details.birth_year)
  const ageTurning = toOptionalNumber(details.age_turning_next_birthday)

  return {
    ...baseInput,
    repeat: 'Yearly',
    priority: baseInput.priority || 'Medium',
    birthday_details: {
      person_name: details.person_name.trim(),
      birth_month: details.birth_month,
      birth_day: details.birth_day,
      birth_year: birthYear,
      age_turning_next_birthday:
        birthYear === null ? ageTurning : null,
      inferred_birth_year: birthYear === null && ageTurning !== null ? isTurningAgeSource : false,
      relationship: details.relationship?.trim() || null,
    },
    renewal_details: null,
    maintenance_details: null,
  }
}

function buildRenewalSubmitInput(baseInput: ReminderInput): ReminderInput {
  const details = baseInput.renewal_details ?? emptyRenewalDetails()
  const displayKind = getRenewalDisplayKind(details, {
    title: baseInput.title,
    category: baseInput.category,
  })
  const renewalKind = getBackendRenewalKind(displayKind)
  const detailsWithDisplayKind = withRenewalDisplayKind(details, displayKind)
  const relevantDate = getRelevantRenewalDate({ ...detailsWithDisplayKind, renewal_kind: renewalKind }, baseInput.due_date)
  const renewalDate = renewalKind === 'expiration'
    ? toOptionalDate(details.renewal_date)
    : toOptionalDate(details.renewal_date ?? relevantDate)
  const expirationDate = renewalKind === 'expiration'
    ? toOptionalDate(details.expiration_date ?? relevantDate)
    : toOptionalDate(details.expiration_date)

  return {
    ...baseInput,
    due_date: relevantDate,
    repeat: baseInput.repeat || 'Yearly',
    priority: baseInput.priority || 'Medium',
    birthday_details: null,
    renewal_details: {
      item_name: details.item_name.trim(),
      renewal_kind: renewalKind,
      owner_name: details.owner_name?.trim() || null,
      provider: details.provider?.trim() || null,
      renewal_date: renewalDate,
      expiration_date: expirationDate,
      renewal_window_days: toOptionalNumber(details.renewal_window_days),
      review_lead_days: toOptionalNumber(details.review_lead_days),
      frequency: detailsWithDisplayKind.frequency,
    },
    maintenance_details: null,
  }
}

function buildMaintenanceSubmitInput(baseInput: ReminderInput): ReminderInput {
  const details = baseInput.maintenance_details ?? emptyMaintenanceDetails()
  const nextDueDate = getMaintenanceDueDate(details, baseInput.due_date)
  const intervalValue = toOptionalNumber(details.interval_value)
  const intervalUnit = details.interval_unit || null

  return {
    ...baseInput,
    due_date: nextDueDate,
    repeat: getMaintenanceRepeat({ ...details, interval_value: intervalValue, interval_unit: intervalUnit }),
    priority: baseInput.priority || 'Medium',
    birthday_details: null,
    renewal_details: null,
    maintenance_details: {
      item_name: details.item_name.trim(),
      maintenance_area: details.maintenance_area,
      last_completed_date: toOptionalDate(details.last_completed_date),
      interval_value: intervalValue,
      interval_unit: intervalUnit,
      next_due_date: toOptionalDate(nextDueDate),
      instructions: details.instructions?.trim() || null,
    },
  }
}

function toOptionalDate(value: string | null | undefined) {
  return value?.trim() || null
}

function toOptionalNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numericValue = Number(value)
  return Number.isFinite(numericValue) ? numericValue : null
}
