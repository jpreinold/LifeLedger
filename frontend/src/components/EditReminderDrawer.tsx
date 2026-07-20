import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Save, Trash2 } from 'lucide-react'

import type { Reminder, ReminderInput } from '../types/reminder'
import { buildReminderSubmitInput, isReminderReady, reminderToInput } from '../lib/reminderInput'
import { ReminderFields } from './ReminderForm'
import { SheetDrawer } from './SheetDrawer'

const drawerCloseMs = 220
const editReminderFormId = 'edit-reminder-form'

interface EditReminderDrawerProps {
  reminder: Reminder
  isSaving: boolean
  onCancel: () => void
  onDelete: (reminder: Reminder) => void
  onSave: (id: string, input: ReminderInput) => Promise<boolean>
}

export function EditReminderDrawer({ reminder, isSaving, onCancel, onDelete, onSave }: EditReminderDrawerProps) {
  const [form, setForm] = useState<ReminderInput>(() => reminderToInput(reminder))
  const [isDrawerOpen, setIsDrawerOpen] = useState(true)
  const isClosingRef = useRef(false)
  const closeTimerRef = useRef<number | null>(null)

  useEffect(() => {
    isClosingRef.current = false
    setIsDrawerOpen(true)
    setForm(reminderToInput(reminder))
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

  return (
    <SheetDrawer
      className="edit-dialog reminder-form-dialog"
      closeLabel="Close edit reminder"
      footer={(
        <div className="sheet-footer-actions reminder-form-footer">
          <button className="primary-button" type="submit" form={editReminderFormId} disabled={isSaving || !isReminderReady(form)}>
            <Save size={18} aria-hidden="true" />
            {isSaving ? 'Saving' : 'Save changes'}
          </button>
          <button type="button" className="text-danger-button" onClick={() => onDelete(reminder)}>
            <Trash2 size={16} aria-hidden="true" />
            Delete reminder
          </button>
        </div>
      )}
      isOpen={isDrawerOpen}
      labelledBy="edit-reminder-heading"
      onClose={requestCancel}
      subtitle={getEditDescription(form.reminder_type)}
      title={getEditHeading(form.reminder_type)}
    >
      <form id={editReminderFormId} className="reminder-form" onSubmit={handleSubmit}>
        <ReminderFields form={form} setForm={setForm} />
      </form>
    </SheetDrawer>
  )
}

function getEditHeading(reminderType: ReminderInput['reminder_type']) {
  if (reminderType === 'renewal') {
    return 'Edit Renewal'
  }

  if (reminderType === 'maintenance') {
    return 'Edit Maintenance'
  }

  if (reminderType === 'birthday') {
    return 'Edit Birthday'
  }

  return 'Edit Reminder'
}

function getEditDescription(reminderType: ReminderInput['reminder_type']) {
  if (reminderType === 'renewal') {
    return 'Update the tracked date, kind, and reminder timing.'
  }

  if (reminderType === 'maintenance') {
    return 'Update the maintenance schedule, next due date, and reminder timing.'
  }

  if (reminderType === 'birthday') {
    return 'Update birthday details and reminder timing.'
  }

  return 'Update details and keep the next due date clear.'
}
