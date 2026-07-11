import type { LifeRecord } from '../types/record'
import {
  formatLongDate,
  formatRelativeDatePhrase,
  formatShortDate,
  getDaysUntilDate,
} from './reminderDisplay'

export type RecordUiStatus = 'Active' | 'Archived' | 'Expired' | 'Expiring soon'

export function getRecordStatusLabel(record: LifeRecord): RecordUiStatus {
  if (record.status === 'archived') {
    return 'Archived'
  }

  if (!record.expiration_date) {
    return 'Active'
  }

  const daysUntilExpiration = getDaysUntilDate(record.expiration_date)
  if (daysUntilExpiration < 0) {
    return 'Expired'
  }

  if (daysUntilExpiration <= 60) {
    return 'Expiring soon'
  }

  return 'Active'
}

export function getRecordStatusClass(record: LifeRecord) {
  const status = getRecordStatusLabel(record)

  if (status === 'Archived') {
    return 'status-completed'
  }

  if (status === 'Expired') {
    return 'status-overdue'
  }

  if (status === 'Expiring soon') {
    return 'status-today'
  }

  return 'status-month'
}

export function formatRecordKeyDate(record: LifeRecord) {
  if (record.expiration_date) {
    return formatExpirationLabel(record.expiration_date)
  }

  if (record.renewal_date) {
    return `Renews on ${formatLongDate(record.renewal_date)}`
  }

  if (record.purchase_date) {
    return `Purchased ${formatShortDate(record.purchase_date)}`
  }

  if (record.issue_date) {
    return `Issued ${formatShortDate(record.issue_date)}`
  }

  if (record.start_date) {
    return `Started ${formatShortDate(record.start_date)}`
  }

  return null
}

export function formatExpirationLabel(value: string) {
  const daysUntilExpiration = getDaysUntilDate(value)

  if (daysUntilExpiration < 0) {
    return `Expired ${formatRelativeDatePhrase(value)}`
  }

  if (daysUntilExpiration === 0) {
    return `Expires today`
  }

  return `Expires ${formatRelativeDatePhrase(value, { monthApproximation: true })}`
}

export function formatRecordDate(value: string | null | undefined) {
  return value ? formatLongDate(value) : null
}

export function getRecordProviderLine(record: LifeRecord) {
  if (record.owner_name && record.provider_or_brand) {
    return `${record.owner_name} \u2022 ${record.provider_or_brand}`
  }

  return record.owner_name ?? record.provider_or_brand ?? null
}

export function formatRecordTimestamp(value: string) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) {
    return null
  }

  return timestamp.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}
