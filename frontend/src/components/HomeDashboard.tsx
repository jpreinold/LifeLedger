import {
  ChevronRight,
  CreditCard,
  FileText,
  Gift,
  ListChecks,
  Plus,
  RefreshCcw,
  Sun,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { getNeedsAttention, type AttentionReminder } from '../lib/reminderSchedule'
import type { Reminder } from '../types/reminder'
import { getCategoryVisual } from './categoryVisuals'

interface HomeDashboardProps {
  reminders: Reminder[]
  isLoading: boolean
  userName?: string | null
  onAddReminder: () => void
  onBrowseTemplates: () => void
  onViewReminders: () => void
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
  isLoading,
  userName,
  onAddReminder,
  onBrowseTemplates,
  onViewReminders,
  onViewRecords,
  onEditReminder,
}: HomeDashboardProps) {
  const activeReminders = reminders.filter((reminder) => !reminder.completed)
  const attentionItems = getNeedsAttention(reminders)
  const visibleAttentionItems = attentionItems.slice(0, maxAttentionItems)
  const upcomingItems = getUpcomingReminders(activeReminders).slice(0, maxUpcomingItems)
  const renewalReminders = activeReminders.filter(isRenewalReminder)
  const overviewTiles: OverviewTileData[] = [
    {
      label: 'Reminders',
      value: String(activeReminders.length),
      sublabel: `${attentionItems.length} due`,
      icon: ListChecks,
      tone: 'blue',
      onClick: onViewReminders,
    },
    {
      label: 'Records',
      value: 'Soon',
      sublabel: 'Coming soon',
      icon: FileText,
      tone: 'green',
      onClick: onViewRecords,
    },
    {
      label: 'Renewals',
      value: renewalReminders.length > 0 ? String(renewalReminders.length) : 'Soon',
      sublabel: renewalReminders.length > 0 ? `${getNeedsAttention(renewalReminders).length} due` : 'Coming soon',
      icon: RefreshCcw,
      tone: 'orange',
      disabled: renewalReminders.length === 0,
      onClick: onViewReminders,
    },
    {
      label: 'Maintenance',
      value: String(countByCategory(activeReminders, 'Home')),
      sublabel: `${getNeedsAttention(activeReminders.filter((reminder) => reminder.category === 'Home')).length} due`,
      icon: Wrench,
      tone: 'teal',
      onClick: onViewReminders,
    },
    {
      label: 'Family dates',
      value: String(countByCategory(activeReminders, 'Family')),
      sublabel: `${getNeedsAttention(activeReminders.filter((reminder) => reminder.category === 'Family')).length} upcoming`,
      icon: Gift,
      tone: 'purple',
      onClick: onViewReminders,
    },
    {
      label: 'Subscriptions',
      value: String(countByCategory(activeReminders, 'Subscriptions')),
      sublabel: `${getNeedsAttention(activeReminders.filter((reminder) => reminder.category === 'Subscriptions')).length} due`,
      icon: CreditCard,
      tone: 'cyan',
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
        <button type="button" className="home-hero-link" onClick={onViewReminders} aria-label="View reminders">
          <ChevronRight size={21} aria-hidden="true" />
        </button>
      </section>

      <section className="quick-actions-card" aria-label="Quick actions">
        <QuickAction label="Add reminder" icon={Plus} tone="blue" onClick={onAddReminder} />
        <QuickAction label="Browse templates" icon={ListChecks} tone="blue-soft" onClick={onBrowseTemplates} />
        <QuickAction label="Add record" icon={FileText} tone="green" disabled />
        <QuickAction label="Review renewals" icon={RefreshCcw} tone="orange" disabled />
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
          <div className="home-list">
            {visibleAttentionItems.map((item) => (
              <AttentionRow item={item} key={item.reminder.id} onClick={() => onEditReminder(item.reminder)} />
            ))}
          </div>
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
          <h2 id="overview-heading">Life admin overview</h2>
        </div>

        <div className="overview-grid">
          {overviewTiles.map((tile) => (
            <OverviewTile tile={tile} key={tile.label} />
          ))}
        </div>
      </section>
    </div>
  )
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

  return (
    <button type="button" className="home-list-row" onClick={onClick}>
      <span className={`home-row-icon tone-${tone}`} aria-hidden="true">
        <Icon size={19} />
      </span>
      <span className="home-row-copy">
        <strong>{reminder.title}</strong>
        <span>
          {reminder.category}
          {' \u00b7 '}
          <em className={`attention-text attention-text-${getAttentionTone(item)}`}>{formatAttentionStatus(item)}</em>
        </span>
      </span>
      <ChevronRight size={18} aria-hidden="true" className="home-row-chevron" />
    </button>
  )
}

function UpcomingRow({ reminder, onClick }: { reminder: Reminder; onClick: () => void }) {
  const { Icon, tone } = getCategoryVisual(reminder.category)

  return (
    <button type="button" className="home-list-row" onClick={onClick}>
      <span className={`home-row-icon tone-${tone}`} aria-hidden="true">
        <Icon size={19} />
      </span>
      <span className="home-row-copy">
        <strong>{reminder.title}</strong>
        <span>
          {reminder.category}
          {' \u00b7 '}
          {formatShortDate(reminder.due_date)}
        </span>
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

function formatAttentionStatus(item: AttentionReminder) {
  if (item.reason === 'Overdue') {
    const days = getDaysOverdue(item.reminder.due_date)
    return `Overdue by ${days} ${days === 1 ? 'day' : 'days'}`
  }

  if (item.reason === 'Due today') {
    return `Due today \u00b7 ${formatReminderTime(item.reminder.reminder_time)}`
  }

  const daysUntilDue = getDaysUntilDue(item.reminder.due_date)

  if (daysUntilDue > 0 && daysUntilDue <= 7) {
    return `Due in ${daysUntilDue} ${daysUntilDue === 1 ? 'day' : 'days'}`
  }

  if (item.reason === 'Reminder window') {
    return `Reminder started \u00b7 Due ${formatShortDate(item.reminder.due_date)}`
  }

  return `Due ${formatShortDate(item.reminder.due_date)}`
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

function isRenewalReminder(reminder: Reminder) {
  const title = reminder.title.toLowerCase()

  return (
    reminder.repeat === 'Yearly' ||
    title.includes('renew') ||
    title.includes('registration') ||
    title.includes('insurance') ||
    title.includes('license') ||
    title.includes('membership') ||
    title.includes('tag')
  )
}

function countByCategory(reminders: Reminder[], category: Reminder['category']) {
  return reminders.filter((reminder) => reminder.category === category).length
}

function getDaysOverdue(value: string) {
  const dueDate = parseDateOnly(value)
  const today = startOfDay(new Date())

  const difference = today.getTime() - dueDate.getTime()
  const days = Math.ceil(difference / 86_400_000)

  return Math.max(days, 1)
}

function getDaysUntilDue(value: string) {
  const dueDate = parseDateOnly(value)
  const today = startOfDay(new Date())

  return Math.ceil((dueDate.getTime() - today.getTime()) / 86_400_000)
}

function formatReminderTime(value: string | null) {
  const [hour = '9', minute = '00'] = (value ?? '09:00').split(':')
  const date = new Date(2000, 0, 1, Number(hour), Number(minute))

  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

function formatShortDate(value: string) {
  const date = parseDateOnly(value)

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(date)
}

function parseDateOnly(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function addDays(value: Date, days: number) {
  const next = new Date(value)
  next.setDate(next.getDate() + days)
  return startOfDay(next)
}
