export const recordTypes = [
  'general',
  'passport',
  'driver_license',
  'vehicle',
  'insurance',
  'appliance',
  'pet',
  'home',
  'subscription',
  'warranty',
] as const

export const recordStatuses = ['active', 'archived'] as const

export type RecordType = (typeof recordTypes)[number]
export type RecordStatus = (typeof recordStatuses)[number]

export interface LifeRecord {
  id: string
  record_type: RecordType
  title: string
  subtitle: string | null
  category: string
  owner_name: string | null
  provider_or_brand: string | null
  start_date: string | null
  issue_date: string | null
  expiration_date: string | null
  purchase_date: string | null
  renewal_date: string | null
  location_hint: string | null
  notes: string | null
  tags: string[]
  status: RecordStatus
  has_protected_data: boolean
  protected_field_names: ProtectedRecordField[]
  created_at: string
  updated_at: string
}

export interface RecordInput {
  record_type: RecordType
  title: string
  subtitle: string | null
  category: string
  owner_name: string | null
  provider_or_brand: string | null
  start_date: string | null
  issue_date: string | null
  expiration_date: string | null
  purchase_date: string | null
  renewal_date: string | null
  location_hint: string | null
  notes: string | null
  tags: string[]
}

export type ProtectedRecordField =
  | 'document_number'
  | 'license_number'
  | 'vin'
  | 'policy_number'
  | 'member_number'
  | 'serial_number'
  | 'account_reference'
  | 'sensitive_notes'

export type ProtectedRecordInput = Partial<Record<ProtectedRecordField, string | null>>

export interface ProtectedRecordStatus {
  has_protected_data: boolean
  protected_field_names: ProtectedRecordField[]
  protected_encryption_version: number | null
  protected_updated_at: string | null
}

export interface ProtectedRecordPayload {
  document_number: string | null
  license_number: string | null
  vin: string | null
  policy_number: string | null
  member_number: string | null
  serial_number: string | null
  account_reference: string | null
  sensitive_notes: string | null
}
