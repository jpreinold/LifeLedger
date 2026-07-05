import { useEffect, useState } from 'react'
import type { Dispatch, FormEvent, SetStateAction } from 'react'
import { Bell, Cake, LayoutTemplate, Plus, X } from 'lucide-react'

import {
  type BirthdayDetailsInput,
  priorityOptions,
  reminderCategories,
  reminderLeadUnits,
  repeatOptions,
  type ReminderInput,
} from '../types/reminder'
import { buildReminderSubmitInput, emptyBirthdayDetails, isReminderReady } from '../lib/reminderInput'
import {
  DEFAULT_REMINDER_LEAD_UNIT,
  DEFAULT_REMINDER_LEAD_VALUE,
  DEFAULT_REMINDER_TIME,
  buildReminderInputWithDefaultTiming,
  defaultReminderTiming,
  getPresetTiming,
  getReminderLeadPreset,
  reminderLeadOptions,
  type ReminderLeadPreset,
} from '../lib/reminderSchedule'
import { getCategoryVisual } from './categoryVisuals'
import { SheetDrawer } from './SheetDrawer'

interface ReminderFormProps {
  isOpen: boolean
  isSaving: boolean
  onCreate: (input: ReminderInput) => Promise<boolean>
  onBrowseTemplates: () => void
  onClose: () => void
  templateDraft: TemplateDraft | null
}

const today = new Date().toISOString().slice(0, 10)
const monthOptions = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
]

export interface TemplateDraft {
  id: string
  input: ReminderInput
}

interface ReminderFieldsProps {
  form: ReminderInput
  setForm: Dispatch<SetStateAction<ReminderInput>>
}

const initialForm: ReminderInput = {
  title: '',
  category: 'Other',
  due_date: today,
  repeat: 'None',
  priority: 'Medium',
  notes: null,
  reminder_type: 'generic',
  birthday_details: null,
  ...defaultReminderTiming(),
}

export function ReminderForm({
  isOpen,
  isSaving,
  onCreate,
  onBrowseTemplates,
  onClose,
  templateDraft,
}: ReminderFormProps) {
  const [form, setForm] = useState<ReminderInput>(initialForm)
  const { Icon, tone } = getCategoryVisual(form.category)

  useEffect(() => {
    if (isOpen && !templateDraft) {
      setForm({ ...initialForm, due_date: new Date().toISOString().slice(0, 10) })
    }
  }, [isOpen, templateDraft])

  useEffect(() => {
    if (!templateDraft) {
      return
    }

    setForm((current) =>
      buildReminderInputWithDefaultTiming({
        ...templateDraft.input,
        due_date: current.due_date || new Date().toISOString().slice(0, 10),
      }),
    )
  }, [templateDraft])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const wasCreated = await onCreate(buildReminderSubmitInput(form))

    if (wasCreated) {
      setForm({ ...initialForm, due_date: new Date().toISOString().slice(0, 10) })
      onClose()
    }
  }

  return (
    <SheetDrawer className="add-dialog" isOpen={isOpen} labelledBy="add-reminder-heading" onClose={onClose}>
        <div className="sheet-header">
          <div>
            <h2 id="add-reminder-heading">Add Reminder</h2>
            <p>Choose a template or start from a blank reminder.</p>
          </div>
          <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close add reminder">
            <X size={19} aria-hidden="true" />
          </button>
        </div>

        <div className="sheet-icon-lockup">
          <div className={`category-icon category-icon-large tone-${tone}`} aria-hidden="true">
            <Icon size={30} />
          </div>
          <button type="button" className="small-outline-button" onClick={onBrowseTemplates}>
            <LayoutTemplate size={15} aria-hidden="true" />
            Browse templates
          </button>
        </div>

        <form className="reminder-form sheet-body" onSubmit={handleSubmit}>
          <ReminderFields form={form} setForm={setForm} />

          <button className="primary-button" type="submit" disabled={isSaving || !isReminderReady(form)}>
            <Plus size={18} aria-hidden="true" />
            {isSaving ? 'Saving' : 'Add reminder'}
          </button>
        </form>
    </SheetDrawer>
  )
}

export function ReminderFields({ form, setForm }: ReminderFieldsProps) {
  const selectedReminderPreset = getReminderLeadPreset(form)

  function handleReminderPresetChange(preset: ReminderLeadPreset) {
    setForm((current) => {
      if (preset === 'custom') {
        return {
          ...current,
          reminder_lead_value:
            current.reminder_lead_value && current.reminder_lead_value > 1 ? current.reminder_lead_value : 2,
          reminder_lead_unit: current.reminder_lead_unit ?? DEFAULT_REMINDER_LEAD_UNIT,
          reminder_time: current.reminder_time ?? DEFAULT_REMINDER_TIME,
        }
      }

      return { ...current, ...getPresetTiming(preset, current) }
    })
  }

  return (
    <>
      {form.reminder_type === 'birthday' ? <BirthdayFields form={form} setForm={setForm} /> : null}

      <label>
        <span>Title</span>
        <input
          required
          maxLength={120}
          value={form.title}
          onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
          placeholder="Renew car tag"
        />
      </label>

      <div className="form-row">
        <label>
          <span>Category</span>
          <select
            value={form.category}
            onChange={(event) =>
              setForm((current) => ({ ...current, category: event.target.value as ReminderInput['category'] }))
            }
          >
            {reminderCategories.map((category) => (
              <option value={category} key={category}>
                {category}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>{form.reminder_type === 'birthday' ? 'Next birthday' : 'Due date'}</span>
          <input
            required
            type="date"
            value={form.due_date}
            disabled={form.reminder_type === 'birthday'}
            onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))}
          />
        </label>
      </div>

      <div className="form-row">
        <label>
          <span>Repeat</span>
          <select
            value={form.repeat}
            onChange={(event) =>
              setForm((current) => ({ ...current, repeat: event.target.value as ReminderInput['repeat'] }))
            }
          >
            {repeatOptions.map((repeat) => (
              <option value={repeat} key={repeat}>
                {repeat}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Priority</span>
          <select
            value={form.priority}
            onChange={(event) =>
              setForm((current) => ({ ...current, priority: event.target.value as ReminderInput['priority'] }))
            }
          >
            {priorityOptions.map((priority) => (
              <option value={priority} key={priority}>
                {priority}
              </option>
            ))}
          </select>
        </label>
      </div>

      <section className="remind-me-section" aria-labelledby="remind-me-heading">
        <div className="form-section-heading">
          <Bell size={16} aria-hidden="true" />
          <span id="remind-me-heading">Remind me</span>
        </div>

        <div className="form-row">
          <label>
            <span>Timing</span>
            <select
              value={selectedReminderPreset}
              onChange={(event) => handleReminderPresetChange(event.target.value as ReminderLeadPreset)}
            >
              {reminderLeadOptions.map((option) => (
                <option value={option.id} key={option.id}>
                  {option.label}
                </option>
              ))}
              <option value="custom">Custom</option>
            </select>
          </label>

          <label>
            <span>Time</span>
            <input
              type="time"
              value={form.reminder_time ?? DEFAULT_REMINDER_TIME}
              onChange={(event) =>
                setForm((current) => ({ ...current, reminder_time: event.target.value || DEFAULT_REMINDER_TIME }))
              }
            />
          </label>
        </div>

        {selectedReminderPreset === 'custom' ? (
          <div className="form-row">
            <label>
              <span>Lead</span>
              <input
                type="number"
                min="0"
                max="36"
                value={form.reminder_lead_value ?? DEFAULT_REMINDER_LEAD_VALUE}
                onChange={(event) =>
                  setForm((current) => ({ ...current, reminder_lead_value: Number(event.target.value || 0) }))
                }
              />
            </label>

            <label>
              <span>Unit</span>
              <select
                value={form.reminder_lead_unit ?? DEFAULT_REMINDER_LEAD_UNIT}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    reminder_lead_unit: event.target.value as ReminderInput['reminder_lead_unit'],
                  }))
                }
              >
                {reminderLeadUnits.map((unit) => (
                  <option value={unit} key={unit}>
                    {unit}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : null}
      </section>
      <label>
        <span>Notes</span>
        <textarea
          maxLength={1000}
          value={form.notes ?? ''}
          onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value || null }))}
          rows={4}
          placeholder="Optional details"
        />
      </label>
    </>
  )
}

function BirthdayFields({ form, setForm }: ReminderFieldsProps) {
  const details = form.birthday_details ?? emptyBirthdayDetails()
  const dayCount = details.birth_month ? getDaysInMonth(details.birth_month) : 31
  const dayOptions = Array.from({ length: dayCount }, (_, index) => index + 1)
  const ageSource = getBirthdayAgeSource(details)
  const preview = getBirthdayPreview(details, form.due_date)

  function updateDetails(updates: Partial<BirthdayDetailsInput>, editedSource?: BirthdayAgeSource) {
    setForm((current) => {
      const currentDetails = current.birthday_details ?? emptyBirthdayDetails()
      const source = editedSource ?? getBirthdayAgeSource(currentDetails)
      const mergedDetails = { ...currentDetails, ...updates }
      const dueDate =
        mergedDetails.birth_month && mergedDetails.birth_day
          ? getNextBirthdayDate(mergedDetails.birth_month, mergedDetails.birth_day)
          : current.due_date
      const nextDetails = calculateBirthdayDetails(mergedDetails, source, dueDate)

      return {
        ...current,
        title:
          updates.person_name !== undefined && shouldUpdateBirthdayTitle(current.title, currentDetails.person_name)
            ? formatBirthdayTitle(nextDetails.person_name)
            : current.title,
        category: current.category === 'Other' ? 'Family' : current.category,
        due_date: dueDate,
        repeat: 'Yearly',
        priority: current.priority || 'Medium',
        reminder_lead_value: current.reminder_lead_value ?? 1,
        reminder_lead_unit: current.reminder_lead_unit ?? 'weeks',
        reminder_time: current.reminder_time ?? '09:00',
        birthday_details: nextDetails,
      }
    })
  }

  function handleMonthChange(value: string) {
    const birthMonth = toOptionalNumber(value)
    const nextDay =
      birthMonth && details.birth_day && details.birth_day > getDaysInMonth(birthMonth) ? null : details.birth_day

    updateDetails({
      birth_month: birthMonth,
      birth_day: nextDay,
    })
  }

  function handleBirthYearChange(value: string) {
    const birthYear = toOptionalNumber(value)
    updateDetails({
      birth_year: birthYear,
      inferred_birth_year: false,
    }, 'birth_year')
  }

  function handleTurningAgeChange(value: string) {
    const turningAge = toOptionalNumber(value)
    updateDetails({
      age_turning_next_birthday: turningAge,
      inferred_birth_year: turningAge !== null,
    }, 'turning_age')
  }

  return (
    <section className="birthday-details-section" aria-labelledby="birthday-details-heading">
      <div className="form-section-heading">
        <Cake size={16} aria-hidden="true" />
        <span id="birthday-details-heading">Birthday</span>
      </div>

      <p className="birthday-helper-text">
        Optional: add a birth year or turning age to calculate age automatically.
      </p>

      <label>
        <span>Person</span>
        <input
          required
          maxLength={120}
          value={details.person_name}
          onChange={(event) => updateDetails({ person_name: event.target.value })}
          placeholder="Max"
        />
      </label>

      <div className="form-row">
        <label>
          <span>Month</span>
          <select value={details.birth_month ?? ''} onChange={(event) => handleMonthChange(event.target.value)}>
            <option value="">Select month</option>
            {monthOptions.map((month) => (
              <option value={month.value} key={month.value}>
                {month.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Day</span>
          <select
            value={details.birth_day ?? ''}
            onChange={(event) => updateDetails({ birth_day: toOptionalNumber(event.target.value) })}
          >
            <option value="">Select day</option>
            {dayOptions.map((day) => (
              <option value={day} key={day}>
                {day}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="form-row">
        <label className="calculated-field-label">
          <span className="field-label-row">
            <span>Birth year</span>
            {ageSource === 'turning_age' && details.birth_year !== null ? (
              <small className="calculated-badge">Calculated</small>
            ) : null}
          </span>
          <input
            inputMode="numeric"
            min="1"
            max="9999"
            type="number"
            value={details.birth_year ?? ''}
            onChange={(event) => handleBirthYearChange(event.target.value)}
            placeholder="1999"
          />
        </label>

        <label className="calculated-field-label">
          <span className="field-label-row">
            <span>Turning age</span>
            {ageSource === 'birth_year' && details.age_turning_next_birthday !== null ? (
              <small className="calculated-badge">Calculated</small>
            ) : null}
          </span>
          <input
            inputMode="numeric"
            min="0"
            max="150"
            type="number"
            value={details.age_turning_next_birthday ?? ''}
            onChange={(event) => handleTurningAgeChange(event.target.value)}
            placeholder="31"
          />
        </label>
      </div>

      <label>
        <span>Relationship</span>
        <input
          maxLength={80}
          value={details.relationship ?? ''}
          onChange={(event) => updateDetails({ relationship: event.target.value || null })}
          placeholder="Friend"
        />
      </label>

      <p className="birthday-preview">{preview}</p>
    </section>
  )
}

type BirthdayAgeSource = 'birth_year' | 'turning_age' | null

function shouldUpdateBirthdayTitle(currentTitle: string, previousPersonName: string) {
  const trimmedTitle = currentTitle.trim()
  return (
    !trimmedTitle ||
    trimmedTitle === 'Birthday reminder' ||
    trimmedTitle === formatBirthdayTitle(previousPersonName) ||
    trimmedTitle === formatBirthdayTitle(previousPersonName).replace(' Birthday', ' birthday')
  )
}

function formatBirthdayTitle(personName: string) {
  const trimmedName = personName.trim()
  return trimmedName ? `${trimmedName}'s Birthday` : 'Birthday reminder'
}

function calculateBirthdayDetails(
  details: BirthdayDetailsInput,
  source: BirthdayAgeSource,
  dueDate: string,
): BirthdayDetailsInput {
  const dueYear = details.birth_month && details.birth_day ? Number(dueDate.slice(0, 4)) : null
  const birthYear = toOptionalNumber(details.birth_year)
  const turningAge = toOptionalNumber(details.age_turning_next_birthday)

  if (source === 'birth_year') {
    return {
      ...details,
      birth_year: birthYear,
      age_turning_next_birthday:
        birthYear !== null && dueYear !== null ? clampOptionalAge(dueYear - birthYear) : null,
      inferred_birth_year: false,
    }
  }

  if (source === 'turning_age') {
    return {
      ...details,
      birth_year: turningAge !== null && dueYear !== null ? dueYear - turningAge : null,
      age_turning_next_birthday: turningAge,
      inferred_birth_year: turningAge !== null,
    }
  }

  return {
    ...details,
    birth_year: null,
    age_turning_next_birthday: null,
    inferred_birth_year: false,
  }
}

function getBirthdayAgeSource(details: BirthdayDetailsInput): BirthdayAgeSource {
  if (details.inferred_birth_year && details.age_turning_next_birthday !== null) {
    return 'turning_age'
  }

  if (details.birth_year !== null) {
    return 'birth_year'
  }

  if (details.age_turning_next_birthday !== null) {
    return 'turning_age'
  }

  return null
}

function getBirthdayPreview(details: BirthdayDetailsInput, dueDate: string) {
  if (!details.birth_month || !details.birth_day) {
    return 'Choose a month and day to calculate the next birthday.'
  }

  const dateLabel = formatFullDate(dueDate)
  const personName = details.person_name.trim()
  const turningAge = details.age_turning_next_birthday

  if (turningAge !== null) {
    return personName
      ? `${personName} turns ${turningAge} on ${dateLabel}.`
      : `They turn ${turningAge} on ${dateLabel}.`
  }

  return personName
    ? `${personName}'s next birthday is ${dateLabel}. Age unknown.`
    : `Next birthday is ${dateLabel}. Age unknown.`
}

function clampOptionalAge(value: number) {
  if (!Number.isFinite(value) || value < 0 || value > 150) {
    return null
  }

  return value
}

function getNextBirthdayDate(month: number, day: number) {
  const currentDay = startOfDay(new Date())
  let candidate = birthdayDateForYear(currentDay.getFullYear(), month, day)

  if (candidate.getTime() < currentDay.getTime()) {
    candidate = birthdayDateForYear(currentDay.getFullYear() + 1, month, day)
  }

  return formatDateOnly(candidate)
}

function birthdayDateForYear(year: number, month: number, day: number) {
  if (month === 2 && day === 29 && !isLeapYear(year)) {
    return new Date(year, 1, 28)
  }

  return new Date(year, month - 1, day)
}

function getDaysInMonth(month: number) {
  return new Date(2000, month, 0).getDate()
}

function isLeapYear(year: number) {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
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
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)

  return new Intl.DateTimeFormat(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(year, month - 1, day))
}

function toOptionalNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numericValue = Number(value)
  return Number.isFinite(numericValue) ? numericValue : null
}
