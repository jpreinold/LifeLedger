export const reminderCategories = [
  'Car',
  'Health',
  'Finance',
  'Home',
  'Family',
  'Subscriptions',
  'Other',
] as const

export const repeatOptions = ['None', 'Weekly', 'Monthly', 'Quarterly', 'Yearly'] as const

export const priorityOptions = ['Low', 'Medium', 'High'] as const

export const reminderLeadUnits = ['days', 'weeks', 'months'] as const

export const reminderStatuses = [
  'Completed',
  'Overdue',
  'Due today',
  'Due this week',
  'Due this month',
  'Upcoming',
] as const

export type ReminderCategory = (typeof reminderCategories)[number]
export type RepeatOption = (typeof repeatOptions)[number]
export type PriorityOption = (typeof priorityOptions)[number]
export type ReminderLeadUnit = (typeof reminderLeadUnits)[number]
export type ReminderStatus = (typeof reminderStatuses)[number]

export interface Reminder {
  id: string
  title: string
  category: ReminderCategory
  due_date: string
  repeat: RepeatOption
  priority: PriorityOption
  notes: string | null
  reminder_lead_value: number | null
  reminder_lead_unit: ReminderLeadUnit | null
  reminder_time: string | null
  completed: boolean
  status: ReminderStatus
  created_at: string
  updated_at: string
  completed_at: string | null
  next_due_date: string | null
}

export interface ReminderInput {
  title: string
  category: ReminderCategory
  due_date: string
  repeat: RepeatOption
  priority: PriorityOption
  notes: string | null
  reminder_lead_value: number | null
  reminder_lead_unit: ReminderLeadUnit | null
  reminder_time: string | null
}
