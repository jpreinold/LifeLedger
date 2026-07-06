import {
  AlertTriangle,
  CalendarCheck,
  CalendarClock,
  Check,
  CheckCircle2,
  Edit3,
  LayoutTemplate,
  ListChecks,
  Plus,
} from 'lucide-react'

import {
  formatReminderDueLabel,
  matchesReminderStatusFilter,
  matchesReminderTypeFilter,
  type ReminderStatusFilter,
  type ReminderTypeFilter,
} from '../lib/reminderDisplay'
import { getNeedsAttention, type AttentionReminder } from '../lib/reminderSchedule'
import { getSmartReminderLabel } from '../lib/smartReminderLabels'
import type { Reminder } from '../types/reminder'

interface DashboardProps {
  reminders: Reminder[]
  isLoading?: boolean
  variant?: 'summary' | 'full'
  onComplete?: (id: string) => Promise<void>
  onEdit?: (reminder: Reminder) => void
  onAddReminder?: () => void
  onBrowseTemplates?: () => void
  activeStatusFilter?: ReminderStatusFilter
  activeTypeFilter?: ReminderTypeFilter
  onStatusFilterChange?: (filter: ReminderStatusFilter) => void
}

export function Dashboard({
  reminders,
  isLoading = false,
  variant = 'summary',
  onComplete,
  onEdit,
  onAddReminder,
  onBrowseTemplates,
  activeStatusFilter = 'active',
  activeTypeFilter = 'all',
  onStatusFilterChange,
}: DashboardProps) {
  const scopedReminders = reminders.filter((reminder) => matchesReminderTypeFilter(reminder, activeTypeFilter))
  const stats: Array<{ id: ReminderStatusFilter; label: string; value: number; icon: typeof ListChecks; tone: string }> = [
    {
      id: 'active',
      label: 'All active',
      value: scopedReminders.filter((reminder) => matchesReminderStatusFilter(reminder, 'active')).length,
      icon: ListChecks,
      tone: 'blue',
    },
    {
      id: 'overdue',
      label: 'Overdue',
      value: scopedReminders.filter((reminder) => matchesReminderStatusFilter(reminder, 'overdue')).length,
      icon: AlertTriangle,
      tone: 'red',
    },
    {
      id: 'today',
      label: 'Due today',
      value: scopedReminders.filter((reminder) => matchesReminderStatusFilter(reminder, 'today')).length,
      icon: CalendarClock,
      tone: 'orange',
    },
    {
      id: 'month',
      label: 'Due this month',
      value: scopedReminders.filter((reminder) => matchesReminderStatusFilter(reminder, 'month')).length,
      icon: CalendarCheck,
      tone: 'green',
    },
  ]
  const attentionItems = getNeedsAttention(reminders).slice(0, 5)

  return (
    <>
      <section className="dashboard-summary-card" aria-label="Reminder summary">
        {stats.map((stat) => {
          const Icon = stat.icon

          const isSelected = activeStatusFilter === stat.id

          return (
            <button
              type="button"
              className={`stat-item stat-item-${stat.tone} ${isSelected ? 'stat-item-selected' : ''}`}
              key={stat.id}
              onClick={() => onStatusFilterChange?.(stat.id)}
              aria-pressed={isSelected}
            >
              {isSelected ? (
                <span className="stat-selected-indicator" aria-hidden="true">
                  <Check size={12} />
                </span>
              ) : null}
              <Icon size={20} aria-hidden="true" />
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
            </button>
          )
        })}
      </section>

      {variant === 'full' ? (
        <section className="radar-panel" aria-labelledby="radar-heading">
          <div className="section-heading radar-heading">
            <div>
              <h2 id="radar-heading">On your radar</h2>
              <span>{isLoading ? 'Loading' : `${attentionItems.length} need attention`}</span>
            </div>
          </div>

          {isLoading ? <p className="empty-state">Loading reminders...</p> : null}

          {!isLoading && attentionItems.length === 0 ? (
            <div className="empty-state empty-state-card radar-empty-state">
              <p>Nothing needs attention right now.</p>
              {reminders.length === 0 ? (
                <div className="empty-state-actions">
                  {onBrowseTemplates ? (
                    <button type="button" className="secondary-button empty-template-button" onClick={onBrowseTemplates}>
                      <LayoutTemplate size={17} aria-hidden="true" />
                      Browse templates
                    </button>
                  ) : null}
                  {onAddReminder ? (
                    <button type="button" className="primary-button empty-add-button" onClick={onAddReminder}>
                      <Plus size={17} aria-hidden="true" />
                      Add reminder
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}

          {!isLoading && attentionItems.length > 0 ? (
            <div className="radar-list">
              {attentionItems.map((item) => (
                <RadarItem
                  item={item}
                  key={item.reminder.id}
                  onComplete={onComplete}
                  onEdit={onEdit}
                />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
    </>
  )
}

function RadarItem({
  item,
  onComplete,
  onEdit,
}: {
  item: AttentionReminder
  onComplete?: (id: string) => Promise<void>
  onEdit?: (reminder: Reminder) => void
}) {
  const { reminder } = item
  const Icon = getAttentionIcon(item)

  return (
    <article className={`radar-item radar-item-${getAttentionTone(item)}`}>
      <div className="radar-item-icon" aria-hidden="true">
        <Icon size={19} />
      </div>

      <div className="radar-item-copy">
        <span>{getAttentionLabel(item)}</span>
        <h3>{reminder.title}</h3>
        <p>{getRadarDueLabel(item)}</p>
      </div>

      <div className="radar-item-actions">
        {onComplete ? (
          <button
            type="button"
            className="icon-button radar-action-button"
            onClick={() => void onComplete(reminder.id)}
            aria-label={`Complete ${reminder.title}`}
          >
            <CheckCircle2 size={18} aria-hidden="true" />
          </button>
        ) : null}
        {onEdit ? (
          <button
            type="button"
            className="icon-button radar-action-button"
            onClick={() => onEdit(reminder)}
            aria-label={`Edit ${reminder.title}`}
          >
            <Edit3 size={17} aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </article>
  )
}

function getAttentionIcon(item: AttentionReminder) {
  if (item.reason === 'Overdue') {
    return AlertTriangle
  }

  if (item.reason === 'Due today') {
    return CalendarClock
  }

  return CalendarCheck
}

function getAttentionTone(item: AttentionReminder) {
  if (item.reason === 'Overdue') {
    return 'overdue'
  }

  if (item.reason === 'Due today') {
    return 'today'
  }

  if (item.reason === 'Reminder window') {
    return 'window'
  }

  return 'week'
}

function getAttentionLabel(item: AttentionReminder) {
  if (item.reason === 'Reminder window') {
    return 'Reminder window started'
  }

  return item.reason
}

function getRadarDueLabel(item: AttentionReminder) {
  const smartLabel = getSmartReminderLabel(item.reminder)
  if (smartLabel) {
    return smartLabel
  }

  if (item.reason === 'Reminder window' && item.reminderDate) {
    return `Reminder started. ${formatReminderDueLabel(item.reminder, { includeDate: false })}`
  }

  return formatReminderDueLabel(item.reminder, { includeDate: false })
}
