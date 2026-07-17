import type { RecordType } from './record'
import type { ReminderType } from './reminder'

export const relationshipTypes = [
  'related_to',
  'related',
  'belongs_to',
  'owned_by',
  'covers',
  'provided_by',
  'reminder_for',
  'renews',
  'maintains',
  'insures',
  'warranty_for',
  'document_for',
  'appointment_for',
  'associated_with',
  'custom',
] as const

export type LinkedEntityType = 'record' | 'reminder' | 'document'
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
  date: string | null
  document_record_id: string | null
  content_type: string | null
  size_bytes: number | null
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
  documents: LinkedItem[]
}

export interface LinkCreateRequest {
  target_type: LinkedEntityType
  target_id: string
  relationship_type?: RelationshipType
  label?: string | null
}

export interface RelationshipCreateRequest {
  source_item_type: LinkedEntityType
  source_item_id: string
  target_item_type: LinkedEntityType
  target_item_id: string
  relationship_type?: RelationshipType
  custom_label?: string | null
}

export interface RelationshipUpdateRequest {
  relationship_type?: RelationshipType
  custom_label?: string | null
}

export interface RelationshipResponse {
  relationship_id: string
  relationship_type: RelationshipType
  custom_label: string | null
  source_item: LinkedEntitySummary
  target_item: LinkedEntitySummary
  created_at: string
  updated_at: string
}

export interface RelationshipCandidate {
  item_type: LinkedEntityType
  item_id: string
  title: string
  subtitle: string | null
  status: string | null
  date: string | null
  record_type: RecordType | null
  reminder_type: ReminderType | null
  document_record_id: string | null
  disabled_reason: string | null
}

export interface RelationshipCandidatesResponse {
  items: RelationshipCandidate[]
}

export const relationshipLabels: Record<RelationshipType, string> = {
  related_to: 'Related to',
  related: 'Related to',
  belongs_to: 'Belongs to',
  owned_by: 'Owned by',
  covers: 'Covers',
  provided_by: 'Provided by',
  reminder_for: 'Reminder for',
  renews: 'Reminder for',
  maintains: 'Maintenance for',
  insures: 'Insurance for',
  warranty_for: 'Warranty for',
  document_for: 'Document for',
  appointment_for: 'Appointment for',
  associated_with: 'Associated with',
  custom: 'Custom',
}
