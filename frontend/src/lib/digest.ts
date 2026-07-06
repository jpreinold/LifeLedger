import { getDaysUntilDate, parseDateOnly } from './reminderDisplay'
import { toAttentionReminder, type AttentionReminder } from './reminderSchedule'
import type { Reminder, ReminderAlert, ReminderType } from '../types/reminder'

export interface DigestOptions {
  lookaheadDays: number
}

export interface DigestSmartGroup {
  type: Extract<ReminderType, 'birthday' | 'renewal' | 'maintenance'>
  label: string
  count: number
}

export interface DailyDigest {
  needsAttention: AttentionReminder[]
  dueToday: Reminder[]
  comingUp: Reminder[]
  smartGroups: DigestSmartGroup[]
  totals: {
    needsAttention: number
    dueToday: number
    comingUp: number
  }
}

const sectionLimit = 5

const smartGroupLabels: Record<DigestSmartGroup['type'], string> = {
  birthday: 'Birthdays coming up',
  renewal: 'Renewals coming up',
  maintenance: 'Maintenance coming up',
}

export function buildDailyDigest(reminders: Reminder[], alerts: ReminderAlert[], options: DigestOptions): DailyDigest {
  const usedReminderIds = new Set<string>()
  const activeReminders = reminders.filter((reminder) => !reminder.completed)
  const needsAttentionAll = alerts.map(toAttentionReminder)
  needsAttentionAll.forEach((item) => usedReminderIds.add(item.reminder.id))

  const dueTodayAll = activeReminders
    .filter((reminder) => !usedReminderIds.has(reminder.id) && getDaysUntilDate(reminder.due_date) === 0)
    .sort(sortByDueDateThenTitle)
  dueTodayAll.forEach((reminder) => usedReminderIds.add(reminder.id))

  const comingUpAll = activeReminders
    .filter((reminder) => {
      if (usedReminderIds.has(reminder.id)) {
        return false
      }

      const daysUntil = getDaysUntilDate(reminder.due_date)
      return daysUntil > 0 && daysUntil <= options.lookaheadDays
    })
    .sort(sortByDueDateThenTitle)

  const smartGroups = getSmartGroups(comingUpAll)

  return {
    needsAttention: needsAttentionAll.slice(0, sectionLimit),
    dueToday: dueTodayAll.slice(0, sectionLimit),
    comingUp: comingUpAll.slice(0, sectionLimit),
    smartGroups,
    totals: {
      needsAttention: needsAttentionAll.length,
      dueToday: dueTodayAll.length,
      comingUp: comingUpAll.length,
    },
  }
}

export function getDigestSummaryText(digest: DailyDigest) {
  const counts = [
    formatDigestCount(digest.totals.needsAttention, 'needs attention'),
    formatDigestCount(digest.totals.dueToday, 'due today'),
    formatDigestCount(digest.totals.comingUp, 'coming up'),
  ]

  return counts.join(' • ')
}

export function hasDigestItems(digest: DailyDigest) {
  return digest.totals.needsAttention > 0 || digest.totals.dueToday > 0 || digest.totals.comingUp > 0
}

function getSmartGroups(reminders: Reminder[]): DigestSmartGroup[] {
  const counts: Record<DigestSmartGroup['type'], number> = {
    birthday: 0,
    renewal: 0,
    maintenance: 0,
  }

  reminders.forEach((reminder) => {
    if (reminder.reminder_type === 'birthday' || reminder.reminder_type === 'renewal' || reminder.reminder_type === 'maintenance') {
      counts[reminder.reminder_type] += 1
    }
  })

  return (Object.keys(counts) as DigestSmartGroup['type'][])
    .filter((type) => counts[type] > 0)
    .map((type) => ({
      type,
      label: smartGroupLabels[type],
      count: counts[type],
    }))
}

function formatDigestCount(count: number, label: string) {
  return `${count} ${label}`
}

function sortByDueDateThenTitle(left: Reminder, right: Reminder) {
  const dueDifference = parseDateOnly(left.due_date).getTime() - parseDateOnly(right.due_date).getTime()

  if (dueDifference !== 0) {
    return dueDifference
  }

  return left.title.localeCompare(right.title)
}
