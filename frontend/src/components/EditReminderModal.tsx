import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Save, X } from 'lucide-react'

import type { Reminder, ReminderInput } from '../types/reminder'
import { ReminderFields } from './ReminderForm'

interface EditReminderModalProps {
  reminder: Reminder
  isSaving: boolean
  onCancel: () => void
  onSave: (id: string, input: ReminderInput) => Promise<boolean>
}

export function EditReminderModal({ reminder, isSaving, onCancel, onSave }: EditReminderModalProps) {
  const [form, setForm] = useState<ReminderInput>(() => toReminderInput(reminder))

  useEffect(() => {
    setForm(toReminderInput(reminder))
  }, [reminder])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const wasSaved = await onSave(reminder.id, {
      ...form,
      title: form.title.trim(),
      notes: form.notes?.trim() || null,
    })

    if (wasSaved) {
      onCancel()
    }
  }

  return (
    <div className="modal-backdrop">
      <section
        className="edit-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-reminder-heading"
      >
        <div className="edit-dialog-header">
          <div>
            <h2 id="edit-reminder-heading">Edit Reminder</h2>
            <p>Update the reminder details and save when ready.</p>
          </div>
          <button type="button" className="secondary-button dialog-close-button" onClick={onCancel}>
            <X size={17} aria-hidden="true" />
            Cancel
          </button>
        </div>

        <form className="reminder-form edit-dialog-body" onSubmit={handleSubmit}>
          <ReminderFields form={form} setForm={setForm} />

          <div className="modal-actions">
            <button type="button" className="secondary-button" onClick={onCancel}>
              Cancel
            </button>
            <button className="primary-button" type="submit" disabled={isSaving || !form.title.trim()}>
              <Save size={18} aria-hidden="true" />
              {isSaving ? 'Saving' : 'Save changes'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}

function toReminderInput(reminder: Reminder): ReminderInput {
  return {
    title: reminder.title,
    category: reminder.category,
    due_date: reminder.due_date,
    repeat: reminder.repeat,
    priority: reminder.priority,
    notes: reminder.notes,
  }
}
