import { buildReminderInputWithDefaultTiming } from './reminderSchedule'
import type { BirthdayDetailsInput, ReminderInput } from '../types/reminder'

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

export function createBirthdayReminderInput(overrides: Partial<ReminderInput> = {}): ReminderInput {
  const birthdayDetails = {
    ...emptyBirthdayDetails(),
    ...(overrides.birthday_details ?? {}),
  }

  return buildReminderInputWithDefaultTiming({
    title: 'Birthday reminder',
    category: 'Family',
    due_date: new Date().toISOString().slice(0, 10),
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

export function isReminderReady(form: ReminderInput) {
  if (!form.title.trim()) {
    return false
  }

  if (form.reminder_type !== 'birthday') {
    return true
  }

  const details = form.birthday_details
  return Boolean(details?.person_name.trim() && details.birth_month && details.birth_day)
}

export function buildReminderSubmitInput(form: ReminderInput): ReminderInput {
  const baseInput = buildReminderInputWithDefaultTiming({
    ...form,
    title: form.title.trim(),
    notes: form.notes?.trim() || null,
  })

  if (baseInput.reminder_type !== 'birthday') {
    return {
      ...baseInput,
      birthday_details: null,
    }
  }

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
  }
}

function toOptionalNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numericValue = Number(value)
  return Number.isFinite(numericValue) ? numericValue : null
}
