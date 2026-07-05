import type { PriorityOption, ReminderCategory, ReminderLeadUnit, ReminderType, RenewalKind, RepeatOption } from './reminder'

export type DefaultDueDateStrategy =
  | 'choose-date'
  | 'next-renewal'
  | 'next-service'
  | 'next-review'
  | 'before-expiration'

export interface TemplateReminderTiming {
  reminder_lead_value: number
  reminder_lead_unit: ReminderLeadUnit
  reminder_time?: string
}

export interface LifeAdminTemplate {
  id: string
  title: string
  category: ReminderCategory
  recommendedRepeat: RepeatOption
  recommendedPriority: PriorityOption
  description: string
  suggestedNotes: string
  defaultDueDateStrategy?: DefaultDueDateStrategy
  suggestedReminderTiming?: TemplateReminderTiming
  smartType?: ReminderType
  smartBadge?: string
  renewalKind?: RenewalKind
  renewalItemName?: string
  renewalWindowDays?: number
  reviewLeadDays?: number
  tags?: string[]
}
