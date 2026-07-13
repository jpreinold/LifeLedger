import { useEffect, useState } from 'react'
import type { Dispatch, FormEvent, SetStateAction } from 'react'
import { Cake, Check, LayoutTemplate, Plus, RefreshCcw, Wrench } from 'lucide-react'

import {
  type BirthdayDetailsInput,
  type MaintenanceDetailsInput,
  type RenewalDetailsInput,
  priorityOptions,
  reminderCategories,
  maintenanceIntervalUnits,
  reminderLeadUnits,
  repeatOptions,
  type ReminderInput,
} from '../types/reminder'
import { buildReminderSubmitInput, emptyBirthdayDetails, emptyMaintenanceDetails, emptyRenewalDetails, isReminderReady } from '../lib/reminderInput'
import {
  getRenewalDateLabel,
  getRenewalDefaults,
  getRenewalDisplayKind,
  getRenewalHelperText,
  getRenewalItemLabel,
  getRenewalPreview,
  getRenewalTitle,
  getRenewalValidationMessage,
  getRelevantRenewalDate,
  isAutoRenewalTitle,
  renewalKindOptions,
  withRenewalDisplayKind,
  type RenewalDisplayKind,
} from '../lib/renewalUx'
import {
  getCalculatedMaintenanceDueDate,
  getMaintenanceAreaCategory,
  getMaintenanceDefaults,
  getMaintenanceDueDate,
  getMaintenancePreview,
  getMaintenanceRepeat,
  getMaintenanceTitle,
  getMaintenanceValidationMessage,
  isAutoMaintenanceTitle,
  maintenanceAreaOptions,
} from '../lib/maintenanceUx'
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
const reminderFormId = 'add-reminder-form'
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
  renewal_details: null,
  maintenance_details: null,
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

  useEffect(() => {
    if (isOpen && !templateDraft) {
      setForm({ ...initialForm, due_date: new Date().toISOString().slice(0, 10) })
    }
  }, [isOpen, templateDraft])

  useEffect(() => {
    if (!templateDraft) {
      return
    }

    setForm((current) => {
      const nextDueDate = templateDraft.input.due_date || ((templateDraft.input.reminder_type === 'renewal' || templateDraft.input.reminder_type === 'maintenance')
        ? ''
        : current.due_date || new Date().toISOString().slice(0, 10))

      return buildReminderInputWithDefaultTiming({
        ...templateDraft.input,
        due_date: nextDueDate,
      })
    })
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
    <SheetDrawer
      className="add-dialog reminder-form-dialog"
      closeLabel="Close add reminder"
      footer={(
        <div className="sheet-footer-actions">
          <button className="primary-button reminder-submit-button" type="submit" form={reminderFormId} disabled={isSaving || !isReminderReady(form)}>
            <Plus size={18} aria-hidden="true" />
            {isSaving ? 'Saving' : 'Add reminder'}
          </button>

          <button type="button" className="text-link-button reminder-template-action" onClick={onBrowseTemplates}>
            <LayoutTemplate size={15} aria-hidden="true" />
            Browse templates
          </button>
        </div>
      )}
      isOpen={isOpen}
      labelledBy="add-reminder-heading"
      onClose={onClose}
      subtitle={getAddFormDescription(form.reminder_type)}
      title={getAddFormHeading(form.reminder_type)}
    >
        <form id={reminderFormId} className="reminder-form" onSubmit={handleSubmit}>
          <ReminderFields form={form} setForm={setForm} />
        </form>
    </SheetDrawer>
  )
}

export function ReminderFields({ form, setForm }: ReminderFieldsProps) {
  const selectedReminderPreset = getReminderLeadPreset(form)
  const renewalDetails = form.renewal_details
  const maintenanceDetails = form.maintenance_details
  const computedRepeat = getComputedRepeat(form)
  const canEditRepeat = form.reminder_type === 'generic' || form.reminder_type === 'renewal'
  const renewalDisplayKind = form.reminder_type === 'renewal'
    ? getRenewalDisplayKind(renewalDetails, { title: form.title, category: form.category })
    : null
  const titlePlaceholder = renewalDisplayKind && renewalDetails
    ? getRenewalTitle(renewalDetails.item_name, renewalDisplayKind)
    : form.reminder_type === 'maintenance' && maintenanceDetails
      ? getMaintenanceTitle(maintenanceDetails.item_name)
      : 'Renew car tag'

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
      <section className="reminder-progressive-section reminder-essentials-section" aria-labelledby="reminder-essentials-heading">
        <div className="form-section-heading">
          <span id="reminder-essentials-heading">Essentials</span>
        </div>
        <label>
          <span>{form.reminder_type === 'renewal' || form.reminder_type === 'maintenance' ? 'Reminder title' : 'Title'}</span>
          <input
            required
            maxLength={120}
            value={form.title}
            onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
            placeholder={titlePlaceholder}
          />
        </label>

        {form.reminder_type === 'generic' ? (
          <label>
            <span>Due date</span>
            <input
              required
              type="date"
              value={form.due_date}
              onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))}
            />
          </label>
        ) : null}
      </section>

      {form.reminder_type !== 'generic' ? (
        <details className="reminder-progressive-section reminder-collapsible-section reminder-smart-details-section" open>
          <summary>Smart details</summary>
          {form.reminder_type === 'birthday' ? <BirthdayFields form={form} setForm={setForm} /> : null}
          {form.reminder_type === 'renewal' ? <RenewalFields form={form} setForm={setForm} /> : null}
          {form.reminder_type === 'maintenance' ? <MaintenanceFields form={form} setForm={setForm} /> : null}
        </details>
      ) : null}

      <details className="reminder-progressive-section reminder-collapsible-section">
        <summary>Schedule</summary>
        {form.reminder_type !== 'generic' && form.reminder_type !== 'renewal' && form.reminder_type !== 'maintenance' ? (
          <label>
            <span>{getDueDateFieldLabel(form.reminder_type)}</span>
            <input
              required
              type="date"
              value={form.due_date}
              disabled={form.reminder_type === 'birthday'}
              onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))}
            />
          </label>
        ) : null}

        <div className="form-row">
          <label>
            <span>Repeat</span>
            <select
              value={computedRepeat}
              disabled={!canEditRepeat}
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
            {!canEditRepeat ? (
              <small className="field-helper">Repeat is calculated from the smart reminder details.</small>
            ) : null}
          </label>

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
        </div>

        <div className="form-row">
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

          {selectedReminderPreset === 'custom' ? (
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
          ) : null}
        </div>

        {selectedReminderPreset === 'custom' ? (
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
        ) : null}
      </details>

      <details className="reminder-progressive-section reminder-collapsible-section">
        <summary>More options</summary>
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
      </details>
    </>
  )
}

function MaintenanceFields({ form, setForm }: ReminderFieldsProps) {
  const details = form.maintenance_details ?? emptyMaintenanceDetails()
  const preview = getMaintenancePreview({ ...form, maintenance_details: details })
  const validationMessage = getMaintenanceValidationMessage({ ...form, maintenance_details: details })

  function updateDetails(updates: Partial<MaintenanceDetailsInput>, options: { recalculateDueDate?: boolean } = {}) {
    setForm((current) => {
      const currentDetails = current.maintenance_details ?? emptyMaintenanceDetails()
      const mergedDetails = { ...currentDetails, ...updates }
      const calculatedDueDate = options.recalculateDueDate ? getCalculatedMaintenanceDueDate(mergedDetails) : ''
      const nextDetails = {
        ...mergedDetails,
        next_due_date: calculatedDueDate || mergedDetails.next_due_date,
      }
      const nextDueDate = getMaintenanceDueDate(nextDetails, current.due_date)
      const shouldRefreshTitle = updates.item_name !== undefined

      return {
        ...current,
        title: shouldRefreshTitle && isAutoMaintenanceTitle(current.title, currentDetails.item_name)
          ? getMaintenanceTitle(nextDetails.item_name)
          : current.title,
        category: getMaintenanceAreaCategory(nextDetails.maintenance_area),
        due_date: nextDueDate,
        repeat: getMaintenanceRepeat(nextDetails),
        maintenance_details: nextDetails,
      }
    })
  }

  function handleAreaChange(value: string) {
    const maintenanceArea = value as MaintenanceDetailsInput['maintenance_area']
    const defaults = getMaintenanceDefaults(maintenanceArea)

    setForm((current) => {
      const currentDetails = current.maintenance_details ?? emptyMaintenanceDetails()
      const nextDetails = {
        ...currentDetails,
        maintenance_area: maintenanceArea,
        interval_value: defaults.interval_value,
        interval_unit: defaults.interval_unit,
      }
      const calculatedDueDate = getCalculatedMaintenanceDueDate(nextDetails)
      const nextWithDueDate = {
        ...nextDetails,
        next_due_date: calculatedDueDate || nextDetails.next_due_date,
      }

      return {
        ...current,
        category: current.category === 'Other' ? defaults.category : current.category,
        repeat: getMaintenanceRepeat(nextWithDueDate),
        priority: defaults.priority,
        reminder_lead_value: defaults.reminder_lead_value,
        reminder_lead_unit: defaults.reminder_lead_unit,
        reminder_time: defaults.reminder_time,
        due_date: getMaintenanceDueDate(nextWithDueDate, current.due_date),
        maintenance_details: nextWithDueDate,
      }
    })
  }

  function handleLastCompletedToday() {
    updateDetails({ last_completed_date: new Date().toISOString().slice(0, 10) }, { recalculateDueDate: true })
  }

  return (
    <section className="maintenance-details-section" aria-labelledby="maintenance-details-heading">
      <div className="form-section-heading">
        <Wrench size={16} aria-hidden="true" />
        <span id="maintenance-details-heading">Maintenance setup</span>
      </div>

      <p className="maintenance-helper-text">
        Add the interval and LifeLedger will calculate the next due date after each completion.
      </p>

      <div className="form-row">
        <label>
          <span>Item name</span>
          <input
            required
            maxLength={120}
            value={details.item_name}
            onChange={(event) => updateDetails({ item_name: event.target.value })}
            placeholder="Change HVAC filter"
          />
        </label>

        <label>
          <span>Maintenance area</span>
          <select value={details.maintenance_area} onChange={(event) => handleAreaChange(event.target.value)}>
            {maintenanceAreaOptions.map((option) => (
              <option value={option.area} key={option.area}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="form-row">
        <label>
          <span>Every</span>
          <input
            required
            type="number"
            min="1"
            max="365"
            inputMode="numeric"
            value={details.interval_value ?? ''}
            onChange={(event) => updateDetails({ interval_value: toOptionalNumber(event.target.value) }, { recalculateDueDate: true })}
          />
        </label>

        <label>
          <span>Interval unit</span>
          <select
            value={details.interval_unit ?? 'months'}
            onChange={(event) => updateDetails({ interval_unit: event.target.value as MaintenanceDetailsInput['interval_unit'] }, { recalculateDueDate: true })}
          >
            {maintenanceIntervalUnits.map((unit) => (
              <option value={unit} key={unit}>
                {unit}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="form-row">
        <label>
          <span>Last completed date (optional)</span>
          <input
            type="date"
            value={details.last_completed_date ?? ''}
            onChange={(event) => updateDetails({ last_completed_date: event.target.value || null }, { recalculateDueDate: true })}
          />
        </label>

        <label>
          <span>Next due date</span>
          <input
            required
            type="date"
            value={details.next_due_date ?? ''}
            onChange={(event) => updateDetails({ next_due_date: event.target.value })}
          />
        </label>
      </div>

      <button type="button" className="small-outline-button maintenance-today-button" onClick={handleLastCompletedToday}>
        Completed today
      </button>

      <label>
        <span>Instructions (optional)</span>
        <textarea
          maxLength={1000}
          value={details.instructions ?? ''}
          onChange={(event) => updateDetails({ instructions: event.target.value || null })}
          rows={3}
          placeholder="General steps or supplies to check"
        />
      </label>

      <p className="maintenance-safety-note">
        Keep notes general. Do not store passwords, account numbers, or sensitive details.
      </p>

      {validationMessage ? <p className="field-error">{validationMessage}</p> : null}

      <div className="maintenance-preview" aria-live="polite">
        <strong>{preview.primary}</strong>
        {preview.reminder ? <span>{preview.reminder}</span> : null}
        {preview.card ? <small>{preview.card}</small> : null}
      </div>
    </section>
  )
}

function RenewalFields({ form, setForm }: ReminderFieldsProps) {
  const details = form.renewal_details ?? emptyRenewalDetails()
  const [touched, setTouched] = useState({ date: false, item: false })
  const displayKind = getRenewalDisplayKind(details, { title: form.title, category: form.category })
  const relevantDate = getRelevantRenewalFormDate(details, form.due_date)
  const preview = getRenewalPreview({ ...form, renewal_details: details })
  const validationMessage = getRenewalValidationMessage({ ...form, renewal_details: details })
  const itemErrorId = 'renewal-item-name-error'
  const dateErrorId = 'renewal-date-error'
  const itemError = touched.item && !details.item_name.trim() ? 'Enter an item name.' : null
  const dateError = touched.date && !relevantDate ? 'Choose the date you want to track.' : null
  const safetyError = validationMessage && validationMessage !== 'Enter an item name.' && validationMessage !== 'Choose the date you want to track.'
    ? validationMessage
    : null

  function updateDetails(updates: Partial<RenewalDetailsInput>) {
    setForm((current) => {
      const currentDetails = current.renewal_details ?? emptyRenewalDetails()
      const currentDisplayKind = getRenewalDisplayKind(currentDetails, {
        title: current.title,
        category: current.category,
      })
      const mergedDetails = withRenewalDisplayKind({ ...currentDetails, ...updates }, currentDisplayKind)
      const nextDate = getRelevantRenewalFormDate(mergedDetails, current.due_date)
      const nextDetails = withRelevantRenewalDate(mergedDetails, nextDate)
      const shouldRefreshTitle = updates.item_name !== undefined

      return {
        ...current,
        title: shouldRefreshTitle && isAutoRenewalTitle(current.title, currentDetails)
          ? getRenewalTitle(nextDetails.item_name, currentDisplayKind)
          : current.title,
        due_date: nextDate,
        renewal_details: nextDetails,
      }
    })
  }

  function handleKindChange(nextKind: RenewalDisplayKind) {
    setTouched({ date: false, item: false })
    setForm((current) => {
      const currentDetails = current.renewal_details ?? emptyRenewalDetails()
      const defaults = getRenewalDefaults(nextKind)
      const mergedDetails = withRenewalDisplayKind(currentDetails, nextKind)
      const nextDate = getRelevantRenewalFormDate(mergedDetails, current.due_date)
      const nextDetails = {
        ...withRelevantRenewalDate(mergedDetails, nextDate),
        renewal_window_days: defaults.renewal_window_days ?? null,
        review_lead_days: defaults.review_lead_days ?? null,
      }

      return {
        ...current,
        title: isAutoRenewalTitle(current.title, currentDetails)
          ? getRenewalTitle(nextDetails.item_name, nextKind)
          : current.title,
        category: defaults.category && current.category === 'Other' ? defaults.category : current.category,
        due_date: nextDate,
        repeat: defaults.repeat,
        priority: defaults.priority,
        reminder_lead_value: defaults.reminder_lead_value,
        reminder_lead_unit: defaults.reminder_lead_unit,
        reminder_time: defaults.reminder_time,
        renewal_details: nextDetails,
      }
    })
  }

  return (
    <section className="renewal-details-section" aria-labelledby="renewal-details-heading">
      <div className="form-section-heading">
        <RefreshCcw size={16} aria-hidden="true" />
        <span id="renewal-details-heading">Renewal setup</span>
      </div>

      <div className="renewal-kind-grid" role="radiogroup" aria-label="Date type">
        {renewalKindOptions.map((option) => {
          const isSelected = option.kind === displayKind

          return (
            <button
              type="button"
              className={isSelected ? 'renewal-kind-option active' : 'renewal-kind-option'}
              key={option.kind}
              role="radio"
              onClick={() => handleKindChange(option.kind)}
              aria-checked={isSelected}
            >
              <span className="renewal-kind-copy">
                <strong>{option.label}</strong>
                <small>{option.description}</small>
              </span>
              {isSelected ? <Check size={15} aria-hidden="true" /> : null}
            </button>
          )
        })}
      </div>

      <p className="renewal-helper-text">{getRenewalHelperText(displayKind)}</p>

      <div className="form-row">
        <label>
          <span>{getRenewalItemLabel(displayKind)}</span>
          <input
            required
            aria-describedby={itemError ? itemErrorId : undefined}
            aria-invalid={Boolean(itemError)}
            maxLength={120}
            value={details.item_name}
            onChange={(event) => updateDetails({ item_name: event.target.value })}
            onBlur={() => setTouched((current) => ({ ...current, item: true }))}
            placeholder={getRenewalItemPlaceholder(displayKind)}
          />
          {itemError ? <span className="field-error" id={itemErrorId}>{itemError}</span> : null}
        </label>

        <label>
          <span>{getRenewalDateLabel(displayKind)}</span>
          <input
            required
            aria-describedby={dateError ? dateErrorId : undefined}
            aria-invalid={Boolean(dateError)}
            type="date"
            value={relevantDate}
            onChange={(event) => updateDetails(withRelevantRenewalDate(details, event.target.value))}
            onBlur={() => setTouched((current) => ({ ...current, date: true }))}
          />
          {dateError ? <span className="field-error" id={dateErrorId}>{dateError}</span> : null}
        </label>
      </div>

      <div className="form-row">
        <label>
          <span>Owner/person (optional)</span>
          <input
            maxLength={120}
            value={details.owner_name ?? ''}
            onChange={(event) => updateDetails({ owner_name: event.target.value || null })}
            placeholder="Alina"
          />
        </label>

        <label>
          <span>Provider/source (optional)</span>
          <input
            maxLength={120}
            value={details.provider ?? ''}
            onChange={(event) => updateDetails({ provider: event.target.value || null })}
            placeholder="DMV, insurer, store"
          />
        </label>
      </div>

      <p className="renewal-safety-note">
        Do not store policy numbers, account numbers, passwords, or other sensitive details here.
      </p>

      {safetyError ? <p className="field-error">{safetyError}</p> : null}

      <div className="renewal-preview" aria-live="polite">
        <strong>{preview.primary}</strong>
        {preview.reminder ? <span>{preview.reminder}</span> : null}
        {preview.card ? <small>{preview.card}</small> : null}
      </div>
    </section>
  )
}

function getAddFormHeading(reminderType: ReminderInput['reminder_type']) {
  if (reminderType === 'birthday') {
    return 'Add Birthday'
  }

  if (reminderType === 'renewal') {
    return 'Add Renewal'
  }

  if (reminderType === 'maintenance') {
    return 'Add Maintenance'
  }

  return 'Add Reminder'
}

function getAddFormDescription(reminderType: ReminderInput['reminder_type']) {
  if (reminderType === 'birthday') {
    return 'Track a birthday and calculate age when details are known.'
  }

  if (reminderType === 'renewal') {
    return 'Set up the date LifeLedger should track.'
  }

  if (reminderType === 'maintenance') {
    return 'Set up a repeating maintenance schedule.'
  }

  return 'Choose a template or start from a blank reminder.'
}

function getRenewalItemPlaceholder(kind: RenewalDisplayKind) {
  if (kind === 'subscription') {
    return 'Netflix'
  }

  if (kind === 'free_trial') {
    return 'YouTube Premium'
  }

  if (kind === 'warranty') {
    return 'HVAC'
  }

  if (kind === 'document') {
    return 'Passport'
  }

  if (kind === 'review') {
    return 'Home insurance'
  }

  return "Alina's car tag"
}

function getDueDateFieldLabel(reminderType: ReminderInput['reminder_type']) {
  if (reminderType === 'birthday') {
    return 'Next birthday'
  }

  return 'Due date'
}

function getComputedRepeat(form: ReminderInput): ReminderInput['repeat'] {
  if (form.reminder_type === 'birthday') {
    return 'Yearly'
  }

  if (form.reminder_type === 'maintenance') {
    return getMaintenanceRepeat(form.maintenance_details ?? emptyMaintenanceDetails())
  }

  return form.repeat
}

function getRelevantRenewalFormDate(details: RenewalDetailsInput, fallbackDate: string) {
  return getRelevantRenewalDate(details, fallbackDate)
}

function withRelevantRenewalDate(details: RenewalDetailsInput, relevantDate: string): RenewalDetailsInput {
  if (details.renewal_kind === 'expiration') {
    return {
      ...details,
      renewal_date: null,
      expiration_date: relevantDate,
    }
  }

  return {
    ...details,
    renewal_date: relevantDate,
    expiration_date: null,
  }
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
