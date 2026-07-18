import {
  CalendarDays,
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

import { getDigestSummaryText, hasDigestItems, type DailyDigest } from '../lib/digest'
import {
  formatReminderAttentionLabel,
  formatReminderStatusLabel,
  getReminderEffectiveDate,
  isActionableReminder,
  isDueWithinDays,
  parseDateOnly,
  sortActionCenterReminders,
} from '../lib/reminderDisplay'
import { getSmartReminderLabel } from '../lib/smartReminderLabels'
import { guidedWorkflowOptions, type GuidedWorkflowId } from '../lib/guidedWorkflows'
import type { DigestPreferences } from '../types/preferences'
import type { Reminder, ReminderAlert, ReminderType } from '../types/reminder'
import { getCategoryVisual } from './categoryVisuals'

interface HomeDashboardProps {
  reminders: Reminder[]
  alerts: ReminderAlert[]
  digest: DailyDigest
  digestPreferences: DigestPreferences
  isLoading: boolean
  recordsCount: number
  userName?: string | null
  onAddRecord: () => void
  onAddReminder: () => void
  onBrowseTemplates: () => void
  onViewCalendar: (date?: string | null) => void
  onViewReminders: () => void
  onViewAlerts: () => void
  onOpenDigest: () => void
  onViewRecords: () => void
  onViewReminder: (reminder: Reminder) => void
  onStartWorkflow?: (workflowId: GuidedWorkflowId) => void
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
  digest,
  digestPreferences,
  isLoading,
  recordsCount,
  userName,
  onAddRecord,
  onAddReminder,
  onBrowseTemplates,
  onViewCalendar,
  onViewReminders,
  onOpenDigest,
  onViewRecords,
  onViewReminder,
  onStartWorkflow,
}: HomeDashboardProps) {
  const activeReminders = reminders.filter(isActionableReminder)
  const genericReminders = activeReminders.filter((reminder) => reminder.reminder_type === 'generic')
  const birthdayReminders = activeReminders.filter((reminder) => reminder.reminder_type === 'birthday')
  const renewalReminders = activeReminders.filter((reminder) => reminder.reminder_type === 'renewal')
  const maintenanceReminders = activeReminders.filter((reminder) => reminder.reminder_type === 'maintenance')
  const attentionItems = [...activeReminders].sort(sortActionCenterReminders)
  const visibleAttentionItems = attentionItems.slice(0, maxAttentionItems)
  const overdueCount = activeReminders.filter((reminder) => reminder.status === 'Overdue').length
  const dueWithin30Count = activeReminders.filter((reminder) => isDueWithinDays(reminder, 30)).length
  const upcomingItems = getUpcomingReminders(activeReminders).slice(0, maxUpcomingItems)
  const overviewTiles: OverviewTileData[] = [
    {
      label: 'Reminders',
      value: String(genericReminders.length),
      sublabel: formatOverviewSublabel(countRemindersByType(activeReminders, 'generic'), 'need attention'),
      icon: ListChecks,
      tone: 'blue',
      onClick: onViewReminders,
    },
    {
      label: 'Birthdays',
      value: String(birthdayReminders.length),
      sublabel: formatOverviewSublabel(countRemindersByType(activeReminders, 'birthday'), 'coming up'),
      icon: Gift,
      tone: 'purple',
      onClick: onViewReminders,
    },
    {
      label: 'Renewals',
      value: String(renewalReminders.length),
      sublabel: formatOverviewSublabel(countRemindersByType(activeReminders, 'renewal'), 'need attention'),
      icon: RefreshCcw,
      tone: 'orange',
      onClick: onViewReminders,
    },
    {
      label: 'Maintenance',
      value: String(maintenanceReminders.length),
      sublabel: formatOverviewSublabel(countRemindersByType(activeReminders, 'maintenance'), 'due'),
      icon: Wrench,
      tone: 'teal',
      onClick: onViewReminders,
    },
    {
      label: 'Items',
      value: String(recordsCount),
      sublabel: recordsCount === 0 ? 'Ready to add' : 'Active',
      icon: FileText,
      tone: 'green',
      onClick: onViewRecords,
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
          <p>{formatAttentionSummary(attentionItems.length, overdueCount, dueWithin30Count)}</p>
        </div>
        <button type="button" className="home-hero-link" onClick={onViewReminders} aria-label="Open Action Center">
          <ChevronRight size={21} aria-hidden="true" />
        </button>
      </section>

      {recordsCount === 0 ? (
        <section className="home-first-item-card" aria-labelledby="first-item-heading">
          <div>
            <h2 id="first-item-heading">What would you like to keep track of?</h2>
            <p>LifeLedger keeps important information, responsibilities, dates, documents, and relationships together. Start with one useful item.</p>
          </div>
          <button type="button" className="primary-button" onClick={onAddRecord}>
            <Plus size={17} aria-hidden="true" />
            Add your first item
          </button>
        </section>
      ) : null}

      {onStartWorkflow ? (
        <section className="home-card home-guided-starts" aria-labelledby="guided-quick-start-heading">
          <div className="home-card-header">
            <div>
              <h2 id="guided-quick-start-heading">Quick starts</h2>
              <p>Track the item, important date, reminder, and optional document together.</p>
            </div>
          </div>
          <div className="home-guided-start-grid">
            {guidedWorkflowOptions.map((workflow) => {
              const Icon = workflow.icon
              return (
                <button type="button" key={workflow.id} onClick={() => onStartWorkflow(workflow.id)}>
                  <Icon size={18} aria-hidden="true" />
                  <span>{workflow.intentLabel}</span>
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              )
            })}
          </div>
        </section>
      ) : null}

      <section className="home-digest-card" aria-labelledby="daily-digest-card-heading">
        <div className="home-digest-icon" aria-hidden="true">
          <CalendarDays size={24} />
        </div>
        <div className="home-digest-copy">
          <div className="home-card-header home-digest-header">
            <h2 id="daily-digest-card-heading">Daily Digest</h2>
            <span className="digest-seen-badge">{getDigestSeenLabel(digestPreferences.digest_last_seen_at)}</span>
          </div>
          <p>{getDigestCardSummary(digest, digestPreferences.digest_enabled)}</p>
          <small>{getDigestCardSubcopy(digest, digestPreferences)}</small>
        </div>
        <button type="button" className="primary-button home-digest-button" onClick={onOpenDigest}>
          View digest
        </button>
      </section>

      <section className="quick-actions-card" aria-label="Quick actions">
        <QuickAction label="Add reminder" icon={Plus} tone="blue" onClick={onAddReminder} />
        <QuickAction label="Browse templates" icon={ListChecks} tone="blue-soft" onClick={onBrowseTemplates} />
        <QuickAction label="Add item" icon={FileText} tone="green" onClick={onAddRecord} />
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
                <DashboardReminderRow reminder={item} key={item.id} onClick={() => onViewReminder(item)} />
              ))}
            </div>
            {attentionItems.length > maxAttentionItems ? (
              <button type="button" className="home-card-link" onClick={onViewReminders}>
                View all
              </button>
            ) : null}
          </>
        ) : null}
      </section>

      <section className="home-card" aria-labelledby="upcoming-heading">
        <div className="home-card-header">
          <h2 id="upcoming-heading">Due within 30 days</h2>
          {upcomingItems.length > 0 ? <span className="count-badge">{upcomingItems.length}</span> : null}
        </div>

        {isLoading ? <p className="home-empty-state">Loading reminders...</p> : null}

        {!isLoading && upcomingItems.length === 0 ? (
          <p className="home-empty-state">No active reminders due within 30 days.</p>
        ) : null}

        {!isLoading && upcomingItems.length > 0 ? (
          <>
            <div className="home-list">
              {upcomingItems.map((reminder) => (
                <UpcomingRow reminder={reminder} key={reminder.id} onClick={() => onViewReminder(reminder)} />
              ))}
            </div>
            <button type="button" className="home-card-link" onClick={() => onViewCalendar(upcomingItems[0] ? getReminderEffectiveDate(upcomingItems[0]) : null)}>
              View calendar
            </button>
          </>
        ) : null}
      </section>

      <section className="home-card" aria-labelledby="overview-heading">
        <div className="home-card-header">
          <h2 id="overview-heading">Life admin overview</h2>
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

function countRemindersByType(reminders: Reminder[], type: ReminderType) {
  return reminders.filter((reminder) => reminder.reminder_type === type).length
}

function QuickAction({
  label,
  icon: Icon,
  tone,
  onClick,
}: {
  label: string
  icon: LucideIcon
  tone: string
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      className={`quick-action quick-action-${tone}`}
      onClick={onClick}
      aria-label={label}
    >
      <span className="quick-action-icon" aria-hidden="true">
        <Icon size={22} />
      </span>
      <span>{label}</span>
    </button>
  )
}

function DashboardReminderRow({ reminder, onClick }: { reminder: Reminder; onClick: () => void }) {
  const { Icon, tone } = getCategoryVisual(reminder.category)

  return (
    <button type="button" className="home-list-row" onClick={onClick}>
      <span className={`home-row-icon tone-${tone}`} aria-hidden="true">
        <Icon size={19} />
      </span>
      <span className="home-row-copy">
        <strong>{reminder.title}</strong>
        <span>
          {formatReminderStatusLabel(reminder)}
          {' \u2022 '}
          {formatReminderAttentionLabel(reminder, { includeDate: false })}
        </span>
      </span>
      <ChevronRight size={18} aria-hidden="true" className="home-row-chevron" />
    </button>
  )
}

function UpcomingRow({ reminder, onClick }: { reminder: Reminder; onClick: () => void }) {
  const { Icon, tone } = getCategoryVisual(reminder.category)
  const smartLabel = getSmartReminderLabel(reminder)
  const detail = smartLabel ?? formatReminderAttentionLabel(reminder, { includeDate: false })

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

function formatAttentionSummary(count: number, overdueCount: number, dueWithin30Count: number) {
  if (count === 0) {
    return 'No reminders need attention today.'
  }

  return `${count} active ${count === 1 ? 'reminder' : 'reminders'}; ${overdueCount} overdue; ${dueWithin30Count} due within 30 days.`
}

function getDigestCardSummary(digest: DailyDigest, isEnabled: boolean) {
  if (!isEnabled) {
    return 'Daily Digest is paused.'
  }

  return hasDigestItems(digest) ? getDigestSummaryText(digest) : "You're all caught up today."
}

function getDigestCardSubcopy(digest: DailyDigest, preferences: DigestPreferences) {
  if (!preferences.digest_enabled) {
    return 'Turn it back on in Settings when you want the daily briefing.'
  }

  if (digest.totals.comingUp > 0) {
    return `Looking ahead ${preferences.digest_lookahead_days} days.`
  }

  return 'No reminders need attention today.'
}

function getDigestSeenLabel(lastSeenAt: string | null) {
  if (!lastSeenAt) {
    return 'Not viewed today'
  }

  const lastSeenDate = new Date(lastSeenAt)
  if (Number.isNaN(lastSeenDate.getTime())) {
    return 'Not viewed today'
  }

  return sameCalendarDate(lastSeenDate, new Date()) ? 'Viewed today' : 'Not viewed today'
}

function formatOverviewSublabel(count: number, label: string) {
  return count === 0 ? 'All clear' : `${count} ${label}`
}

function getUpcomingReminders(reminders: Reminder[]) {
  return reminders
    .filter((reminder) => isDueWithinDays(reminder, 30))
    .sort((left, right) => {
      const dueDifference = parseDateOnly(getReminderEffectiveDate(left)).getTime() - parseDateOnly(getReminderEffectiveDate(right)).getTime()

      if (dueDifference !== 0) {
        return dueDifference
      }

      return left.title.localeCompare(right.title)
    })
}

function sameCalendarDate(left: Date, right: Date) {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  )
}
