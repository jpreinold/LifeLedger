import { useEffect, useRef, useState } from 'react'

import type { DynamicFieldValue } from '../types/record'

type BirthdayAgeSource = 'birth_year' | 'turning_age' | null

interface BirthdayDraft {
  month: string
  day: string
  birthYear: string
  turningAge: string
  ageSource: BirthdayAgeSource
}

const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export function PersonBirthdayInput({
  inferredBirthYear = null,
  label = 'Birthday',
  onChange,
  onInferredBirthYearChange,
  onValidityChange,
  subjectName,
  value,
}: {
  inferredBirthYear?: number | null
  label?: string
  onChange: (value: DynamicFieldValue) => void
  onInferredBirthYearChange?: (value: number | null) => void
  onValidityChange?: (isValid: boolean) => void
  subjectName?: string
  value: DynamicFieldValue
}) {
  const [draft, setDraft] = useState<BirthdayDraft>(() => parseBirthday(value, inferredBirthYear))
  const draftRef = useRef(draft)

  useEffect(() => {
    const parsed = parseBirthday(value, inferredBirthYear)
    setDraft((current) => {
      if (sameDraft(current, parsed)) return current
      draftRef.current = parsed
      return parsed
    })
  }, [inferredBirthYear, value])

  function update(part: 'month' | 'day' | 'birthYear' | 'turningAge', nextValue: string) {
    const current = draftRef.current
    let ageSource = current.ageSource
    if (part === 'birthYear') ageSource = nextValue ? 'birth_year' : null
    if (part === 'turningAge') ageSource = nextValue ? 'turning_age' : null

    const next = calculateDraft({ ...current, [part]: nextValue, ageSource })
    draftRef.current = next
    setDraft(next)
    onValidityChange?.(isBirthdayDraftValid(next))

    const stored = toStoredBirthday(next)
    if (stored === undefined) return
    onChange(stored)
    onInferredBirthYearChange?.(
      stored !== null && next.ageSource === 'turning_age' && next.birthYear
        ? Number(next.birthYear)
        : null,
    )
  }

  const invalidDay = Boolean(draft.month && draft.day && !isValidMonthDay(Number(draft.month), Number(draft.day)))
  const invalidBirthYear = Boolean(
    draft.ageSource === 'birth_year'
    && draft.birthYear
    && (draft.birthYear.length !== 4 || !isValidBirthYear(Number(draft.birthYear))),
  )
  const invalidTurningAge = Boolean(draft.turningAge && !isValidTurningAge(Number(draft.turningAge)))
  const preview = getBirthdayPreview(draft, subjectName)

  return (
    <div className="person-birthday-input" aria-label={label}>
      <span className="person-birthday-label">{label}</span>
      <div className="person-birthday-date-fields">
        <label>
          <span>Month</span>
          <select value={draft.month} onChange={(event) => update('month', event.target.value)}>
            <option value="">Choose</option>
            {months.map((month, index) => <option value={String(index + 1)} key={month}>{month}</option>)}
          </select>
        </label>
        <label>
          <span>Day</span>
          <input
            inputMode="numeric"
            max={31}
            min={1}
            type="number"
            value={draft.day}
            onChange={(event) => update('day', event.target.value)}
          />
        </label>
      </div>
      <div className="person-birthday-age-fields">
        <label className="calculated-field-label">
          <span className="field-label-row">
            <span>Birth year</span>
            {draft.ageSource === 'turning_age' && draft.birthYear ? <small className="calculated-badge">Calculated</small> : null}
          </span>
          <input
            aria-label="Birth Year"
            inputMode="numeric"
            max={new Date().getFullYear()}
            min={new Date().getFullYear() - 150}
            placeholder="1999"
            type="text"
            value={draft.birthYear}
            onChange={(event) => update('birthYear', event.target.value.replace(/\D/g, '').slice(0, 4))}
          />
        </label>
        <label className="calculated-field-label">
          <span className="field-label-row">
            <span>Age at next birthday</span>
            {draft.ageSource === 'birth_year' && draft.turningAge ? <small className="calculated-badge">Calculated</small> : null}
          </span>
          <input
            aria-label="Turning age"
            inputMode="numeric"
            max={150}
            min={0}
            placeholder="31"
            type="number"
            value={draft.turningAge}
            onChange={(event) => update('turningAge', event.target.value)}
          />
        </label>
      </div>
      <small className="field-helper">Enter either a birth year or the age at their next birthday; LifeLedger calculates the other. Both are optional.</small>
      {preview ? <small className="person-birthday-preview" role="status">{preview}</small> : null}
      {invalidDay ? <small className="field-error" role="alert">Choose a valid day for that month.</small> : null}
      {invalidBirthYear ? <small className="field-error" role="alert">Enter a birth year that produces an age from 0 to 150.</small> : null}
      {invalidTurningAge ? <small className="field-error" role="alert">Enter an age from 0 to 150.</small> : null}
    </div>
  )
}

function parseBirthday(value: DynamicFieldValue, inferredBirthYear: number | null): BirthdayDraft {
  if (typeof value !== 'string') return emptyDraft()
  const monthDay = /^--(\d{2})-(\d{2})$/.exec(value)
  const fullDate = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!monthDay && !fullDate) return emptyDraft()

  const month = String(Number((fullDate ?? monthDay)![fullDate ? 2 : 1]))
  const day = String(Number((fullDate ?? monthDay)![fullDate ? 3 : 2]))
  const birthYear = fullDate?.[1] ?? (inferredBirthYear ? String(inferredBirthYear) : '')
  const ageSource: BirthdayAgeSource = fullDate ? 'birth_year' : inferredBirthYear ? 'turning_age' : null
  return calculateDraft({ month, day, birthYear, turningAge: '', ageSource })
}

function emptyDraft(): BirthdayDraft {
  return { month: '', day: '', birthYear: '', turningAge: '', ageSource: null }
}

function calculateDraft(draft: BirthdayDraft): BirthdayDraft {
  const dueYear = getNextBirthdayYear(draft.month, draft.day)
  if (draft.ageSource === 'birth_year') {
    const birthYear = Number(draft.birthYear)
    const turningAge = dueYear !== null && draft.birthYear.length === 4 && isValidBirthYear(birthYear)
      ? dueYear - birthYear
      : null
    return { ...draft, turningAge: turningAge !== null && isValidTurningAge(turningAge) ? String(turningAge) : '' }
  }
  if (draft.ageSource === 'turning_age') {
    const turningAge = Number(draft.turningAge)
    const birthYear = dueYear !== null && draft.turningAge !== '' && isValidTurningAge(turningAge)
      ? dueYear - turningAge
      : null
    return { ...draft, birthYear: birthYear !== null ? String(birthYear) : '' }
  }
  return { ...draft, birthYear: '', turningAge: '' }
}

function toStoredBirthday(draft: BirthdayDraft): DynamicFieldValue | undefined {
  const month = Number(draft.month)
  const day = Number(draft.day)
  if (!draft.month || !draft.day || !isValidMonthDay(month, day)) return null
  const monthDay = `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  if (draft.ageSource === null) return `--${monthDay}`
  if (draft.ageSource === 'turning_age') {
    return draft.turningAge !== '' && isValidTurningAge(Number(draft.turningAge)) ? `--${monthDay}` : undefined
  }
  if (draft.birthYear.length < 4) return undefined
  if (!isValidBirthYear(Number(draft.birthYear))) return undefined
  return `${draft.birthYear}-${monthDay}`
}

function isValidMonthDay(month: number, day: number) {
  if (!Number.isInteger(month) || !Number.isInteger(day) || month < 1 || month > 12 || day < 1) return false
  return day <= new Date(2000, month, 0).getDate()
}

function sameDraft(left: BirthdayDraft, right: BirthdayDraft) {
  return left.month === right.month
    && left.day === right.day
    && left.birthYear === right.birthYear
    && left.turningAge === right.turningAge
    && left.ageSource === right.ageSource
}

function isValidBirthYear(year: number) {
  const currentYear = new Date().getFullYear()
  return Number.isInteger(year) && year <= currentYear && year >= currentYear - 150
}

function isValidTurningAge(age: number) {
  return Number.isInteger(age) && age >= 0 && age <= 150
}

function isBirthdayDraftValid(draft: BirthdayDraft) {
  if (!draft.month && !draft.day && !draft.birthYear && !draft.turningAge) return true
  if (!draft.month || !draft.day || !isValidMonthDay(Number(draft.month), Number(draft.day))) return false
  if (draft.ageSource === 'birth_year') return draft.birthYear.length === 4 && isValidBirthYear(Number(draft.birthYear))
  if (draft.ageSource === 'turning_age') return draft.turningAge !== '' && isValidTurningAge(Number(draft.turningAge))
  return true
}

function getBirthdayPreview(draft: BirthdayDraft, subjectName?: string) {
  const month = Number(draft.month)
  const day = Number(draft.day)
  if (!draft.month || !draft.day || !isValidMonthDay(month, day)) return null
  const next = birthdayDateForYear(getNextBirthdayYear(draft.month, draft.day)!, month, day)
  const dateLabel = next.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })
  const name = subjectName?.trim() || 'This birthday'
  if (draft.turningAge !== '' && isValidTurningAge(Number(draft.turningAge))) {
    return `${name} is next on ${dateLabel} · turning ${draft.turningAge}.`
  }
  return `${name} is next on ${dateLabel} · age unknown.`
}

function getNextBirthdayYear(monthValue: string, dayValue: string) {
  const month = Number(monthValue)
  const day = Number(dayValue)
  if (!monthValue || !dayValue || !isValidMonthDay(month, day)) return null
  const today = new Date()
  const thisYear = birthdayDateForYear(today.getFullYear(), month, day)
  return thisYear < startOfToday(today) ? today.getFullYear() + 1 : today.getFullYear()
}

function birthdayDateForYear(year: number, month: number, day: number) {
  const lastDay = new Date(year, month, 0).getDate()
  return new Date(year, month - 1, Math.min(day, lastDay))
}

function startOfToday(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}
