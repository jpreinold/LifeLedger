import {
  AlertTriangle,
  CalendarCheck,
  CalendarClock,
  CheckCircle2,
  Edit3,
  LayoutTemplate,
  ListChecks,
  Plus,
} from 'lucide-react'

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
}

export function Dashboard({
  reminders,
  isLoading = false,
  variant = 'summary',
  onComplete,
  onEdit,
  onAddReminder,
  onBrowseTemplates,
}: DashboardProps) {
  const activeCount = reminders.filter((reminder) => !reminder.completed).length
  const overdueCount = reminders.filter((reminder) => reminder.status === 'Overdue').length
  const dueTodayCount = reminders.filter((reminder) => reminder.status === 'Due today').length
  const dueThisWeekCount = reminders.filter((reminder) =>
    ['Due today', 'Due this week'].includes(reminder.status),
  ).length

  const stats = [
    { label: 'All active', value: activeCount, icon: ListChecks, tone: 'blue' },
    { label: 'Overdue', value: overdueCount, icon: AlertTriangle, tone: 'red' },
    { label: 'Due today', value: dueTodayCount, icon: CalendarClock, tone: 'orange' },
    { label: 'Due this week', value: dueThisWeekCount, icon: CalendarCheck, tone: 'green' },
  ]
  const attentionItems = getNeedsAttention(reminders).slice(0, 5)

  return (
    <>
      <section className="dashboard-summary-card" aria-label="Reminder summary">
        {stats.map((stat) => {
          const Icon = stat.icon

          return (
            <article className={`stat-item stat-item-${stat.tone}`} key={stat.label}>
              <Icon size={20} aria-hidden="true" />
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
            </article>
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
    return `Window opened ${formatShortDate(item.reminderDate)}. Due ${formatShortDate(item.reminder.due_date)}`
  }

  if (item.reason === 'Overdue') {
    return `Due ${formatShortDate(item.reminder.due_date)}`
  }

  if (item.reason === 'Due today') {
    return `Due today at ${formatShortDate(item.reminder.due_date)}`
  }

  return `Due ${formatShortDate(item.reminder.due_date)}`
}

function formatShortDate(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(new Date(year, month - 1, day))
}
