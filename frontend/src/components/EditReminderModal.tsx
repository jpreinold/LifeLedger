import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Save, Trash2, X } from 'lucide-react'

import type { Reminder, ReminderInput } from '../types/reminder'
import { buildReminderSubmitInput, isReminderReady } from '../lib/reminderInput'
import { buildReminderInputWithDefaultTiming } from '../lib/reminderSchedule'
import { getCategoryVisual } from './categoryVisuals'
import { ReminderFields } from './ReminderForm'
import { SheetDrawer } from './SheetDrawer'

const drawerCloseMs = 220

interface EditReminderModalProps {
  reminder: Reminder
  isSaving: boolean
  onCancel: () => void
  onDelete: (id: string) => Promise<void>
  onSave: (id: string, input: ReminderInput) => Promise<boolean>
}

export function EditReminderModal({ reminder, isSaving, onCancel, onDelete, onSave }: EditReminderModalProps) {
  const [form, setForm] = useState<ReminderInput>(() => toReminderInput(reminder))
  const [isDrawerOpen, setIsDrawerOpen] = useState(true)
  const isClosingRef = useRef(false)
  const closeTimerRef = useRef<number | null>(null)
  const { Icon, tone } = getCategoryVisual(form.category)

  useEffect(() => {
    isClosingRef.current = false
    setIsDrawerOpen(true)
    setForm(toReminderInput(reminder))
  }, [reminder])

  useEffect(() => {
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current)
      }
    }
  }, [])

  const requestCancel = useCallback(() => {
    if (isClosingRef.current) {
      return
    }

    isClosingRef.current = true
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onCancel()
    }, drawerCloseMs)
  }, [onCancel])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const wasSaved = await onSave(reminder.id, buildReminderSubmitInput(form))

    if (wasSaved) {
      requestCancel()
    }
  }

  async function handleDelete() {
    await onDelete(reminder.id)
    requestCancel()
  }

  return (
    <SheetDrawer className="edit-dialog" isOpen={isDrawerOpen} labelledBy="edit-reminder-heading" onClose={requestCancel}>
        <div className="sheet-header">
          <div>
            <h2 id="edit-reminder-heading">Edit Reminder</h2>
            <p>Update details and keep the next due date clear.</p>
          </div>
          <button type="button" className="icon-button ghost-icon-button" onClick={requestCancel} aria-label="Close edit reminder">
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
            <button className="primary-button" type="submit" disabled={isSaving || !isReminderReady(form)}>
              <Save size={18} aria-hidden="true" />
              {isSaving ? 'Saving' : 'Save changes'}
            </button>
            <button type="button" className="text-danger-button" onClick={() => void handleDelete()}>
              <Trash2 size={16} aria-hidden="true" />
              Delete reminder
            </button>
          </div>
        </form>
    </SheetDrawer>
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
    reminder_type: reminder.reminder_type ?? 'generic',
    birthday_details: reminder.birthday_details
      ? {
          person_name: reminder.birthday_details.person_name,
          birth_month: reminder.birthday_details.birth_month,
          birth_day: reminder.birthday_details.birth_day,
          birth_year: reminder.birthday_details.birth_year,
          age_turning_next_birthday: reminder.birthday_details.age_turning_next_birthday,
          inferred_birth_year: reminder.birthday_details.inferred_birth_year,
          relationship: reminder.birthday_details.relationship,
        }
      : null,
    renewal_details: reminder.renewal_details
      ? {
          item_name: reminder.renewal_details.item_name,
          renewal_kind: reminder.renewal_details.renewal_kind,
          owner_name: reminder.renewal_details.owner_name,
          provider: reminder.renewal_details.provider,
          renewal_date: reminder.renewal_details.renewal_date,
          expiration_date: reminder.renewal_details.expiration_date,
          renewal_window_days: reminder.renewal_details.renewal_window_days,
          review_lead_days: reminder.renewal_details.review_lead_days,
          frequency: reminder.renewal_details.frequency,
        }
      : null,
  })
}
