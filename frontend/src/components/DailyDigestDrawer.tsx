import { CalendarDays, CheckCircle2, ChevronRight, X } from 'lucide-react'
import type { MouseEvent, ReactNode } from 'react'

import { getAttentionDetail, getAttentionLabel } from '../lib/attentionDisplay'
import type { DailyDigest } from '../lib/digest'
import {
  formatLongDate,
  formatReminderDueLabel,
  formatShortDate,
  getReminderTypeLabel,
} from '../lib/reminderDisplay'
import type { AttentionReminder } from '../lib/reminderSchedule'
import { getSmartReminderLabel } from '../lib/smartReminderLabels'
import type { Reminder } from '../types/reminder'
import { getCategoryVisual } from './categoryVisuals'
import { SheetDrawer } from './SheetDrawer'

interface DailyDigestDrawerProps {
  digest: DailyDigest
  isLoading: boolean
  isOpen: boolean
  onClose: () => void
  onComplete: (id: string) => Promise<void>
  onDismiss: (id: string) => Promise<void>
  onViewReminder: (reminder: Reminder) => void
}

export function DailyDigestDrawer({
  digest,
  isLoading,
  isOpen,
  onClose,
  onComplete,
  onDismiss,
  onViewReminder,
}: DailyDigestDrawerProps) {
  const hasBriefingItems =
    digest.needsAttention.length > 0 || digest.dueToday.length > 0 || digest.comingUp.length > 0

  return (
    <SheetDrawer className="digest-dialog" isOpen={isOpen} labelledBy="daily-digest-heading" onClose={onClose}>
      <div className="sheet-header digest-header">
        <div>
          <h2 id="daily-digest-heading">Daily Digest</h2>
          <p>{formatLongDate(new Date().toISOString())}</p>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close daily digest">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="digest-body">
        <section className="digest-summary-card" aria-label="Daily Digest summary">
          <div className="digest-summary-icon" aria-hidden="true">
            <CalendarDays size={22} />
          </div>
          <div>
            <h3>Here&apos;s what needs attention today.</h3>
            <p>{getDigestIntro(digest)}</p>
          </div>
        </section>

        {isLoading ? <p className="digest-empty-state">Loading your digest...</p> : null}

        {!isLoading && !hasBriefingItems ? (
          <div className="digest-empty-card">
            <CheckCircle2 size={25} aria-hidden="true" />
            <h3>You&apos;re all caught up.</h3>
            <p>No reminders need attention today.</p>
          </div>
        ) : null}

        {!isLoading && digest.needsAttention.length > 0 ? (
          <DigestSection
            count={digest.totals.needsAttention}
            title="Needs attention"
            visibleCount={digest.needsAttention.length}
          >
            {digest.needsAttention.map((item) => (
              <DigestAttentionItem
                item={item}
                key={item.reminder.id}
                onComplete={onComplete}
                onDismiss={onDismiss}
                onViewReminder={onViewReminder}
              />
            ))}
          </DigestSection>
        ) : null}

        {!isLoading && digest.dueToday.length > 0 ? (
          <DigestSection count={digest.totals.dueToday} title="Due today" visibleCount={digest.dueToday.length}>
            {digest.dueToday.map((reminder) => (
              <DigestReminderItem
                detail="Due today"
                key={reminder.id}
                reminder={reminder}
                onViewReminder={onViewReminder}
              />
            ))}
          </DigestSection>
        ) : null}

        {!isLoading && digest.comingUp.length > 0 ? (
          <DigestSection count={digest.totals.comingUp} title="Coming up" visibleCount={digest.comingUp.length}>
            {digest.comingUp.map((reminder) => (
              <DigestReminderItem
                detail={getReminderDetail(reminder)}
                key={reminder.id}
                reminder={reminder}
                onViewReminder={onViewReminder}
              />
            ))}
          </DigestSection>
        ) : null}

        {!isLoading && digest.smartGroups.length > 0 ? (
          <section className="digest-section digest-smart-summary" aria-labelledby="digest-smart-heading">
            <div className="digest-section-header">
              <h3 id="digest-smart-heading">Smart reminders</h3>
            </div>
            <div className="digest-smart-grid">
              {digest.smartGroups.map((group) => (
                <div className={`digest-smart-pill digest-smart-pill-${group.type}`} key={group.type}>
                  <strong>{group.count}</strong>
                  <span>{group.label}</span>
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </SheetDrawer>
  )
}

function DigestSection({
  children,
  count,
  title,
  visibleCount,
}: {
  children: ReactNode
  count: number
  title: string
  visibleCount: number
}) {
  const remainingCount = count - visibleCount

  return (
    <section className="digest-section" aria-label={title}>
      <div className="digest-section-header">
        <h3>{title}</h3>
        <span className="count-badge">{count}</span>
      </div>
      <div className="digest-list">{children}</div>
      {remainingCount > 0 ? <p className="digest-more-note">+{remainingCount} more in Reminders.</p> : null}
    </section>
  )
}

function DigestAttentionItem({
  item,
  onComplete,
  onDismiss,
  onViewReminder,
}: {
  item: AttentionReminder
  onComplete: (id: string) => Promise<void>
  onDismiss: (id: string) => Promise<void>
  onViewReminder: (reminder: Reminder) => void
}) {
  const detail = getAttentionDetail(item)

  return (
    <DigestItemShell
      badge={getAttentionLabel(item)}
      detail={detail}
      reminder={item.reminder}
      onViewReminder={onViewReminder}
    >
      <button type="button" className="digest-chip-button" onClick={(event) => handleAction(event, onDismiss, item.reminder.id)}>
        Dismiss
      </button>
      <button type="button" className="digest-chip-button digest-chip-button-primary" onClick={(event) => handleAction(event, onComplete, item.reminder.id)}>
        Complete
      </button>
    </DigestItemShell>
  )
}

function DigestReminderItem({
  detail,
  reminder,
  onViewReminder,
}: {
  detail: string
  reminder: Reminder
  onViewReminder: (reminder: Reminder) => void
}) {
  return <DigestItemShell badge={getReminderTypeLabel(reminder.reminder_type)} detail={detail} reminder={reminder} onViewReminder={onViewReminder} />
}

function DigestItemShell({
  badge,
  children,
  detail,
  reminder,
  onViewReminder,
}: {
  badge: string
  children?: ReactNode
  detail: string
  reminder: Reminder
  onViewReminder: (reminder: Reminder) => void
}) {
  const { Icon, tone } = getCategoryVisual(reminder.category)

  return (
    <article className={`digest-item tone-${tone}`}>
      <button type="button" className="digest-item-main" onClick={() => onViewReminder(reminder)}>
        <span className={`digest-item-icon tone-${tone}`} aria-hidden="true">
          <Icon size={19} />
        </span>
        <span className="digest-item-copy">
          <span className="digest-item-badge">{badge}</span>
          <strong>{reminder.title}</strong>
          <span>{detail}</span>
          <small>
            {reminder.category} {'\u2022'} {formatShortDate(reminder.due_date)}
          </small>
        </span>
        <ChevronRight size={18} aria-hidden="true" className="digest-item-chevron" />
      </button>
      {children ? <div className="digest-item-actions">{children}</div> : null}
    </article>
  )
}

function handleAction(
  event: MouseEvent<HTMLButtonElement>,
  action: (id: string) => Promise<void>,
  id: string,
) {
  event.stopPropagation()
  void action(id)
}

function getDigestIntro(digest: DailyDigest) {
  if (digest.totals.needsAttention > 0) {
    return `${digest.totals.needsAttention} ${digest.totals.needsAttention === 1 ? 'item needs' : 'items need'} your attention.`
  }

  if (digest.totals.dueToday > 0) {
    return `${digest.totals.dueToday} ${digest.totals.dueToday === 1 ? 'reminder is' : 'reminders are'} due today.`
  }

  if (digest.totals.comingUp > 0) {
    return `${digest.totals.comingUp} ${digest.totals.comingUp === 1 ? 'reminder is' : 'reminders are'} coming up.`
  }

  return 'No reminders need attention today.'
}

function getReminderDetail(reminder: Reminder) {
  return getSmartReminderLabel(reminder) ?? formatReminderDueLabel(reminder, { includeDate: false })
}
