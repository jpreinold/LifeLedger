import { useState } from 'react'
import type { FormEvent } from 'react'
import { Plus } from 'lucide-react'

import {
  priorityOptions,
  reminderCategories,
  repeatOptions,
  type ReminderInput,
} from '../types/reminder'

interface ReminderFormProps {
  isSaving: boolean
  onCreate: (input: ReminderInput) => Promise<boolean>
}

const today = new Date().toISOString().slice(0, 10)

const initialForm: ReminderInput = {
  title: '',
  category: 'Other',
  due_date: today,
  repeat: 'None',
  priority: 'Medium',
  notes: null,
}

export function ReminderForm({ isSaving, onCreate }: ReminderFormProps) {
  const [form, setForm] = useState<ReminderInput>(initialForm)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const wasCreated = await onCreate({
      ...form,
      title: form.title.trim(),
      notes: form.notes?.trim() || null,
    })

    if (wasCreated) {
      setForm({ ...initialForm, due_date: new Date().toISOString().slice(0, 10) })
    }
  }

  return (
    <section className="form-panel" aria-labelledby="add-reminder-heading">
      <h2 id="add-reminder-heading">Add Reminder</h2>

      <form className="reminder-form" onSubmit={handleSubmit}>
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

        <button className="primary-button" type="submit" disabled={isSaving || !form.title.trim()}>
          <Plus size={18} aria-hidden="true" />
          {isSaving ? 'Saving' : 'Add reminder'}
        </button>
      </form>
    </section>
  )
}
