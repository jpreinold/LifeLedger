import {
  ChevronRight,
  FileText,
  Gift,
  ListChecks,
  Plus,
  RefreshCcw,
  Sun,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { formatReminderDueLabel, parseDateOnly, startOfDay } from '../lib/reminderDisplay'
import { toAttentionReminder, type AttentionReminder } from '../lib/reminderSchedule'
import { getSmartReminderLabel } from '../lib/smartReminderLabels'
import type { Reminder, ReminderAlert, ReminderType } from '../types/reminder'
import { getCategoryVisual } from './categoryVisuals'

interface HomeDashboardProps {
  reminders: Reminder[]
  alerts: ReminderAlert[]
  isLoading: boolean
  userName?: string | null
  onAddReminder: () => void
  onBrowseTemplates: () => void
  onViewReminders: () => void
  onViewAlerts: () => void
  onViewRecords: () => void
  onEditReminder: (reminder: Reminder) => void
}

interface OverviewTileData {
  label: string
  value: string
  sublabel: string
  icon: LucideIcon
  tone: string
  disabled?: boolean
  onClick?: () => void
}

const maxAttentionItems = 3
const maxUpcomingItems = 4

export function HomeDashboard({
  reminders,
  alerts,
  isLoading,
  userName,
  onAddReminder,
  onBrowseTemplates,
  onViewReminders,
  onViewAlerts,
  onEditReminder,
}: HomeDashboardProps) {
  const activeReminders = reminders.filter((reminder) => !reminder.completed)
  const genericReminders = activeReminders.filter((reminder) => reminder.reminder_type === 'generic')
  const birthdayReminders = activeReminders.filter((reminder) => reminder.reminder_type === 'birthday')
  const renewalReminders = activeReminders.filter((reminder) => reminder.reminder_type === 'renewal')
  const maintenanceReminders = activeReminders.filter((reminder) => reminder.reminder_type === 'maintenance')
  const attentionItems = alerts.map(toAttentionReminder)
  const visibleAttentionItems = attentionItems.slice(0, maxAttentionItems)
  const upcomingItems = getUpcomingReminders(activeReminders).slice(0, maxUpcomingItems)
  const overviewTiles: OverviewTileData[] = [
    {
      label: 'Reminders',
      value: String(genericReminders.length),
      sublabel: formatOverviewSublabel(countAlertsByType(alerts, 'generic'), 'need attention'),
      icon: ListChecks,
      tone: 'blue',
      onClick: onViewReminders,
    },
    {
      label: 'Birthdays',
      value: String(birthdayReminders.length),
      sublabel: formatOverviewSublabel(countAlertsByType(alerts, 'birthday'), 'coming up'),
      icon: Gift,
      tone: 'purple',
      onClick: onViewReminders,
    },
    {
      label: 'Renewals',
      value: String(renewalReminders.length),
      sublabel: formatOverviewSublabel(countAlertsByType(alerts, 'renewal'), 'need attention'),
      icon: RefreshCcw,
      tone: 'orange',
      onClick: onViewReminders,
    },
    {
      label: 'Maintenance',
      value: String(maintenanceReminders.length),
      sublabel: formatOverviewSublabel(countAlertsByType(alerts, 'maintenance'), 'due'),
      icon: Wrench,
      tone: 'teal',
      onClick: onViewReminders,
    },
  ]

  return (
    <div className="home-dashboard" aria-label="Home dashboard">
      <section className="home-hero-card">
        <div className="home-hero-icon" aria-hidden="true">
          <Sun size={25} />
        </div>
        <div className="home-hero-copy">
          <h2>{getGreeting(userName)}</h2>
          <p>{formatAttentionSummary(attentionItems.length)}</p>
        </div>
        <button type="button" className="home-hero-link" onClick={onViewAlerts} aria-label="View alerts">
          <ChevronRight size={21} aria-hidden="true" />
        </button>
      </section>

      <section className="quick-actions-card" aria-label="Quick actions">
        <QuickAction label="Add reminder" icon={Plus} tone="blue" onClick={onAddReminder} />
        <QuickAction label="Browse templates" icon={ListChecks} tone="blue-soft" onClick={onBrowseTemplates} />
        <QuickAction label="Add record" icon={FileText} tone="green" disabled />
        <QuickAction label="Review renewals" icon={RefreshCcw} tone="orange" onClick={onViewReminders} />
      </section>

      <section className="home-card" aria-labelledby="needs-attention-heading">
        <div className="home-card-header">
          <h2 id="needs-attention-heading">Needs attention</h2>
          {attentionItems.length > 0 ? <span className="count-badge count-badge-danger">{attentionItems.length}</span> : null}
        </div>

        {isLoading ? <p className="home-empty-state">Loading reminders...</p> : null}

        {!isLoading && visibleAttentionItems.length === 0 ? (
          <p className="home-empty-state">Nothing needs attention right now.</p>
        ) : null}

        {!isLoading && visibleAttentionItems.length > 0 ? (
          <>
            <div className="home-list">
              {visibleAttentionItems.map((item) => (
                <AttentionRow item={item} key={item.reminder.id} onClick={() => onEditReminder(item.reminder)} />
              ))}
            </div>
            {attentionItems.length > maxAttentionItems ? (
              <button type="button" className="home-card-link" onClick={onViewAlerts}>
                View all
              </button>
            ) : null}
          </>
        ) : null}
      </section>

      <section className="home-card" aria-labelledby="upcoming-heading">
        <div className="home-card-header">
          <h2 id="upcoming-heading">Upcoming this month</h2>
          {upcomingItems.length > 0 ? <span className="count-badge">{upcomingItems.length}</span> : null}
        </div>

        {isLoading ? <p className="home-empty-state">Loading reminders...</p> : null}

        {!isLoading && upcomingItems.length === 0 ? (
          <p className="home-empty-state">No upcoming reminders this month.</p>
        ) : null}

        {!isLoading && upcomingItems.length > 0 ? (
          <>
            <div className="home-list">
              {upcomingItems.map((reminder) => (
                <UpcomingRow reminder={reminder} key={reminder.id} onClick={() => onEditReminder(reminder)} />
              ))}
            </div>
            <button type="button" className="home-card-link" onClick={onViewReminders}>
              View reminders
            </button>
          </>
        ) : null}
      </section>

      <section className="home-card" aria-labelledby="overview-heading">
        <div className="home-card-header">
          <h2 id="overview-heading">Smart reminder overview</h2>
        </div>

        <div className="overview-grid overview-grid-smart">
          {overviewTiles.map((tile) => (
            <OverviewTile tile={tile} key={tile.label} />
          ))}
        </div>
      </section>
    </div>
  )
}

function countAlertsByType(alerts: ReminderAlert[], type: ReminderType) {
  return alerts.filter((alert) => alert.reminder_type === type).length
}
function QuickAction({
  label,
  icon: Icon,
  tone,
  disabled = false,
  onClick,
}: {
  label: string
  icon: LucideIcon
  tone: string
  disabled?: boolean
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      className={`quick-action quick-action-${tone}`}
      disabled={disabled}
      onClick={onClick}
      aria-label={disabled ? `${label} coming soon` : label}
    >
      <span className="quick-action-icon" aria-hidden="true">
        <Icon size={22} />
      </span>
      <span>{label}</span>
      {disabled ? <small>Coming soon</small> : null}
    </button>
  )
}

function AttentionRow({ item, onClick }: { item: AttentionReminder; onClick: () => void }) {
  const { reminder } = item
  const { Icon, tone } = getCategoryVisual(reminder.category)
  const smartLabel = getSmartReminderLabel(reminder)
  const detail = smartLabel ?? formatAttentionStatus(item)

  return (
    <button type="button" className="home-list-row" onClick={onClick}>
      <span className={`home-row-icon tone-${tone}`} aria-hidden="true">
        <Icon size={19} />
      </span>
      <span className="home-row-copy">
        <strong>{reminder.title}</strong>
        <span>
          {reminder.category}
          {' \u2022 '}
          <em className={`attention-text attention-text-${getAttentionTone(item)}`}>{detail}</em>
        </span>
      </span>
      <ChevronRight size={18} aria-hidden="true" className="home-row-chevron" />
    </button>
  )
}

function UpcomingRow({ reminder, onClick }: { reminder: Reminder; onClick: () => void }) {
  const { Icon, tone } = getCategoryVisual(reminder.category)
  const smartLabel = getSmartReminderLabel(reminder)
  const detail = smartLabel ?? formatReminderDueLabel(reminder, { includeDate: false })

  return (
    <button type="button" className="home-list-row" onClick={onClick}>
      <span className={`home-row-icon tone-${tone}`} aria-hidden="true">
        <Icon size={19} />
      </span>
      <span className="home-row-copy">
        <strong>{reminder.title}</strong>
        <span>{reminder.category} {'\u2022'} {detail}</span>
      </span>
      <ChevronRight size={18} aria-hidden="true" className="home-row-chevron" />
    </button>
  )
}

function OverviewTile({ tile }: { tile: OverviewTileData }) {
  const { icon: Icon } = tile

  return (
    <button
      type="button"
      className={`overview-tile overview-tile-${tile.tone}`}
      disabled={tile.disabled}
      onClick={tile.onClick}
    >
      <span className="overview-tile-icon" aria-hidden="true">
        <Icon size={19} />
      </span>
      <span className="overview-tile-copy">
        <span>{tile.label}</span>
        <strong>{tile.value}</strong>
        <small>{tile.sublabel}</small>
      </span>
    </button>
  )
}

function getGreeting(userName?: string | null) {
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return userName ? `${greeting}, ${userName}` : greeting
}

function formatAttentionSummary(count: number) {
  return `${count} ${count === 1 ? 'item needs' : 'items need'} attention today.`
}

function formatOverviewSublabel(count: number, label: string) {
  return count === 0 ? 'All clear' : `${count} ${label}`
}

function formatAttentionStatus(item: AttentionReminder) {
  if (item.reason === 'Reminder window') {
    return `Reminder started \u2022 ${formatReminderDueLabel(item.reminder, { includeDate: false })}`
  }

  return formatReminderDueLabel(item.reminder, { includeDate: false })
}

function getAttentionTone(item: AttentionReminder) {
  if (item.reason === 'Overdue') {
    return 'danger'
  }

  if (item.reason === 'Due today') {
    return 'warning'
  }

  return 'primary'
}

function getUpcomingReminders(reminders: Reminder[]) {
  const today = startOfDay(new Date())
  const thirtyDaysFromNow = addDays(today, 30)

  return reminders
    .filter((reminder) => {
      const dueDate = parseDateOnly(reminder.due_date)
      const isCurrentMonth = dueDate.getFullYear() === today.getFullYear() && dueDate.getMonth() === today.getMonth()

      return dueDate >= today && (isCurrentMonth || dueDate <= thirtyDaysFromNow)
    })
    .sort((left, right) => {
      const dueDifference = parseDateOnly(left.due_date).getTime() - parseDateOnly(right.due_date).getTime()

      if (dueDifference !== 0) {
        return dueDifference
      }

      return left.title.localeCompare(right.title)
    })
}

function addDays(value: Date, days: number) {
  const next = new Date(value)
  next.setDate(next.getDate() + days)
  return startOfDay(next)
}
