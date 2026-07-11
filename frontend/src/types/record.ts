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
