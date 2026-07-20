import { useEffect, useState } from 'react'

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
  value,
}: {
  label?: string
  onChange: (value: DynamicFieldValue) => void
  value: DynamicFieldValue
}) {
  const [parts, setParts] = useState<BirthdayParts>(() => parseBirthday(value))

  useEffect(() => {
    const parsed = parseBirthday(value)
    setParts((current) => sameParts(current, parsed) ? current : parsed)
  }, [value])

  function update(part: keyof BirthdayParts, nextValue: string) {
    const next = { ...parts, [part]: nextValue }
    setParts(next)
    onChange(toStoredBirthday(next))
  }

  const currentYear = new Date().getFullYear()
  const invalidDay = Boolean(parts.month && parts.day && !isValidMonthDay(Number(parts.month), Number(parts.day)))

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
            type="number"
            value={parts.year}
            onChange={(event) => update('year', event.target.value)}
          />
        </label>
      </div>
      <small className="field-helper">Month and day create an annual linked reminder. Add the year whenever you know it.</small>
      {invalidDay ? <small className="field-error" role="alert">Choose a valid day for that month.</small> : null}
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

function toStoredBirthday(parts: BirthdayParts): DynamicFieldValue {
  const month = Number(parts.month)
  const day = Number(parts.day)
  if (!parts.month || !parts.day || !isValidMonthDay(month, day)) return null
  const monthDay = `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  if (!parts.year) return `--${monthDay}`
  return `${parts.year.padStart(4, '0')}-${monthDay}`
}

function isValidMonthDay(month: number, day: number) {
  if (!Number.isInteger(month) || !Number.isInteger(day) || month < 1 || month > 12 || day < 1) return false
  return day <= new Date(2000, month, 0).getDate()
}

function sameParts(left: BirthdayParts, right: BirthdayParts) {
  return left.month === right.month && left.day === right.day && left.year === right.year
}
