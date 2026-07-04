import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Save, Trash2, X } from 'lucide-react'

import type { Reminder, ReminderInput } from '../types/reminder'
import { buildReminderInputWithDefaultTiming } from '../lib/reminderSchedule'
import { getCategoryVisual } from './categoryVisuals'
import { ReminderFields } from './ReminderForm'

interface EditReminderModalProps {
  reminder: Reminder
  isSaving: boolean
  onCancel: () => void
  onDelete: (id: string) => Promise<void>
  onSave: (id: string, input: ReminderInput) => Promise<boolean>
}

export function EditReminderModal({ reminder, isSaving, onCancel, onDelete, onSave }: EditReminderModalProps) {
  const [form, setForm] = useState<ReminderInput>(() => toReminderInput(reminder))
  const { Icon, tone } = getCategoryVisual(form.category)

  useEffect(() => {
    setForm(toReminderInput(reminder))
  }, [reminder])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onCancel()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onCancel])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const wasSaved = await onSave(
      reminder.id,
      buildReminderInputWithDefaultTiming({
        ...form,
        title: form.title.trim(),
        notes: form.notes?.trim() || null,
      }),
    )

    if (wasSaved) {
      onCancel()
    }
  }

  async function handleDelete() {
    await onDelete(reminder.id)
    onCancel()
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onCancel}>
      <section
        className="sheet-dialog edit-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-reminder-heading"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sheet-header">
          <div>
            <h2 id="edit-reminder-heading">Edit Reminder</h2>
            <p>Update details and keep the next due date clear.</p>
          </div>
          <button type="button" className="icon-button ghost-icon-button" onClick={onCancel} aria-label="Close edit reminder">
            <X size={19} aria-hidden="true" />
          </button>
        </div>

        <div className="sheet-icon-lockup">
          <div className={`category-icon category-icon-large tone-${tone}`} aria-hidden="true">
            <Icon size={30} />
          </div>
        </div>

        <form className="reminder-form sheet-body" onSubmit={handleSubmit}>
          <ReminderFields form={form} setForm={setForm} />

          <div className="modal-actions">
            <button className="primary-button" type="submit" disabled={isSaving || !form.title.trim()}>
              <Save size={18} aria-hidden="true" />
              {isSaving ? 'Saving' : 'Save changes'}
            </button>
            <button type="button" className="text-danger-button" onClick={() => void handleDelete()}>
              <Trash2 size={16} aria-hidden="true" />
              Delete reminder
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}

function toReminderInput(reminder: Reminder): ReminderInput {
  return buildReminderInputWithDefaultTiming({
    title: reminder.title,
    category: reminder.category,
    due_date: reminder.due_date,
    repeat: reminder.repeat,
    priority: reminder.priority,
    notes: reminder.notes,
    reminder_lead_value: reminder.reminder_lead_value,
    reminder_lead_unit: reminder.reminder_lead_unit,
    reminder_time: reminder.reminder_time,
  })
}
