import type { RecordType } from './record'
import type { ReminderType } from './reminder'

export const relationshipTypes = [
  'related',
  'belongs_to',
  'covers',
  'renews',
  'maintains',
  'insures',
  'warranty_for',
  'document_for',
  'appointment_for',
  'custom',
] as const

export type LinkedEntityType = 'record' | 'reminder'
export type RelationshipType = (typeof relationshipTypes)[number]
export type LinkDirection = 'outbound' | 'inbound'

export interface LinkedEntitySummary {
  entity_type: LinkedEntityType
  id: string
  title: string
  subtitle: string | null
  record_type: RecordType | null
  reminder_type: ReminderType | null
  status: string | null
  due_date: string | null
}

export interface LinkedItem {
  link_id: string
  relationship_type: RelationshipType
  label: string | null
  direction: LinkDirection
  linked_entity: LinkedEntitySummary
  created_at: string
}

export interface LinkedItemsResponse {
  records: LinkedItem[]
  reminders: LinkedItem[]
}

export interface LinkCreateRequest {
  target_type: LinkedEntityType
  target_id: string
  relationship_type?: RelationshipType
  label?: string | null
}

export const relationshipLabels: Record<RelationshipType, string> = {
  related: 'Related to',
  belongs_to: 'Belongs to',
  covers: 'Covers',
  renews: 'Reminder for',
  maintains: 'Maintenance for',
  insures: 'Insurance for',
  warranty_for: 'Warranty for',
  document_for: 'Document for',
  appointment_for: 'Appointment for',
  custom: 'Custom',
}
