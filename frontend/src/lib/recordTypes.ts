import {
  BadgeCheck,
  Car,
  FileText,
  Home,
  HousePlug,
  PawPrint,
  RefreshCcw,
  ShieldCheck,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type { DynamicFieldType, ProtectedRecordField, ProtectedRecordInput, RecordInput, RecordType } from '../types/record'

export type RecordField =
  | 'subtitle'
  | 'owner_name'
  | 'provider_or_brand'
  | 'start_date'
  | 'issue_date'
  | 'expiration_date'
  | 'purchase_date'
  | 'renewal_date'
  | 'location_hint'
  | 'notes'
  | 'tags'

export interface DynamicFieldPreset {
  key: string
  label: string
  field_type: DynamicFieldType
  is_sensitive?: boolean
  select_options?: string[]
  description?: string
  display_order?: number
}

export interface RecordTypeDefinition {
  type: RecordType
  label: string
  icon: LucideIcon
  category: 'General' | 'Documents' | 'Vehicle' | 'Home' | 'Pet' | 'Subscription' | 'Warranty'
  description: string
  defaultTitle: string
  tone: 'other' | 'car' | 'finance' | 'home' | 'family' | 'subscriptions' | 'health'
  fields: RecordField[]
  coreFields: Array<'title' | RecordField>
  defaultSuggestedFields: RecordField[]
  dynamicFieldPresets: DynamicFieldPreset[]
  protectedFields: ProtectedRecordField[]
  labels?: Partial<Record<RecordField, string>>
  placeholders?: Partial<Record<RecordField, string>>
}

export const recordTypeDefinitions: Record<RecordType, RecordTypeDefinition> = {
  general: {
    type: 'general',
    label: 'General',
    icon: FileText,
    category: 'General',
    description: 'A flexible record for important details.',
    defaultTitle: 'Important record',
    tone: 'other',
    protectedFields: ['sensitive_notes'],
    fields: [
      'subtitle',
      'owner_name',
      'provider_or_brand',
      'start_date',
      'expiration_date',
      'location_hint',
      'notes',
      'tags',
    ],
    coreFields: ['title'],
    defaultSuggestedFields: ['subtitle', 'owner_name', 'provider_or_brand'],
    dynamicFieldPresets: [
      { key: 'date', label: 'Date', field_type: 'date', description: 'A useful date for this record.', display_order: 200 },
      { key: 'sensitive_notes', label: 'Sensitive notes', field_type: 'long_text', is_sensitive: true, description: 'Encrypted before storage and hidden until explicit reveal.', display_order: 900 },
    ],
  },
  passport: {
    type: 'passport',
    label: 'Passport',
    icon: BadgeCheck,
    category: 'Documents',
    description: 'Track dates and issuing details, with an optional protected document number.',
    defaultTitle: 'Passport',
    tone: 'other',
    protectedFields: ['document_number'],
    fields: ['owner_name', 'provider_or_brand', 'issue_date', 'expiration_date', 'location_hint', 'notes', 'tags'],
    coreFields: ['title', 'owner_name', 'expiration_date'],
    defaultSuggestedFields: ['owner_name', 'provider_or_brand', 'expiration_date'],
    dynamicFieldPresets: [
      { key: 'document_number', label: 'Passport number', field_type: 'short_text', is_sensitive: true, description: 'Encrypted before storage and hidden until explicit reveal.', display_order: 110 },
      { key: 'nationality', label: 'Nationality', field_type: 'short_text', display_order: 140 },
    ],
    labels: { provider_or_brand: 'Issuing country' },
    placeholders: { provider_or_brand: 'United States' },
  },
  driver_license: {
    type: 'driver_license',
    label: 'Driver license',
    icon: BadgeCheck,
    category: 'Documents',
    description: 'Track dates and issuing authority, with an optional protected license number.',
    defaultTitle: 'Driver license',
    tone: 'other',
    protectedFields: ['license_number'],
    fields: ['owner_name', 'provider_or_brand', 'issue_date', 'expiration_date', 'location_hint', 'notes', 'tags'],
    coreFields: ['title', 'owner_name', 'expiration_date'],
    defaultSuggestedFields: ['owner_name', 'provider_or_brand', 'expiration_date'],
    dynamicFieldPresets: [
      { key: 'license_number', label: 'License number', field_type: 'short_text', is_sensitive: true, description: 'Encrypted before storage and hidden until explicit reveal.', display_order: 110 },
      { key: 'class', label: 'Class', field_type: 'short_text', display_order: 140 },
      { key: 'restrictions', label: 'Restrictions', field_type: 'short_text', display_order: 150 },
      { key: 'real_id', label: 'Real ID', field_type: 'boolean', display_order: 160 },
    ],
    labels: { provider_or_brand: 'Issuing state or authority' },
    placeholders: { provider_or_brand: 'Maryland' },
  },
  vehicle: {
    type: 'vehicle',
    label: 'Vehicle',
    icon: Car,
    category: 'Vehicle',
    description: 'Track a vehicle by name, owner, brand, dates, and safe notes.',
    defaultTitle: 'Vehicle',
    tone: 'car',
    protectedFields: ['vin'],
    fields: ['subtitle', 'owner_name', 'provider_or_brand', 'purchase_date', 'location_hint', 'notes', 'tags'],
    coreFields: ['title', 'provider_or_brand'],
    defaultSuggestedFields: ['subtitle', 'provider_or_brand'],
    dynamicFieldPresets: [
      { key: 'year', label: 'Year', field_type: 'number', display_order: 110 },
      { key: 'model', label: 'Model', field_type: 'short_text', display_order: 120 },
      { key: 'vin', label: 'VIN', field_type: 'short_text', is_sensitive: true, description: 'Encrypted before storage and hidden until explicit reveal.', display_order: 130 },
      { key: 'color', label: 'Color', field_type: 'short_text', display_order: 140 },
      { key: 'purchase_price', label: 'Purchase price', field_type: 'money', display_order: 150 },
      { key: 'mileage', label: 'Mileage', field_type: 'number', display_order: 160 },
      { key: 'license_plate', label: 'License plate', field_type: 'short_text', is_sensitive: true, display_order: 170 },
    ],
    labels: { provider_or_brand: 'Make or brand' },
    placeholders: { subtitle: 'Daily driver', provider_or_brand: 'Toyota' },
  },
  insurance: {
    type: 'insurance',
    label: 'Insurance',
    icon: ShieldCheck,
    category: 'Documents',
    description: 'Track provider and dates, with optional protected policy or member numbers.',
    defaultTitle: 'Insurance',
    tone: 'finance',
    protectedFields: ['policy_number', 'member_number'],
    fields: ['subtitle', 'owner_name', 'provider_or_brand', 'start_date', 'renewal_date', 'expiration_date', 'notes', 'tags'],
    coreFields: ['title', 'provider_or_brand'],
    defaultSuggestedFields: ['provider_or_brand', 'renewal_date', 'expiration_date'],
    dynamicFieldPresets: [
      { key: 'policy_number', label: 'Policy number', field_type: 'short_text', is_sensitive: true, display_order: 110 },
      { key: 'member_number', label: 'Member number', field_type: 'short_text', is_sensitive: true, display_order: 120 },
      { key: 'coverage', label: 'Coverage', field_type: 'short_text', display_order: 130 },
    ],
    labels: { provider_or_brand: 'Provider' },
    placeholders: { provider_or_brand: 'Insurer' },
  },
  appliance: {
    type: 'appliance',
    label: 'Appliance',
    icon: HousePlug,
    category: 'Home',
    description: 'Track brand, purchase date, warranty date, and where it lives.',
    defaultTitle: 'Appliance',
    tone: 'home',
    protectedFields: ['serial_number'],
    fields: ['subtitle', 'provider_or_brand', 'purchase_date', 'expiration_date', 'location_hint', 'notes', 'tags'],
    coreFields: ['title', 'provider_or_brand'],
    defaultSuggestedFields: ['provider_or_brand', 'purchase_date', 'expiration_date'],
    dynamicFieldPresets: [
      { key: 'serial_number', label: 'Serial number', field_type: 'short_text', is_sensitive: true, display_order: 110 },
      { key: 'model_number', label: 'Model number', field_type: 'short_text', display_order: 120 },
    ],
    labels: { provider_or_brand: 'Brand', expiration_date: 'Warranty expiration' },
    placeholders: { provider_or_brand: 'Bosch' },
  },
  pet: {
    type: 'pet',
    label: 'Pet',
    icon: PawPrint,
    category: 'Pet',
    description: 'Track a pet record with safe notes and dates.',
    defaultTitle: 'Pet',
    tone: 'family',
    protectedFields: [],
    fields: ['subtitle', 'owner_name', 'start_date', 'notes', 'tags'],
    coreFields: ['title'],
    defaultSuggestedFields: ['owner_name', 'start_date'],
    dynamicFieldPresets: [
      { key: 'microchip', label: 'Microchip', field_type: 'short_text', is_sensitive: true, display_order: 110 },
      { key: 'vet', label: 'Vet', field_type: 'short_text', display_order: 120 },
    ],
    labels: { start_date: 'Adoption or start date' },
  },
  home: {
    type: 'home',
    label: 'Home',
    icon: Home,
    category: 'Home',
    description: 'Track home details without requiring a full sensitive address.',
    defaultTitle: 'Home',
    tone: 'home',
    protectedFields: [],
    fields: ['subtitle', 'purchase_date', 'start_date', 'location_hint', 'notes', 'tags'],
    coreFields: ['title'],
    defaultSuggestedFields: ['location_hint', 'purchase_date'],
    dynamicFieldPresets: [
      { key: 'home_type', label: 'Home type', field_type: 'short_text', display_order: 110 },
      { key: 'year_built', label: 'Year built', field_type: 'number', display_order: 120 },
    ],
    labels: { location_hint: 'Location hint' },
    placeholders: { location_hint: 'City, neighborhood, or nickname' },
  },
  subscription: {
    type: 'subscription',
    label: 'Subscription',
    icon: RefreshCcw,
    category: 'Subscription',
    description: 'Track provider, start date, and renewal date without payment details.',
    defaultTitle: 'Subscription',
    tone: 'subscriptions',
    protectedFields: ['account_reference'],
    fields: ['subtitle', 'provider_or_brand', 'start_date', 'renewal_date', 'notes', 'tags'],
    coreFields: ['title', 'provider_or_brand'],
    defaultSuggestedFields: ['provider_or_brand', 'renewal_date'],
    dynamicFieldPresets: [
      { key: 'account_reference', label: 'Account reference', field_type: 'short_text', is_sensitive: true, display_order: 110 },
      { key: 'cost', label: 'Cost', field_type: 'money', display_order: 120 },
      { key: 'billing_cycle', label: 'Billing cycle', field_type: 'select', select_options: ['Monthly', 'Quarterly', 'Yearly'], display_order: 130 },
    ],
    labels: { provider_or_brand: 'Provider' },
    placeholders: { provider_or_brand: 'Streaming service' },
  },
  warranty: {
    type: 'warranty',
    label: 'Warranty',
    icon: Wrench,
    category: 'Warranty',
    description: 'Track purchase and expiration dates, warranty files, and service details.',
    defaultTitle: 'Warranty',
    tone: 'health',
    protectedFields: ['serial_number'],
    fields: ['subtitle', 'provider_or_brand', 'purchase_date', 'expiration_date', 'notes', 'tags'],
    coreFields: ['title', 'provider_or_brand'],
    defaultSuggestedFields: ['provider_or_brand', 'purchase_date', 'expiration_date'],
    dynamicFieldPresets: [
      { key: 'serial_number', label: 'Serial number', field_type: 'short_text', is_sensitive: true, display_order: 110 },
      { key: 'coverage', label: 'Coverage', field_type: 'short_text', display_order: 120 },
    ],
    labels: { provider_or_brand: 'Brand or provider' },
  },
}

export const recordTypeOptions = Object.values(recordTypeDefinitions)

export const recordFilterOptions = [
  { id: 'all', label: 'All' },
  { id: 'General', label: 'General' },
  { id: 'Documents', label: 'Documents' },
  { id: 'Vehicle', label: 'Vehicle' },
  { id: 'Home', label: 'Home' },
  { id: 'Pet', label: 'Pet' },
  { id: 'Subscription', label: 'Subscription' },
  { id: 'Warranty', label: 'Warranty' },
] as const

export type RecordFilter = (typeof recordFilterOptions)[number]['id']

export function getRecordTypeDefinition(type: RecordType) {
  return recordTypeDefinitions[type] ?? recordTypeDefinitions.general
}

export function createRecordInput(type: RecordType): RecordInput {
  const definition = getRecordTypeDefinition(type)

  return {
    record_type: type,
    title: '',
    subtitle: null,
    category: definition.category,
    owner_name: null,
    provider_or_brand: null,
    start_date: null,
    issue_date: null,
    expiration_date: null,
    purchase_date: null,
    renewal_date: null,
    location_hint: null,
    notes: null,
    tags: [],
  }
}

export function recordToInput(record: RecordInput): RecordInput {
  const definition = getRecordTypeDefinition(record.record_type)

  return {
    record_type: record.record_type,
    title: record.title,
    subtitle: record.subtitle,
    category: record.category || definition.category,
    owner_name: record.owner_name,
    provider_or_brand: record.provider_or_brand,
    start_date: record.start_date,
    issue_date: record.issue_date,
    expiration_date: record.expiration_date,
    purchase_date: record.purchase_date,
    renewal_date: record.renewal_date,
    location_hint: record.location_hint,
    notes: record.notes,
    tags: [...record.tags],
  }
}

export function normalizeRecordInput(input: RecordInput): RecordInput {
  const definition = getRecordTypeDefinition(input.record_type)

  return {
    record_type: input.record_type,
    title: input.title.trim(),
    subtitle: normalizeOptionalText(input.subtitle),
    category: definition.category,
    owner_name: normalizeOptionalText(input.owner_name),
    provider_or_brand: normalizeOptionalText(input.provider_or_brand),
    start_date: input.start_date || null,
    issue_date: input.issue_date || null,
    expiration_date: input.expiration_date || null,
    purchase_date: input.purchase_date || null,
    renewal_date: input.renewal_date || null,
    location_hint: normalizeOptionalText(input.location_hint),
    notes: normalizeOptionalText(input.notes),
    tags: normalizeTags(input.tags),
  }
}

export function hasProtectedRecordInput(input: ProtectedRecordInput) {
  return Object.values(input).some((value) => typeof value === 'string' && value.trim().length > 0)
}

export function getProtectedFieldLabel(field: ProtectedRecordField) {
  const labels: Record<ProtectedRecordField, string> = {
    document_number: 'Document number',
    license_number: 'License number',
    vin: 'VIN',
    policy_number: 'Policy number',
    member_number: 'Member number',
    serial_number: 'Serial number',
    account_reference: 'Account reference',
    sensitive_notes: 'Sensitive notes',
  }

  return labels[field]
}

export function tagsToText(tags: string[]) {
  return tags.join(', ')
}

export function tagsFromText(value: string) {
  return normalizeTags(value.split(','))
}

function normalizeOptionalText(value: string | null) {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

function normalizeTags(tags: string[]) {
  const normalized: string[] = []
  const seen = new Set<string>()

  for (const item of tags) {
    const tag = item.trim()
    const dedupeKey = tag.toLocaleLowerCase()
    if (!tag || seen.has(dedupeKey)) {
      continue
    }

    seen.add(dedupeKey)
    normalized.push(tag.slice(0, 40))

    if (normalized.length >= 12) {
      break
    }
  }

  return normalized
}
