import type { PriorityOption, ReminderCategory, ReminderLeadUnit, RepeatOption } from './reminder'

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
  tags?: string[]
}
