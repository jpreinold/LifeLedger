import { getEntityDefinition } from './entityRegistry'
import type { EntitySection } from './entityRegistry'
import type { LinkedEntityType, RelationshipType } from '../types/linkedItem'
import type { RecordType } from '../types/record'

export const productTerms = {
  item: 'Item',
  items: 'Items',
  addItem: 'Add item',
  itemType: 'Item type',
  detail: 'Detail',
  details: 'Details',
  addDetail: 'Add another detail',
  protectedDetail: 'Protected detail',
  protectedDetails: 'Protected details',
  responsibility: 'Responsibility',
  responsibilities: 'Responsibilities',
  reminder: 'Reminder',
  reminders: 'Reminders',
  document: 'Document',
  documents: 'Documents',
  addDocument: 'Add document',
  relatedItem: 'Related item',
  relatedItems: 'Related items',
  addRelatedItem: 'Add related item',
  owner: 'Owner',
  provider: 'Provider',
} as const

export function getEntityTypeLabel(type: RecordType | string | null | undefined) {
  return getEntityDefinition(type).singularLabel
}

export function getEntityTypePluralLabel(type: RecordType | string | null | undefined) {
  return getEntityDefinition(type).pluralLabel
}

export function getEntityActionLabel(type: RecordType | string | null | undefined, action: 'create' | 'edit' | 'delete') {
  const definition = getEntityDefinition(type)
  if (action === 'create') return definition.createActionLabel
  if (action === 'edit') return `Edit ${definition.singularLabel.toLocaleLowerCase()}`
  return `Delete ${definition.singularLabel.toLocaleLowerCase()}`
}

export function getSectionLabel(section: EntitySection) {
  const labels: Record<EntitySection, string> = {
    overview: 'Overview',
    details: 'Details',
    responsibilities: productTerms.responsibilities,
    documents: productTerms.documents,
    relatedItems: productTerms.relatedItems,
  }
  return labels[section]
}

export function getRelationshipPresentation(type: RelationshipType | string | null | undefined) {
  const labels: Record<RelationshipType, string> = {
    related_to: 'Related to',
    related: 'Related to',
    belongs_to: 'Belongs to',
    owned_by: 'Owned by',
    covers: 'Covers',
    provided_by: 'Provided by',
    reminder_for: 'Responsibility for',
    renews: 'Renews',
    maintains: 'Maintenance for',
    insures: 'Insurance for',
    warranty_for: 'Warranty for',
    document_for: 'Document for',
    appointment_for: 'Appointment for',
    associated_with: 'Related to',
    custom: 'Related to',
  }
  return type && type in labels ? labels[type as RelationshipType] : 'Related to'
}

export function getResponsibilityPresentation(context: 'global' | 'item') {
  return context === 'item'
    ? { singular: productTerms.responsibility, plural: productTerms.responsibilities, add: 'Add responsibility' }
    : { singular: productTerms.reminder, plural: productTerms.reminders, add: 'Add reminder' }
}

export function getSearchResultTypeLabel(
  sourceType: LinkedEntityType,
  recordType?: RecordType | string | null,
) {
  if (sourceType === 'record') return getEntityTypeLabel(recordType)
  if (sourceType === 'document') return productTerms.document
  return productTerms.reminder
}

export function getCategoryPresentation(recordType: RecordType | string | null | undefined, category: string | null | undefined) {
  const normalized = normalizeLabel(category)
  if (!normalized) return null
  const definition = getEntityDefinition(recordType)
  const redundant = new Set([
    normalizeLabel(definition.singularLabel),
    normalizeLabel(definition.pluralLabel),
    normalizeLabel(definition.internalRecordType.replace(/_/g, ' ')),
    ...definition.legacyDuplicateCategories.map(normalizeLabel),
  ])
  return redundant.has(normalized) ? null : category?.trim() || null
}

export function translateApiPresentationMessage(message: string) {
  return message
    .replace(/\bLinked items\b/g, productTerms.relatedItems)
    .replace(/\blinked items\b/g, 'related items')
    .replace(/\bCustom fields\b/g, 'Additional details')
    .replace(/\bcustom fields\b/g, 'additional details')
    .replace(/\bAttachments\b/g, productTerms.documents)
    .replace(/\battachments\b/g, 'documents')
    .replace(/\bAttachment\b/g, productTerms.document)
    .replace(/\battachment\b/g, 'document')
    .replace(/\bRecords\b/g, productTerms.items)
    .replace(/\brecords\b/g, 'items')
    .replace(/\bRecord\b/g, productTerms.item)
    .replace(/\brecord\b/g, 'item')
}

function normalizeLabel(value: string | null | undefined) {
  return value?.trim().toLocaleLowerCase().replace(/[_-]+/g, ' ') ?? ''
}
