import type { PriorityOption, ReminderCategory, RepeatOption } from './reminder'

export type DefaultDueDateStrategy =
  | 'choose-date'
  | 'next-renewal'
  | 'next-service'
  | 'next-review'
  | 'before-expiration'

export interface LifeAdminTemplate {
  id: string
  title: string
  category: ReminderCategory
  recommendedRepeat: RepeatOption
  recommendedPriority: PriorityOption
  description: string
  suggestedNotes: string
  defaultDueDateStrategy?: DefaultDueDateStrategy
  tags?: string[]
}
