import { Cake, CheckCircle2, Clock3, Pencil, RefreshCcw, Trash2, Wrench, X } from 'lucide-react'

import { getMaintenanceAreaLabel, getMaintenanceDueDate } from '../lib/maintenanceUx'
import {
  formatLongDate,
  formatMonthDay,
  formatReminderDueLabel,
  formatReminderStatusLabel,
  formatRepeatLabel,
  getReminderTypeLabel,
} from '../lib/reminderDisplay'
import { formatReminderTiming } from '../lib/reminderSchedule'
import {
  getRelevantRenewalDate,
  getRenewalDateLabel,
  getRenewalDisplayKind,
  getRenewalKindLabel,
} from '../lib/renewalUx'
import { getSmartReminderLabel } from '../lib/smartReminderLabels'
import type { Reminder } from '../types/reminder'
import { getCategoryVisual } from './categoryVisuals'
import { SheetDrawer } from './SheetDrawer'

interface ReminderDetailDrawerProps {
  reminder: Reminder
  isAlertEligible: boolean
  onClose: () => void
  onComplete: (id: string) => Promise<void>
  onDismiss: (id: string) => Promise<void>
  onEdit: (reminder: Reminder) => void
  onRequestDelete: (reminder: Reminder) => void
  onSnooze: (id: string) => Promise<void>
}

interface DetailRow {
  label: string
  value: string | null | undefined
}

export function ReminderDetailDrawer({
  reminder,
  isAlertEligible,
  onClose,
  onComplete,
  onDismiss,
  onEdit,
  onRequestDelete,
  onSnooze,
}: ReminderDetailDrawerProps) {
  const { Icon, tone } = getCategoryVisual(reminder.category)
  const smartLabel = getSmartReminderLabel(reminder)
  const TypeIcon = getTypeIcon(reminder.reminder_type)
  const typeRows = getTypeSpecificRows(reminder)
  const note = getNotes(reminder)

  return (
    <SheetDrawer className="detail-dialog" isOpen labelledBy="reminder-detail-heading" onClose={onClose}>
      <div className="sheet-header detail-header">
        <div>
          <h2 id="reminder-detail-heading">Reminder details</h2>
          <p>Review the reminder before taking action.</p>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close reminder details">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="detail-body">
        <section className={`detail-hero tone-${tone}`} aria-labelledby="detail-title">
          <div className={`category-icon category-icon-large tone-${tone}`} aria-hidden="true">
            <Icon size={30} />
          </div>
          <div className="detail-hero-copy">
            <div className="card-chip-row">
              <span className="type-chip">{getReminderTypeLabel(reminder.reminder_type)}</span>
              <span className="category-chip">{reminder.category}</span>
            </div>
            <h3 id="detail-title">{reminder.title}</h3>
            {smartLabel ? (
              <p className="detail-smart-label">
                <TypeIcon size={15} aria-hidden="true" />
                {smartLabel}
              </p>
            ) : (
              <p>{formatReminderDueLabel(reminder)}</p>
            )}
          </div>
        </section>

        <DetailSection
          title="Details"
          rows={[
            { label: 'Title', value: reminder.title },
            { label: 'Type', value: getReminderTypeLabel(reminder.reminder_type) },
            { label: 'Category', value: reminder.category },
            { label: 'Priority', value: `${reminder.priority} priority` },
            ...typeRows,
          ]}
        />

        <DetailSection
          title="Schedule"
          rows={[
            { label: 'Status', value: formatReminderStatusLabel(reminder) },
            { label: 'Due date', value: formatLongDate(reminder.due_date) },
            { label: 'Reminder timing', value: formatReminderTiming(reminder) },
            { label: 'Repeat', value: formatRepeatLabel(reminder.repeat) ?? 'Does not repeat' },
          ]}
        />

        {note ? (
          <section className="detail-section" aria-labelledby="detail-notes-heading">
            <h3 id="detail-notes-heading">{reminder.reminder_type === 'maintenance' ? 'Notes & Instructions' : 'Notes'}</h3>
            <p className="detail-note">{note}</p>
          </section>
        ) : null}

        <section className="detail-actions" aria-label="Reminder actions">
          <button type="button" className="secondary-button" onClick={() => onEdit(reminder)}>
            <Pencil size={17} aria-hidden="true" />
            Edit
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={() => void onComplete(reminder.id)}
            disabled={reminder.completed}
          >
            <CheckCircle2 size={17} aria-hidden="true" />
            {reminder.completed ? 'Completed' : 'Complete'}
          </button>
          {isAlertEligible ? (
            <>
              <button type="button" className="small-outline-button" onClick={() => void onDismiss(reminder.id)}>
                Dismiss for now
              </button>
              <button type="button" className="small-outline-button" onClick={() => void onSnooze(reminder.id)}>
                <Clock3 size={14} aria-hidden="true" />
                Remind tomorrow
              </button>
            </>
          ) : null}
          <button type="button" className="text-danger-button detail-delete-button" onClick={() => onRequestDelete(reminder)}>
            <Trash2 size={16} aria-hidden="true" />
            Delete
          </button>
        </section>
      </div>
    </SheetDrawer>
  )
}

function DetailSection({ rows, title }: { rows: DetailRow[]; title: string }) {
  const visibleRows = rows.filter((row) => hasValue(row.value))

  if (visibleRows.length === 0) {
    return null
  }

  return (
    <section className="detail-section" aria-label={title}>
      <h3>{title}</h3>
      <dl className="detail-list">
        {visibleRows.map((row) => (
          <div className="detail-row" key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function getTypeSpecificRows(reminder: Reminder): DetailRow[] {
  if (reminder.reminder_type === 'birthday') {
    const details = reminder.birthday_details
    if (!details) {
      return []
    }

    return [
      { label: 'Person', value: details.person_name },
      { label: 'Birthday', value: formatBirthday(details.birth_month, details.birth_day) },
      { label: 'Birth year', value: details.birth_year?.toString() },
      { label: 'Turning', value: details.age_turning_next_birthday?.toString() },
      { label: 'Relationship', value: details.relationship },
    ]
  }

  if (reminder.reminder_type === 'renewal') {
    const details = reminder.renewal_details
    if (!details) {
      return []
    }

    const displayKind = getRenewalDisplayKind(details, { title: reminder.title, category: reminder.category })
    const relevantDate = getRelevantRenewalDate(details, reminder.due_date)

    return [
      { label: 'Item', value: details.item_name },
      { label: 'Renewal kind', value: getRenewalKindLabel(displayKind) },
      { label: getRenewalDateLabel(displayKind), value: relevantDate ? formatLongDate(relevantDate) : null },
      { label: 'Provider', value: details.provider },
      { label: 'Owner', value: details.owner_name },
      { label: 'Renewal window', value: details.renewal_window_days ? `${details.renewal_window_days} days` : null },
      { label: 'Review lead', value: details.review_lead_days ? `${details.review_lead_days} days` : null },
    ]
  }

  if (reminder.reminder_type === 'maintenance') {
    const details = reminder.maintenance_details
    if (!details) {
      return []
    }

    const nextDueDate = getMaintenanceDueDate(details, reminder.due_date)

    return [
      { label: 'Item', value: details.item_name },
      { label: 'Area', value: getMaintenanceAreaLabel(details.maintenance_area) },
      { label: 'Interval', value: formatInterval(details.interval_value, details.interval_unit) },
      { label: 'Last completed', value: details.last_completed_date ? formatLongDate(details.last_completed_date) : null },
      { label: 'Next due', value: nextDueDate ? formatLongDate(nextDueDate) : null },
    ]
  }

  return []
}

function getNotes(reminder: Reminder) {
  if (reminder.reminder_type === 'maintenance' && reminder.maintenance_details?.instructions) {
    return reminder.notes ? `${reminder.notes}\n\n${reminder.maintenance_details.instructions}` : reminder.maintenance_details.instructions
  }

  return reminder.notes
}

function getTypeIcon(type: Reminder['reminder_type']) {
  if (type === 'maintenance') {
    return Wrench
  }

  if (type === 'renewal') {
    return RefreshCcw
  }

  return Cake
}

function formatBirthday(month: number, day: number) {
  const value = `2000-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  return formatMonthDay(value)
}

function formatInterval(value: number | null, unit: string | null) {
  if (!value || !unit) {
    return null
  }

  const unitLabel = value === 1 ? unit.slice(0, -1) : unit
  return `Every ${value} ${unitLabel}`
}

function hasValue(value: string | null | undefined) {
  return value !== null && value !== undefined && value.trim().length > 0
}
