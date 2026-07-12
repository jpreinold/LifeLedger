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

export const dynamicFieldTypes = [
  'short_text',
  'long_text',
  'date',
  'number',
  'money',
  'phone',
  'email',
  'url',
  'boolean',
  'select',
] as const

export type DynamicFieldType = (typeof dynamicFieldTypes)[number]
export type DynamicFieldValue = string | number | boolean | null

export interface DynamicRecordField {
  field_id: string
  key: string
  label: string
  field_type: DynamicFieldType
  value: DynamicFieldValue
  is_sensitive: boolean
  has_value: boolean
  display_order: number
  select_options: string[]
  created_at: string
  updated_at: string
}

export interface DynamicRecordFieldInput {
  key?: string | null
  label: string
  field_type: DynamicFieldType
  value?: DynamicFieldValue
  is_sensitive?: boolean
  select_options?: string[]
  display_order?: number | null
}

export interface DynamicRecordFieldUpdateInput {
  label?: string
  field_type?: DynamicFieldType
  value?: DynamicFieldValue
  is_sensitive?: boolean
  select_options?: string[]
  display_order?: number | null
}

export interface DynamicRecordFieldReveal {
  field_id: string
  value: DynamicFieldValue
}
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
  dynamic_fields: DynamicRecordField[]
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

export type RecordAttachmentStatus =
  | 'pending_upload'
  | 'uploaded'
  | 'scanning'
  | 'available'
  | 'rejected'
  | 'scan_failed'
  | 'deleting'
  | 'deleted'

export type RecordAttachmentScanResult =
  | 'pending'
  | 'no_threats_found'
  | 'threats_found'
  | 'unsupported'
  | 'access_denied'
  | 'failed'

export interface RecordAttachment {
  attachment_id: string
  record_id: string
  display_name: string
  content_type: 'application/pdf' | 'image/jpeg' | 'image/png'
  size_bytes: number
  status: RecordAttachmentStatus
  scan_result: RecordAttachmentScanResult | null
  created_at: string
  uploaded_at: string | null
  scan_completed_at: string | null
  available_at: string | null
  deleted_at: string | null
}

export interface RecordAttachmentUploadIntentInput {
  filename: string
  content_type: string
  size_bytes: number
}

export interface PresignedPostUpload {
  url: string
  fields: Record<string, string>
}

export interface RecordAttachmentUploadIntent {
  attachment_id: string
  upload: PresignedPostUpload
  expires_at: string
  max_size_bytes: number
}

export interface RecordAttachmentDownloadUrl {
  url: string
  expires_at: string
}
