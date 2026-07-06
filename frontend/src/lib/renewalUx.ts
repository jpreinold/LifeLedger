import type {
  PriorityOption,
  Reminder,
  ReminderCategory,
  ReminderInput,
  ReminderLeadUnit,
  RenewalDetails,
  RenewalDetailsInput,
  RenewalKind,
  RepeatOption,
} from '../types/reminder'
import { formatCount, formatRelativeDatePhrase, getDaysUntilDate } from './reminderDisplay'
import { formatReminderTiming } from './reminderSchedule'

export const renewalDisplayKinds = [
  'renewal',
  'expiration',
  'review',
  'subscription',
  'free_trial',
  'warranty',
  'document',
] as const

export type RenewalDisplayKind = (typeof renewalDisplayKinds)[number]

type RenewalDetailsLike = RenewalDetails | RenewalDetailsInput

interface RenewalKindOption {
  kind: RenewalDisplayKind
  label: string
  description: string
}

interface RenewalDefaults {
  repeat: RepeatOption
  priority: PriorityOption
  reminder_lead_value: number
  reminder_lead_unit: ReminderLeadUnit
  reminder_time: string
  category?: ReminderCategory
  review_lead_days?: number | null
  renewal_window_days?: number | null
}

interface RenewalPreview {
  primary: string
  reminder: string | null
  card: string | null
}

const DISPLAY_KIND_PREFIX = 'lifeledger_kind:'

export const renewalKindOptions: RenewalKindOption[] = [
  {
    kind: 'renewal',
    label: 'Renewal',
    description: 'Something renews on this date.',
  },
  {
    kind: 'expiration',
    label: 'Expiration',
    description: 'Something expires on this date.',
  },
  {
    kind: 'review',
    label: 'Review',
    description: 'Review something before a deadline.',
  },
  {
    kind: 'subscription',
    label: 'Subscription',
    description: 'A recurring service or membership renews.',
  },
  {
    kind: 'free_trial',
    label: 'Free trial',
    description: 'Cancel or review before a trial ends.',
  },
  {
    kind: 'warranty',
    label: 'Warranty',
    description: 'Coverage expires on this date.',
  },
  {
    kind: 'document',
    label: 'Document',
    description: 'A document or certification expires.',
  },
]

const renewalDefaults: Record<RenewalDisplayKind, RenewalDefaults> = {
  renewal: {
    repeat: 'Yearly',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'months',
    reminder_time: '09:00',
  },
  expiration: {
    repeat: 'None',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'months',
    reminder_time: '09:00',
  },
  review: {
    repeat: 'None',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'weeks',
    reminder_time: '09:00',
    review_lead_days: 7,
  },
  subscription: {
    repeat: 'Monthly',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'weeks',
    reminder_time: '09:00',
    category: 'Subscriptions',
  },
  free_trial: {
    repeat: 'None',
    priority: 'High',
    reminder_lead_value: 1,
    reminder_lead_unit: 'days',
    reminder_time: '09:00',
    category: 'Subscriptions',
    review_lead_days: 1,
  },
  warranty: {
    repeat: 'None',
    priority: 'Medium',
    reminder_lead_value: 1,
    reminder_lead_unit: 'months',
    reminder_time: '09:00',
  },
  document: {
    repeat: 'None',
    priority: 'Medium',
    reminder_lead_value: 3,
    reminder_lead_unit: 'months',
    reminder_time: '09:00',
  },
}

export function getRenewalDefaults(kind: RenewalDisplayKind): RenewalDefaults {
  return renewalDefaults[kind]
}

export function getBackendRenewalKind(kind: RenewalDisplayKind): RenewalKind {
  if (kind === 'expiration' || kind === 'free_trial' || kind === 'warranty' || kind === 'document') {
    return 'expiration'
  }

  if (kind === 'review') {
    return 'review'
  }

  return 'renewal'
}

export function withRenewalDisplayKind(
  details: RenewalDetailsLike,
  kind: RenewalDisplayKind,
): RenewalDetailsInput {
  return {
    ...details,
    renewal_kind: getBackendRenewalKind(kind),
    frequency: encodeRenewalDisplayKind(kind),
  }
}

export function getRenewalDisplayKind(
  details: RenewalDetailsLike | null | undefined,
  context: { title?: string | null; category?: ReminderCategory | null } = {},
): RenewalDisplayKind {
  const encodedKind = parseRenewalDisplayKind(details?.frequency)
  if (encodedKind) {
    return encodedKind
  }

  const haystack = [
    details?.item_name,
    details?.provider,
    context.title,
    context.category === 'Subscriptions' ? 'subscription' : null,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()

  if (/\btrial\b/.test(haystack)) {
    return 'free_trial'
  }

  if (/\bwarranty\b/.test(haystack)) {
    return 'warranty'
  }

  if (/\b(subscription|membership)\b/.test(haystack)) {
    return 'subscription'
  }

  if (details?.renewal_kind === 'review') {
    return 'review'
  }

  if (details?.renewal_kind === 'expiration') {
    return 'expiration'
  }

  return 'renewal'
}

export function getRenewalKindLabel(kind: RenewalDisplayKind) {
  return renewalKindOptions.find((option) => option.kind === kind)?.label ?? 'Renewal'
}

export function getRenewalItemLabel(kind: RenewalDisplayKind) {
  if (kind === 'subscription' || kind === 'free_trial') {
    return 'Service name'
  }

  if (kind === 'document') {
    return 'Document name'
  }

  return 'Item name'
}

export function getRenewalDateLabel(kind: RenewalDisplayKind) {
  if (kind === 'review') {
    return 'Review by date'
  }

  if (kind === 'subscription') {
    return 'Next renewal date'
  }

  if (kind === 'free_trial') {
    return 'Trial end date'
  }

  if (kind === 'warranty') {
    return 'Warranty expiration date'
  }

  if (kind === 'expiration' || kind === 'document') {
    return 'Expiration date'
  }

  return 'Renewal date'
}

export function getRenewalHelperText(kind: RenewalDisplayKind) {
  if (kind === 'free_trial') {
    return 'Use this to remember to cancel or review before the trial ends.'
  }

  if (kind === 'warranty') {
    return 'Use this to review coverage before it expires.'
  }

  return 'LifeLedger uses this date to show when something renews, expires, or needs review.'
}

export function getRenewalTitle(itemName: string, kind: RenewalDisplayKind) {
  const trimmedName = itemName.trim()
  if (!trimmedName) {
    return 'Renewal reminder'
  }

  if (kind === 'review') {
    return `Review ${trimmedName}`
  }

  if (kind === 'subscription') {
    return /\b(subscription|membership)\b/i.test(trimmedName)
      ? `${trimmedName} renewal`
      : `${trimmedName} subscription renewal`
  }

  if (kind === 'free_trial') {
    return /\btrial\b/i.test(trimmedName) ? `Cancel ${trimmedName}` : `Cancel ${trimmedName} trial`
  }

  if (kind === 'warranty') {
    return /\bwarranty\b/i.test(trimmedName)
      ? `${trimmedName} expiration`
      : `${trimmedName} warranty expiration`
  }

  if (kind === 'expiration' || kind === 'document') {
    return `${trimmedName} expiration`
  }

  if (/\b(insurance|subscription|membership|warranty|certification)\b/i.test(trimmedName)) {
    return `${trimmedName} renewal`
  }

  return `Renew ${trimmedName}`
}

export function isAutoRenewalTitle(currentTitle: string, previousDetails: RenewalDetailsLike) {
  const trimmedTitle = currentTitle.trim()
  const previousKind = getRenewalDisplayKind(previousDetails)
  const previousName = previousDetails.item_name.trim()

  if (!trimmedTitle || trimmedTitle === 'Renewal reminder') {
    return true
  }

  if (!previousName) {
    return false
  }

  const generatedTitles = new Set([
    getRenewalTitle(previousName, previousKind),
    `${previousName} renewal`,
    `${previousName} expiration`,
    `${previousName} expiration reminder`,
    `${previousName} reminder`,
    `${previousName} cancellation reminder`,
    `Renew ${previousName}`,
    `Review ${previousName}`,
  ])

  return generatedTitles.has(trimmedTitle)
}

export function getRelevantRenewalDate(details: RenewalDetailsLike, fallbackDate = '') {
  if (details.renewal_kind === 'expiration') {
    return details.expiration_date || details.renewal_date || fallbackDate
  }

  return details.renewal_date || details.expiration_date || fallbackDate
}

export function getRenewalPreview(input: ReminderInput): RenewalPreview {
  const details = input.renewal_details
  if (!details) {
    return {
      primary: 'Enter an item and date to preview this reminder.',
      reminder: null,
      card: null,
    }
  }

  const itemName = getOwnedItemName(details)
  const relevantDate = getRelevantRenewalDate(details, input.due_date)
  if (!itemName || !relevantDate) {
    return {
      primary: 'Enter an item and date to preview this reminder.',
      reminder: null,
      card: null,
    }
  }

  const displayKind = getRenewalDisplayKind(details, { title: input.title, category: input.category })
  const dateLabel = formatFullDate(relevantDate)
  const previewItemName = itemName || 'This item'
  const primary = getRenewalPreviewPrimary(previewItemName, relevantDate, dateLabel, displayKind, input.repeat)
  const title = input.title.trim() || getRenewalTitle(details.item_name, displayKind)
  const cardLabel = getRenewalCardLabelFromParts(displayKind, relevantDate, input.repeat)

  return {
    primary,
    reminder: `LifeLedger will remind you ${formatReminderTiming(input)}.`,
    card: cardLabel ? `Card: ${title} - ${cardLabel}` : `Card: ${title}`,
  }
}

export function getRenewalValidationMessage(input: ReminderInput) {
  if (input.reminder_type !== 'renewal') {
    return null
  }

  const details = input.renewal_details
  if (!details?.item_name.trim()) {
    return 'Enter an item name.'
  }

  if (!getRelevantRenewalDate(details, input.due_date)) {
    return 'Choose the date you want to track.'
  }

  if (containsSensitiveText([input.title, input.notes, details.item_name, details.owner_name, details.provider])) {
    return 'This field should not include sensitive numbers or passwords.'
  }

  return null
}

export function getRenewalCardSmartLabel(reminder: Reminder) {
  const details = reminder.renewal_details
  if (!details) {
    return reminder.computed_label ?? reminder.renewal_status_label ?? reminder.renewal_window_label
  }

  const displayKind = getRenewalDisplayKind(details, {
    title: reminder.title,
    category: reminder.category,
  })
  const relevantDate = getRelevantRenewalDate(details, reminder.due_date)

  if (!relevantDate) {
    return reminder.computed_label ?? reminder.renewal_status_label ?? reminder.renewal_window_label
  }

  return getRenewalCardLabelFromParts(displayKind, relevantDate, reminder.repeat)
    ?? reminder.computed_label
    ?? reminder.renewal_status_label
    ?? reminder.renewal_window_label
}

function encodeRenewalDisplayKind(kind: RenewalDisplayKind) {
  return `${DISPLAY_KIND_PREFIX}${kind}`
}

function parseRenewalDisplayKind(value: string | null | undefined): RenewalDisplayKind | null {
  if (!value?.startsWith(DISPLAY_KIND_PREFIX)) {
    return null
  }

  const kind = value.slice(DISPLAY_KIND_PREFIX.length)
  return renewalDisplayKinds.includes(kind as RenewalDisplayKind) ? (kind as RenewalDisplayKind) : null
}

function getRenewalPreviewPrimary(
  itemName: string,
  relevantDate: string,
  dateLabel: string,
  kind: RenewalDisplayKind,
  repeat: RepeatOption,
) {
  if (kind === 'expiration' || kind === 'document') {
    return `${itemName} expires on ${dateLabel}.`
  }

  if (kind === 'review') {
    return `Review ${itemName} by ${dateLabel}.`
  }

  if (kind === 'subscription') {
    if (repeat === 'Monthly') {
      return `${itemName} renews on the ${formatOrdinalDay(relevantDate)}.`
    }

    return `${itemName} renews on ${dateLabel}.`
  }

  if (kind === 'free_trial') {
    return `${itemName} trial ends on ${formatShortDate(relevantDate)}.`
  }

  if (kind === 'warranty') {
    return `${itemName} warranty expires on ${dateLabel}.`
  }

  return `${itemName} renews on ${dateLabel}.`
}

function getRenewalCardLabelFromParts(kind: RenewalDisplayKind, relevantDate: string, repeat: RepeatOption) {
  if (kind === 'review') {
    return getReviewLabel(relevantDate)
  }

  if (kind === 'subscription') {
    if (repeat === 'Monthly') {
      return `Renews on the ${formatOrdinalDay(relevantDate)}`
    }

    return getActionDateLabel(relevantDate, 'Subscription renews', 'Subscription renewal overdue by')
  }

  if (kind === 'free_trial') {
    return getActionDateLabel(relevantDate, 'Trial ends', 'Trial ended')
  }

  if (kind === 'warranty') {
    return getActionDateLabel(relevantDate, 'Warranty expires', 'Warranty expired', { monthApproximation: true })
  }

  if (kind === 'document') {
    return getActionDateLabel(relevantDate, 'Document expires', 'Document expired')
  }

  if (kind === 'expiration') {
    return getActionDateLabel(relevantDate, 'Expires', 'Expired')
  }

  return getActionDateLabel(relevantDate, 'Renews', 'Renewal overdue by')
}

function getReviewLabel(value: string) {
  const daysUntil = getDaysUntilDate(value)
  if (daysUntil < 0) {
    return `Review overdue by ${formatCount(Math.abs(daysUntil), 'day')}`
  }

  return `Review ${formatRelativeDatePhrase(value)}`
}

function getActionDateLabel(
  value: string,
  futurePrefix: string,
  pastPrefix: string,
  options: { monthApproximation?: boolean } = {},
) {
  const daysUntil = getDaysUntilDate(value)
  if (daysUntil < 0) {
    const distance = formatCount(Math.abs(daysUntil), 'day')
    return pastPrefix.endsWith('by') ? `${pastPrefix} ${distance}` : `${pastPrefix} ${distance} ago`
  }

  return `${futurePrefix} ${formatRelativeDatePhrase(value, options)}`
}

function getOwnedItemName(details: RenewalDetailsLike) {
  const itemName = details.item_name.trim()
  const ownerName = details.owner_name?.trim()

  if (!itemName || !ownerName || itemName.toLowerCase().includes(ownerName.toLowerCase())) {
    return itemName
  }

  return `${ownerName}'s ${itemName.charAt(0).toLowerCase()}${itemName.slice(1)}`
}

function containsSensitiveText(values: Array<string | null | undefined>) {
  const text = values.filter(Boolean).join(' ')

  return (
    /\b(password|passcode|account number|policy number|card number|credit card|ssn|social security|passport number|license number|vin)\b/i.test(text) ||
    /\b\d{3}-\d{2}-\d{4}\b/.test(text) ||
    /\b(?:\d[ -]?){13,19}\b/.test(text) ||
    /\d{9,}/.test(text)
  )
}

function formatFullDate(value: string) {
  const date = parseDateOnly(value)

  return new Intl.DateTimeFormat(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

function formatShortDate(value: string) {
  const date = parseDateOnly(value)

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(date)
}

function formatOrdinalDay(value: string) {
  const day = parseDateOnly(value).getDate()
  const suffix = day % 10 === 1 && day !== 11
    ? 'st'
    : day % 10 === 2 && day !== 12
      ? 'nd'
      : day % 10 === 3 && day !== 13
        ? 'rd'
        : 'th'

  return `${day}${suffix}`
}

function parseDateOnly(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

