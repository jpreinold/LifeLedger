import {
  entityCapabilityRegistry,
  entityTypeOrder,
  getEntityDefinition,
  getEntityDefinitions,
} from './entityRegistry'
import type {
  DynamicFieldPreset,
  EntityCapabilityDefinition,
  RecordField,
} from './entityRegistry'
import type {
  ProtectedRecordField,
  ProtectedRecordInput,
  LifeRecord,
  RecordInput,
  RecordType,
} from '../types/record'

export type { DynamicFieldPreset, RecordField }
export type RecordTypeDefinition = EntityCapabilityDefinition

export const recordTypeDefinitions = entityCapabilityRegistry
export const recordTypeOptions = getEntityDefinitions(entityTypeOrder)

export const recordFilterOptions = [
  { id: 'all', label: 'All items' },
  ...recordTypeOptions.map((definition) => ({ id: definition.type, label: definition.pluralLabel })),
] as Array<{ id: 'all' | RecordType; label: string }>

export type RecordFilter = 'all' | RecordType

export function getRecordTypeDefinition(type: RecordType | string | null | undefined) {
  return getEntityDefinition(type)
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
    birthday: null,
    location_hint: null,
    notes: null,
    tags: [],
  }
}

export function recordToInput(record: RecordInput | LifeRecord): RecordInput {
  const definition = getRecordTypeDefinition(record.record_type)

  return {
    record_type: record.record_type,
    title: record.title,
    subtitle: record.subtitle,
    category: record.category?.trim() || definition.category,
    owner_name: record.owner_name,
    provider_or_brand: record.provider_or_brand,
    start_date: record.start_date,
    issue_date: record.issue_date,
    expiration_date: record.expiration_date,
    purchase_date: record.purchase_date,
    renewal_date: record.renewal_date,
    birthday: record.birthday ?? null,
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
    category: input.category?.trim() || definition.category,
    owner_name: normalizeOptionalText(input.owner_name),
    provider_or_brand: normalizeOptionalText(input.provider_or_brand),
    start_date: input.start_date || null,
    issue_date: input.issue_date || null,
    expiration_date: input.expiration_date || null,
    purchase_date: input.purchase_date || null,
    renewal_date: input.renewal_date || null,
    birthday: input.birthday || null,
    location_hint: normalizeOptionalText(input.location_hint),
    notes: normalizeOptionalText(input.notes),
    tags: normalizeTags(input.tags),
  }
}

export function hasProtectedRecordInput(input: ProtectedRecordInput) {
  return Object.values(input).some((value) => typeof value === 'string' && value.trim().length > 0)
}

export function getProtectedFieldLabel(field: ProtectedRecordField) {
  for (const definition of Object.values(entityCapabilityRegistry)) {
    const detail = definition.suggestedDetails.find((item) => item.protectedField === field)
    if (detail) return detail.label
  }

  const fallbackLabels: Record<ProtectedRecordField, string> = {
    document_number: 'Document number',
    license_number: 'License number',
    vin: 'VIN',
    policy_number: 'Policy number',
    member_number: 'Member number',
    serial_number: 'Serial number',
    account_reference: 'Account reference',
    sensitive_notes: 'Protected notes',
  }
  return fallbackLabels[field]
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
    if (!tag || seen.has(dedupeKey)) continue

    seen.add(dedupeKey)
    normalized.push(tag.slice(0, 40))
    if (normalized.length >= 12) break
  }

  return normalized
}
