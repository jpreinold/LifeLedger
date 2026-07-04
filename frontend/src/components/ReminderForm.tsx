import { useEffect, useState } from 'react'
import type { Dispatch, FormEvent, SetStateAction } from 'react'
import { LayoutTemplate, Plus, X } from 'lucide-react'

import {
  priorityOptions,
  reminderCategories,
  repeatOptions,
  type ReminderInput,
} from '../types/reminder'
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

    setForm((current) => ({
      ...templateDraft.input,
      due_date: current.due_date || new Date().toISOString().slice(0, 10),
    }))
  }, [templateDraft])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const wasCreated = await onCreate({
      ...form,
      title: form.title.trim(),
      notes: form.notes?.trim() || null,
    })

    if (wasCreated) {
      setForm({ ...initialForm, due_date: new Date().toISOString().slice(0, 10) })
      onClose()
    }
  }

  if (!isOpen) {
    return null
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="sheet-dialog add-dialog"
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
