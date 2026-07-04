import { useEffect, useRef, useState } from 'react'
import type { Dispatch, FormEvent, SetStateAction } from 'react'
import { Bell, LayoutTemplate, Plus, X } from 'lucide-react'

import {
  priorityOptions,
  reminderCategories,
  reminderLeadUnits,
  repeatOptions,
  type ReminderInput,
} from '../types/reminder'
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

interface ReminderFormProps {
  isOpen: boolean
  isSaving: boolean
  onCreate: (input: ReminderInput) => Promise<boolean>
  onBrowseTemplates: () => void
  onClose: () => void
  templateDraft: TemplateDraft | null
}

const today = new Date().toISOString().slice(0, 10)
const drawerCloseMs = 220

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
  const [isClosing, setIsClosing] = useState(false)
  const closeTimerRef = useRef<number | null>(null)
  const { Icon, tone } = getCategoryVisual(form.category)

  useEffect(() => {
    if (isOpen) {
      setIsClosing(false)
    }

    if (isOpen && !templateDraft) {
      setForm({ ...initialForm, due_date: new Date().toISOString().slice(0, 10) })
    }
  }, [isOpen, templateDraft])

  useEffect(() => {
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current)
      }
    }
  }, [])

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

  function requestClose() {
    if (isClosing) {
      return
    }

    setIsClosing(true)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onClose()
    }, drawerCloseMs)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const wasCreated = await onCreate(
      buildReminderInputWithDefaultTiming({
        ...form,
        title: form.title.trim(),
        notes: form.notes?.trim() || null,
      }),
    )

    if (wasCreated) {
      setForm({ ...initialForm, due_date: new Date().toISOString().slice(0, 10) })
      requestClose()
    }
  }

  if (!isOpen) {
    return null
  }

  return (
    <div
      className={`modal-backdrop ${isClosing ? 'modal-backdrop-closing' : ''}`}
      role="presentation"
      onMouseDown={requestClose}
    >
      <section
        className={`sheet-dialog add-dialog ${isClosing ? 'sheet-dialog-closing' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-reminder-heading"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sheet-header">
          <div>
            <h2 id="add-reminder-heading">Add Reminder</h2>
            <p>Choose a template or start from a blank reminder.</p>
          </div>
          <button type="button" className="icon-button ghost-icon-button" onClick={requestClose} aria-label="Close add reminder">
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

          <button className="primary-button" type="submit" disabled={isSaving || !form.title.trim()}>
            <Plus size={18} aria-hidden="true" />
            {isSaving ? 'Saving' : 'Add reminder'}
          </button>
        </form>
      </section>
    </div>
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
          <span>Due date</span>
          <input
            required
            type="date"
            value={form.due_date}
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
