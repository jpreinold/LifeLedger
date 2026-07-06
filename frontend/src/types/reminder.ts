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

export const reminderTypes = ['generic', 'birthday', 'renewal', 'maintenance'] as const

export const reminderAlertReasons = ['Overdue', 'Due today', 'Reminder window'] as const

export const renewalKinds = ['renewal', 'expiration', 'review'] as const

export const maintenanceAreas = ['home', 'vehicle', 'pet', 'health', 'other'] as const

export const maintenanceIntervalUnits = ['days', 'weeks', 'months', 'years'] as const

export type ReminderCategory = (typeof reminderCategories)[number]
export type RepeatOption = (typeof repeatOptions)[number]
export type PriorityOption = (typeof priorityOptions)[number]
export type ReminderLeadUnit = (typeof reminderLeadUnits)[number]
export type ReminderStatus = (typeof reminderStatuses)[number]
export type ReminderType = (typeof reminderTypes)[number]
export type ReminderAlertReason = (typeof reminderAlertReasons)[number]
export type RenewalKind = (typeof renewalKinds)[number]
export type MaintenanceArea = (typeof maintenanceAreas)[number]
export type MaintenanceIntervalUnit = (typeof maintenanceIntervalUnits)[number]

export interface BirthdayDetails {
  person_name: string
  birth_month: number
  birth_day: number
  birth_year: number | null
  age_turning_next_birthday: number | null
  inferred_birth_year: boolean
  relationship: string | null
}

export interface BirthdayDetailsInput {
  person_name: string
  birth_month: number | null
  birth_day: number | null
  birth_year: number | null
  age_turning_next_birthday: number | null
  inferred_birth_year: boolean
  relationship: string | null
}

export interface RenewalDetails {
  item_name: string
  renewal_kind: RenewalKind
  owner_name: string | null
  provider: string | null
  renewal_date: string | null
  expiration_date: string | null
  renewal_window_days: number | null
  review_lead_days: number | null
  frequency: string | null
}

export interface RenewalDetailsInput {
  item_name: string
  renewal_kind: RenewalKind
  owner_name: string | null
  provider: string | null
  renewal_date: string | null
  expiration_date: string | null
  renewal_window_days: number | null
  review_lead_days: number | null
  frequency: string | null
}
export interface MaintenanceDetails {
  item_name: string
  maintenance_area: MaintenanceArea
  last_completed_date: string | null
  interval_value: number | null
  interval_unit: MaintenanceIntervalUnit | null
  next_due_date: string | null
  instructions: string | null
}

export interface MaintenanceDetailsInput {
  item_name: string
  maintenance_area: MaintenanceArea
  last_completed_date: string | null
  interval_value: number | null
  interval_unit: MaintenanceIntervalUnit | null
  next_due_date: string | null
  instructions: string | null
}
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
  reminder_type: ReminderType
  birthday_details: BirthdayDetails | null
  renewal_details: RenewalDetails | null
  maintenance_details: MaintenanceDetails | null
  completed: boolean
  alert_dismissed_until: string | null
  alert_last_seen_at: string | null
  alert_last_action_at: string | null
  alert_snoozed_until: string | null
  status: ReminderStatus
  created_at: string
  updated_at: string
  completed_at: string | null
  next_due_date: string | null
  computed_label: string | null
  birthday_age_label: string | null
  renewal_status_label: string | null
  renewal_window_label: string | null
  maintenance_status_label: string | null
}

export interface ReminderAlert extends Reminder {
  alert_reason: ReminderAlertReason
  alert_reminder_start_date: string | null
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
  reminder_type: ReminderType
  birthday_details: BirthdayDetailsInput | null
  renewal_details: RenewalDetailsInput | null
  maintenance_details: MaintenanceDetailsInput | null
}
