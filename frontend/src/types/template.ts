import type { PriorityOption, ReminderCategory, ReminderLeadUnit, RepeatOption } from './reminder'
import type { RenewalDisplayKind } from '../lib/renewalUx'

export type DefaultDueDateStrategy =
  | 'choose-date'
  | 'next-renewal'
  | 'next-service'
  | 'next-review'
  | 'before-expiration'

export type TemplateTargetType = 'generic' | 'birthday' | 'renewal' | 'comingSoon'

export type TemplateFilterGroup =
  | 'Smart'
  | 'Dates & People'
  | 'Vehicle'
  | 'Home'
  | 'Health'
  | 'Finance'
  | 'Subscriptions'
  | 'Documents'
  | 'Maintenance'
  | 'Coming soon'

export interface TemplateReminderTiming {
  reminder_lead_value: number
  reminder_lead_unit: ReminderLeadUnit
  reminder_time?: string
}

export interface LifeAdminTemplate {
  id: string
  title: string
  category: ReminderCategory
  targetType: TemplateTargetType
  targetKind?: RenewalDisplayKind
  comingSoonLabel?: string
  recommendedRepeat: RepeatOption
  recommendedPriority: PriorityOption
  description: string
  suggestedNotes: string
  defaultDueDateStrategy?: DefaultDueDateStrategy
  defaultReminderTiming?: TemplateReminderTiming
  smartBadge?: string
  renewalItemName?: string
  renewalWindowDays?: number
  reviewLeadDays?: number
  featured?: boolean
  filterGroups?: TemplateFilterGroup[]
  tags?: string[]
}
