import { useMemo } from 'react'
import {
  AlertCircle,
  Bell,
  Cake,
  CalendarCheck,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Plus,
  RefreshCcw,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { getMaintenanceDueDate } from '../lib/maintenanceUx'
import {
  formatReminderDueLabel,
  formatReminderStatusLabel,
  getReminderTypeLabel,
} from '../lib/reminderDisplay'
import { getRelevantRenewalDate } from '../lib/renewalUx'
import { getSmartReminderLabel } from '../lib/smartReminderLabels'
import type { Reminder } from '../types/reminder'

interface CalendarViewProps {
  reminders: Reminder[]
  isLoading: boolean
  selectedDate: string | null
  visibleMonth: string
  onAddForDate: (date: string) => void
  onSelectedDateChange: (date: string | null) => void
  onViewReminder: (reminder: Reminder) => void
  onVisibleMonthChange: (month: string) => void
}

interface CalendarDay {
  date: Date
  dateKey: string
  isCurrentMonth: boolean
  isSelected: boolean
  isToday: boolean
}

interface CalendarItem {
  date: Date
  dateKey: string
  reminder: Reminder
}

interface SyncIndicator {
  Icon: LucideIcon
  label: string
  tone: 'synced' | 'attention' | 'muted'
}

const weekDays = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']

export function CalendarView({
  reminders,
  isLoading,
  selectedDate,
  visibleMonth,
  onAddForDate,
  onSelectedDateChange,
  onViewReminder,
  onVisibleMonthChange,
}: CalendarViewProps) {
  const todayKey = formatDateOnly(new Date())
  const visibleMonthDate = startOfMonth(parseDateKey(visibleMonth) ?? new Date())
  const selectedDateValue = parseDateKey(selectedDate)
  const selectedDateKey =
    selectedDateValue && isSameMonth(selectedDateValue, visibleMonthDate) ? formatDateOnly(selectedDateValue) : null
  const selectedDateInMonth = selectedDateKey ? parseDateKey(selectedDateKey) : null
  const calendarItems = useMemo(() => buildCalendarItems(reminders), [reminders])
  const itemsByDate = useMemo(() => groupItemsByDate(calendarItems), [calendarItems])
  const monthItems = useMemo(
    () => calendarItems.filter((item) => isSameMonth(item.date, visibleMonthDate)),
    [calendarItems, visibleMonthDate],
  )
  const selectedDayItems = selectedDateKey ? itemsByDate.get(selectedDateKey) ?? [] : []
  const laterMonthItems =
    selectedDateInMonth === null
      ? []
      : monthItems.filter((item) => item.date.getTime() > selectedDateInMonth.getTime())
  const monthGroups = useMemo(() => groupItemsByDate(monthItems), [monthItems])
  const monthCells = useMemo(
    () => buildMonthCells(visibleMonthDate, todayKey, selectedDateKey),
    [selectedDateKey, todayKey, visibleMonthDate],
  )
  const defaultAddDate = selectedDateKey ?? getDefaultAddDate(visibleMonthDate, todayKey)

  function goToMonth(offset: number) {
    const nextMonth = startOfMonth(addMonths(visibleMonthDate, offset))
    onVisibleMonthChange(formatDateOnly(nextMonth))

    if (!selectedDateValue) {
      return
    }

    const selectedDay = selectedDateValue.getDate()
    const clampedDay = Math.min(selectedDay, getDaysInMonth(nextMonth))
    onSelectedDateChange(formatDateOnly(new Date(nextMonth.getFullYear(), nextMonth.getMonth(), clampedDay)))
  }

  function goToToday() {
    const today = new Date()
    onVisibleMonthChange(formatDateOnly(startOfMonth(today)))
    onSelectedDateChange(formatDateOnly(today))
  }

  function selectDate(day: CalendarDay) {
    onSelectedDateChange(day.dateKey)

    if (!day.isCurrentMonth) {
      onVisibleMonthChange(formatDateOnly(startOfMonth(day.date)))
    }
  }

  return (
    <section className="calendar-view" aria-labelledby="calendar-view-heading">
      <div className="calendar-page-heading">
        <div>
          <h2 id="calendar-view-heading">Calendar</h2>
          <p>See what's coming up.</p>
        </div>
        <button type="button" className="secondary-button calendar-today-button" onClick={goToToday}>
          Today
        </button>
      </div>

      <section className="calendar-month-card" aria-label="Month calendar">
        <div className="calendar-month-toolbar">
          <button type="button" className="icon-button calendar-month-button" onClick={() => goToMonth(-1)} aria-label="Previous month">
            <ChevronLeft size={20} aria-hidden="true" />
          </button>
          <strong>{formatMonthLabel(visibleMonthDate)}</strong>
          <button type="button" className="icon-button calendar-month-button" onClick={() => goToMonth(1)} aria-label="Next month">
            <ChevronRight size={20} aria-hidden="true" />
          </button>
        </div>

        <div className="calendar-weekdays" aria-hidden="true">
          {weekDays.map((day) => (
            <span key={day}>{day}</span>
          ))}
        </div>

        <div className="calendar-grid">
          {monthCells.map((day) => {
            const dayItems = itemsByDate.get(day.dateKey) ?? []
            return (
              <button
                type="button"
                className={getCalendarDayClass(day)}
                onClick={() => selectDate(day)}
                aria-label={`${formatAccessibleDate(day.dateKey)}${dayItems.length > 0 ? `, ${dayItems.length} scheduled` : ''}`}
                aria-pressed={day.isSelected}
                key={day.dateKey}
              >
                <span className="calendar-day-number">{day.date.getDate()}</span>
                <span className="calendar-day-markers" aria-hidden="true">
                  {dayItems.slice(0, 3).map((item) => (
                    <span className={`calendar-dot calendar-dot-${item.reminder.reminder_type}`} key={item.reminder.id} />
                  ))}
                  {dayItems.length > 3 ? <span className="calendar-dot-count">+{dayItems.length - 3}</span> : null}
                </span>
              </button>
            )
          })}
        </div>
      </section>

      <section className="calendar-agenda-card" aria-label="Calendar agenda">
        <div className="calendar-agenda-header">
          <div>
            <h3>{selectedDateKey ? formatAgendaHeading(selectedDateKey) : `${formatMonthLabel(visibleMonthDate)} agenda`}</h3>
            <p>{getAgendaSubcopy(selectedDateKey, monthItems.length, selectedDayItems.length)}</p>
          </div>
          <button
            type="button"
            className="secondary-button calendar-add-date-button"
            onClick={() => onAddForDate(defaultAddDate)}
          >
            <Plus size={16} aria-hidden="true" />
            {selectedDateKey ? 'Add for this date' : 'Add something'}
          </button>
        </div>

        {isLoading ? <p className="calendar-empty-text">Loading reminders...</p> : null}

        {!isLoading && monthItems.length === 0 ? (
          <CalendarEmptyState
            actionLabel="Add something"
            message="Nothing scheduled this month."
            onAction={() => onAddForDate(defaultAddDate)}
          />
        ) : null}

        {!isLoading && monthItems.length > 0 && selectedDateKey ? (
          <>
            {selectedDayItems.length > 0 ? (
              <div className="calendar-agenda-list">
                {selectedDayItems.map((item) => (
                  <CalendarAgendaRow item={item} key={item.reminder.id} onViewReminder={onViewReminder} />
                ))}
              </div>
            ) : (
              <CalendarEmptyState
                actionLabel="Add for this date"
                message="Nothing scheduled for this date."
                onAction={() => onAddForDate(selectedDateKey)}
              />
            )}

            {laterMonthItems.length > 0 ? (
              <section className="calendar-later-section" aria-label="Later this month">
                <div className="calendar-later-header">
                  <h3>Later this month</h3>
                  <span>{laterMonthItems.length}</span>
                </div>
                <div className="calendar-agenda-list">
                  {laterMonthItems.slice(0, 4).map((item) => (
                    <CalendarAgendaRow item={item} key={item.reminder.id} onViewReminder={onViewReminder} />
                  ))}
                </div>
              </section>
            ) : null}

            {monthItems.length > selectedDayItems.length ? (
              <button type="button" className="calendar-full-agenda-button" onClick={() => onSelectedDateChange(null)}>
                <CalendarDays size={16} aria-hidden="true" />
                View full month agenda
                <ChevronRight size={18} aria-hidden="true" />
              </button>
            ) : null}
          </>
        ) : null}

        {!isLoading && monthItems.length > 0 && !selectedDateKey ? (
          <div className="calendar-month-agenda">
            {Array.from(monthGroups.entries()).map(([dateKey, items]) => (
              <section className="calendar-agenda-group" aria-label={formatAccessibleDate(dateKey)} key={dateKey}>
                <h4>{formatGroupHeading(dateKey, todayKey)}</h4>
                <div className="calendar-agenda-list">
                  {items.map((item) => (
                    <CalendarAgendaRow item={item} key={item.reminder.id} onViewReminder={onViewReminder} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : null}
      </section>
    </section>
  )
}

function CalendarAgendaRow({
  item,
  onViewReminder,
}: {
  item: CalendarItem
  onViewReminder: (reminder: Reminder) => void
}) {
  const reminder = item.reminder
  const TypeIcon = getTypeIcon(reminder.reminder_type)
  const smartLabel = getSmartReminderLabel(reminder)
  const syncIndicator = getSyncIndicator(reminder)
  const SyncIcon = syncIndicator?.Icon ?? CalendarDays

  return (
    <button type="button" className="calendar-agenda-row" onClick={() => onViewReminder(reminder)}>
      <span className={`calendar-type-icon calendar-type-${reminder.reminder_type}`} aria-hidden="true">
        <TypeIcon size={18} />
      </span>
      <span className="calendar-agenda-copy">
        <strong>{reminder.title}</strong>
        <span>
          {getReminderTypeLabel(reminder.reminder_type)}
          {' \u2022 '}
          {reminder.category}
        </span>
        <small>{smartLabel ? `${smartLabel} \u2022 ${formatReminderStatusLabel(reminder)}` : formatReminderDueLabel(reminder, { includeDate: false })}</small>
        {syncIndicator ? (
          <span className={`calendar-sync-pill calendar-sync-pill-${syncIndicator.tone}`}>
            <SyncIcon size={13} aria-hidden="true" />
            {syncIndicator.label}
          </span>
        ) : null}
      </span>
      <ChevronRight size={18} aria-hidden="true" className="calendar-agenda-chevron" />
    </button>
  )
}

function CalendarEmptyState({
  actionLabel,
  message,
  onAction,
}: {
  actionLabel: string
  message: string
  onAction: () => void
}) {
  return (
    <div className="calendar-empty-card">
      <CalendarDays size={22} aria-hidden="true" />
      <p>{message}</p>
      <button type="button" className="secondary-button calendar-empty-button" onClick={onAction}>
        <Plus size={16} aria-hidden="true" />
        {actionLabel}
      </button>
    </div>
  )
}

function buildCalendarItems(reminders: Reminder[]): CalendarItem[] {
  return reminders
    .flatMap((reminder): CalendarItem[] => {
      if (reminder.completed) {
        return []
      }

      const dateKey = toDateKey(getCalendarDate(reminder))
      const date = parseDateKey(dateKey)

      if (!dateKey || !date) {
        return []
      }

      return [{ date, dateKey, reminder }]
    })
    .sort((left, right) => {
      const dateDifference = left.date.getTime() - right.date.getTime()

      if (dateDifference !== 0) {
        return dateDifference
      }

      const statusDifference = getStatusRank(left.reminder) - getStatusRank(right.reminder)
      if (statusDifference !== 0) {
        return statusDifference
      }

      return left.reminder.title.localeCompare(right.reminder.title)
    })
}

function getCalendarDate(reminder: Reminder) {
  if (reminder.reminder_type === 'renewal' && reminder.renewal_details) {
    return getRelevantRenewalDate(reminder.renewal_details, reminder.due_date)
  }

  if (reminder.reminder_type === 'maintenance' && reminder.maintenance_details) {
    return getMaintenanceDueDate(reminder.maintenance_details, reminder.due_date)
  }

  return reminder.due_date
}

function groupItemsByDate(items: CalendarItem[]) {
  return items.reduce((groups, item) => {
    const group = groups.get(item.dateKey) ?? []
    group.push(item)
    groups.set(item.dateKey, group)
    return groups
  }, new Map<string, CalendarItem[]>())
}

function buildMonthCells(month: Date, todayKey: string, selectedDateKey: string | null): CalendarDay[] {
  const monthStart = startOfMonth(month)
  const monthEnd = new Date(month.getFullYear(), month.getMonth() + 1, 0)
  const gridStart = addDays(monthStart, -monthStart.getDay())
  const gridEnd = addDays(monthEnd, 6 - monthEnd.getDay())
  const days: CalendarDay[] = []

  for (let day = new Date(gridStart); day.getTime() <= gridEnd.getTime(); day = addDays(day, 1)) {
    const dateKey = formatDateOnly(day)
    days.push({
      date: day,
      dateKey,
      isCurrentMonth: isSameMonth(day, month),
      isSelected: selectedDateKey === dateKey,
      isToday: todayKey === dateKey,
    })
  }

  return days
}

function getCalendarDayClass(day: CalendarDay) {
  return [
    'calendar-day',
    day.isCurrentMonth ? 'calendar-day-current' : 'calendar-day-adjacent',
    day.isToday ? 'calendar-day-today' : '',
    day.isSelected ? 'calendar-day-selected' : '',
  ]
    .filter(Boolean)
    .join(' ')
}

function getAgendaSubcopy(selectedDateKey: string | null, monthCount: number, selectedCount: number) {
  if (!selectedDateKey) {
    return formatCount(monthCount, 'item')
  }

  if (selectedCount === 0) {
    return 'No LifeLedger items on this date.'
  }

  return formatCount(selectedCount, 'item')
}

function getSyncIndicator(reminder: Reminder): SyncIndicator | null {
  if (reminder.calendar_sync_status === 'needs_attention' || reminder.calendar_sync_status === 'error') {
    return {
      Icon: AlertCircle,
      label: 'Needs attention',
      tone: 'attention',
    }
  }

  if (reminder.calendar_sync_enabled && reminder.calendar_sync_status === 'synced') {
    return {
      Icon: CalendarCheck,
      label: 'Synced',
      tone: 'synced',
    }
  }

  if (reminder.calendar_sync_enabled) {
    return {
      Icon: CalendarDays,
      label: 'Not synced',
      tone: 'muted',
    }
  }

  return null
}

function getTypeIcon(type: Reminder['reminder_type']) {
  if (type === 'birthday') {
    return Cake
  }

  if (type === 'renewal') {
    return RefreshCcw
  }

  if (type === 'maintenance') {
    return Wrench
  }

  return Bell
}

function getStatusRank(reminder: Reminder) {
  if (reminder.status === 'Overdue') {
    return 0
  }

  if (reminder.status === 'Due today') {
    return 1
  }

  if (reminder.status === 'Due this week') {
    return 2
  }

  if (reminder.status === 'Due this month') {
    return 3
  }

  return 4
}

function getDefaultAddDate(visibleMonth: Date, todayKey: string) {
  const today = parseDateKey(todayKey) ?? new Date()

  if (isSameMonth(today, visibleMonth)) {
    return todayKey
  }

  return formatDateOnly(visibleMonth)
}

function formatCount(count: number, noun: string) {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

function formatMonthLabel(value: Date) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'long',
    year: 'numeric',
  }).format(value)
}

function formatAgendaHeading(value: string) {
  const date = parseDateKey(value)

  if (!date) {
    return 'Selected date'
  }

  return new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(date)
}

function formatGroupHeading(value: string, todayKey: string) {
  const date = parseDateKey(value)

  if (!date) {
    return value
  }

  const label = new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(date)

  return value === todayKey ? `Today, ${label}` : label
}

function formatAccessibleDate(value: string) {
  const date = parseDateKey(value)

  if (!date) {
    return value
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'full',
  }).format(date)
}

function toDateKey(value: string | null | undefined) {
  const date = parseDateKey(value)
  return date ? formatDateOnly(date) : null
}

function parseDateKey(value: string | null | undefined) {
  if (!value || !/^\d{4}-\d{2}-\d{2}/.test(value)) {
    return null
  }

  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  const date = new Date(year, month - 1, day)

  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return null
  }

  return date
}

function formatDateOnly(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function startOfMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), 1)
}

function addDays(value: Date, days: number) {
  const next = new Date(value)
  next.setDate(next.getDate() + days)
  return new Date(next.getFullYear(), next.getMonth(), next.getDate())
}

function addMonths(value: Date, months: number) {
  return new Date(value.getFullYear(), value.getMonth() + months, 1)
}

function getDaysInMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth() + 1, 0).getDate()
}

function isSameMonth(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth()
}
