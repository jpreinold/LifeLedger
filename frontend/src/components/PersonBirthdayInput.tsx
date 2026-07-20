import { useEffect, useRef, useState } from 'react'

import type { DynamicFieldValue } from '../types/record'

interface BirthdayParts {
  month: string
  day: string
  year: string
}

const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export function PersonBirthdayInput({
  label = 'Birthday',
  onChange,
  onValidityChange,
  subjectName,
  value,
}: {
  label?: string
  onChange: (value: DynamicFieldValue) => void
  onValidityChange?: (isValid: boolean) => void
  subjectName?: string
  value: DynamicFieldValue
}) {
  const [parts, setParts] = useState<BirthdayParts>(() => parseBirthday(value))
  const partsRef = useRef(parts)

  useEffect(() => {
    const parsed = parseBirthday(value)
    setParts((current) => {
      if (sameParts(current, parsed)) return current
      partsRef.current = parsed
      return parsed
    })
  }, [value])

  function update(part: keyof BirthdayParts, nextValue: string) {
    const next = { ...partsRef.current, [part]: nextValue }
    partsRef.current = next
    setParts(next)
    onValidityChange?.(isBirthdayDraftValid(next, currentYear))
    const stored = toStoredBirthday(next)
    if (stored !== undefined) onChange(stored)
  }

  const currentYear = new Date().getFullYear()
  const invalidDay = Boolean(parts.month && parts.day && !isValidMonthDay(Number(parts.month), Number(parts.day)))
  const invalidYear = Boolean(parts.year && (parts.year.length === 4 && !isValidBirthYear(Number(parts.year), currentYear)))
  const preview = getBirthdayPreview(parts, subjectName)

  return (
    <div className="person-birthday-input" aria-label={label}>
      <span className="person-birthday-label">{label}</span>
      <div className="person-birthday-fields">
        <label>
          <span>Month</span>
          <select value={parts.month} onChange={(event) => update('month', event.target.value)}>
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
            value={parts.day}
            onChange={(event) => update('day', event.target.value)}
          />
        </label>
        <label>
          <span>Year <small>Optional</small></span>
          <input
            inputMode="numeric"
            max={currentYear}
            min={currentYear - 150}
            placeholder="YYYY"
            type="text"
            value={parts.year}
            onChange={(event) => update('year', event.target.value.replace(/\D/g, '').slice(0, 4))}
          />
        </label>
      </div>
      <small className="field-helper">Month and day create an annual linked reminder. Add the year whenever you know it.</small>
      {preview ? <small className="person-birthday-preview" role="status">{preview}</small> : null}
      {invalidDay ? <small className="field-error" role="alert">Choose a valid day for that month.</small> : null}
      {invalidYear ? <small className="field-error" role="alert">Enter a birth year that produces an age from 0 to 150.</small> : null}
    </div>
  )
}

function parseBirthday(value: DynamicFieldValue): BirthdayParts {
  if (typeof value !== 'string') return { month: '', day: '', year: '' }
  const monthDay = /^--(\d{2})-(\d{2})$/.exec(value)
  if (monthDay) return { month: String(Number(monthDay[1])), day: String(Number(monthDay[2])), year: '' }
  const fullDate = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (fullDate) {
    return { month: String(Number(fullDate[2])), day: String(Number(fullDate[3])), year: fullDate[1] }
  }
  return { month: '', day: '', year: '' }
}

function toStoredBirthday(parts: BirthdayParts): DynamicFieldValue | undefined {
  const month = Number(parts.month)
  const day = Number(parts.day)
  if (!parts.month || !parts.day || !isValidMonthDay(month, day)) return null
  const monthDay = `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  if (!parts.year) return `--${monthDay}`
  if (parts.year.length < 4) return undefined
  if (!isValidBirthYear(Number(parts.year), new Date().getFullYear())) return undefined
  return `${parts.year}-${monthDay}`
}

function isValidMonthDay(month: number, day: number) {
  if (!Number.isInteger(month) || !Number.isInteger(day) || month < 1 || month > 12 || day < 1) return false
  return day <= new Date(2000, month, 0).getDate()
}

function sameParts(left: BirthdayParts, right: BirthdayParts) {
  return left.month === right.month && left.day === right.day && left.year === right.year
}

function isValidBirthYear(year: number, currentYear: number) {
  return Number.isInteger(year) && year <= currentYear && year >= currentYear - 150
}

function isBirthdayDraftValid(parts: BirthdayParts, currentYear: number) {
  if (!parts.month && !parts.day && !parts.year) return true
  if (!parts.month || !parts.day || !isValidMonthDay(Number(parts.month), Number(parts.day))) return false
  if (!parts.year) return true
  return parts.year.length === 4 && isValidBirthYear(Number(parts.year), currentYear)
}

function getBirthdayPreview(parts: BirthdayParts, subjectName?: string) {
  const month = Number(parts.month)
  const day = Number(parts.day)
  if (!parts.month || !parts.day || !isValidMonthDay(month, day)) return null
  const today = new Date()
  const thisYear = birthdayDateForYear(today.getFullYear(), month, day)
  const next = thisYear < startOfToday(today) ? birthdayDateForYear(today.getFullYear() + 1, month, day) : thisYear
  const dateLabel = next.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })
  const name = subjectName?.trim() || 'This birthday'
  if (parts.year.length === 4 && isValidBirthYear(Number(parts.year), today.getFullYear())) {
    return `${name} is next on ${dateLabel} · turning ${next.getFullYear() - Number(parts.year)}.`
  }
  return `${name} is next on ${dateLabel} · age unknown.`
}

function birthdayDateForYear(year: number, month: number, day: number) {
  const lastDay = new Date(year, month, 0).getDate()
  return new Date(year, month - 1, Math.min(day, lastDay))
}

function startOfToday(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}
