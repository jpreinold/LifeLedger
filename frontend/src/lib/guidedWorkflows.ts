import { BadgeCheck, Car, PawPrint, RefreshCcw } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type { EntityCapabilityDefinition, SuggestedDetailDefinition } from './entityRegistry'
import { getEntityDefinition } from './entityRegistry'
import { createMaintenanceReminderInput, createRenewalReminderInput, emptyMaintenanceDetails, emptyRenewalDetails } from './reminderInput'
import { createRecordInput, recordToInput } from './recordTypes'
import type { RelationshipType } from '../types/linkedItem'
import type {
  DynamicFieldType,
  DynamicRecordField,
  DynamicRecordFieldInput,
  DynamicRecordFieldUpdateInput,
  LifeRecord,
  ProtectedRecordField,
  ProtectedRecordInput,
  RecordInput,
  RecordType,
} from '../types/record'
import type { ReminderInput, ReminderLeadUnit, ReminderType, RepeatOption } from '../types/reminder'

export const guidedWorkflowIds = [
  'passport_expiration',
  'vehicle_registration',
  'pet_vaccination',
  'subscription_renewal',
] as const

export type GuidedWorkflowId = (typeof guidedWorkflowIds)[number]
export type GuidedWorkflowStep = 'item' | 'details' | 'responsibility' | 'document' | 'review'
export type GuidedWorkflowValues = Record<string, string>
export type GuidedInputType = 'text' | 'date' | 'number' | 'money' | 'select' | 'password' | 'url' | 'textarea'
export type GuidedRecordField = Exclude<keyof RecordInput, 'record_type' | 'category' | 'tags' | 'birthday_inferred_birth_year'>

export interface GuidedWorkflowField {
  id: string
  label: string
  reviewLabel: string
  step: 'details' | 'responsibility'
  inputType: GuidedInputType
  required: boolean
  placeholder?: string
  helperText?: string
  options?: string[]
  suggestions?: string[]
  registryDetailKey?: string
  recordField?: GuidedRecordField
  dynamicDetailKey?: string
  protectedField?: ProtectedRecordField
  protected: boolean
  searchable: boolean
}

export interface GuidedReminderConfiguration {
  type: ReminderType
  title: string
  defaultLeadValue: number
  defaultLeadUnit: ReminderLeadUnit
  defaultRepeat: RepeatOption
}

export interface GuidedWorkflowDefinition {
  id: GuidedWorkflowId
  title: string
  shortDescription: string
  intentLabel: string
  icon: LucideIcon
  associatedItemType: RecordType
  existingItemCanBeUsed: boolean
  newItemCanBeCreated: boolean
  itemTitleConfiguration: {
    label: string
    placeholder: string
    reviewLabel: string
    mirrorRecordField?: GuidedRecordField
  }
  requiredSteps: GuidedWorkflowStep[]
  fields: GuidedWorkflowField[]
  responsibilityConfiguration: GuidedReminderConfiguration
  documentPrompt: {
    title: string
    description: string
    privacyGuidance: string
    optional: true
  }
  relationshipDefaults: {
    type: RelationshipType
    presentation: string
  }
  reviewPresentation: {
    title: string
    saveLabel: string
  }
  completionPresentation: {
    title: string
  }
  defaultValues: GuidedWorkflowValues
}

const scheduleDefaults = (leadValue: number, leadUnit: ReminderLeadUnit, repeat: RepeatOption): GuidedWorkflowValues => ({
  reminder_lead_value: String(leadValue),
  reminder_lead_unit: leadUnit,
  reminder_repeat: repeat,
})

const field = (
  id: string,
  label: string,
  step: GuidedWorkflowField['step'],
  inputType: GuidedInputType,
  options: Partial<GuidedWorkflowField> = {},
): GuidedWorkflowField => ({
  id,
  label,
  reviewLabel: label,
  step,
  inputType,
  required: false,
  protected: false,
  searchable: true,
  ...options,
})

export const guidedWorkflowRegistry: Record<GuidedWorkflowId, GuidedWorkflowDefinition> = {
  passport_expiration: {
    id: 'passport_expiration',
    title: 'Track passport expiration',
    shortDescription: 'Keep the expiration date and renewal reminder together.',
    intentLabel: 'Track my passport expiration',
    icon: BadgeCheck,
    associatedItemType: 'passport',
    existingItemCanBeUsed: true,
    newItemCanBeCreated: true,
    itemTitleConfiguration: {
      label: 'Passport holder',
      placeholder: 'Full name',
      reviewLabel: 'Passport holder',
    },
    requiredSteps: ['item', 'details', 'responsibility', 'document', 'review'],
    fields: [
      field('expiration_date', 'When does it expire?', 'details', 'date', {
        required: true,
        reviewLabel: 'Passport expires',
        registryDetailKey: 'expiration_date',
        recordField: 'expiration_date',
      }),
      field('issuing_country', 'Issuing country', 'details', 'text', {
        registryDetailKey: 'provider_or_brand',
        recordField: 'provider_or_brand',
        placeholder: 'United States',
      }),
      field('issue_date', 'Issue date', 'details', 'date', {
        registryDetailKey: 'issue_date',
        recordField: 'issue_date',
      }),
      field('passport_number', 'Passport number', 'details', 'password', {
        reviewLabel: 'Passport number',
        helperText: 'Optional. This detail will be encrypted before storage and excluded from search.',
        registryDetailKey: 'document_number',
        protectedField: 'document_number',
        protected: true,
        searchable: false,
      }),
    ],
    responsibilityConfiguration: {
      type: 'renewal',
      title: 'Passport renewal',
      defaultLeadValue: 6,
      defaultLeadUnit: 'months',
      defaultRepeat: 'None',
    },
    documentPrompt: {
      title: 'Add a passport document',
      description: 'A passport scan or renewal receipt can stay with this passport.',
      privacyGuidance: 'Optional. Upload only if keeping a copy here is appropriate for you. LifeLedger does not read or extract its contents.',
      optional: true,
    },
    relationshipDefaults: { type: 'reminder_for', presentation: 'Responsibility for this passport' },
    reviewPresentation: { title: 'Review passport tracking', saveLabel: 'Start tracking passport' },
    completionPresentation: { title: 'Passport expiration is now tracked' },
    defaultValues: scheduleDefaults(6, 'months', 'None'),
  },
  vehicle_registration: {
    id: 'vehicle_registration',
    title: 'Track vehicle registration',
    shortDescription: 'Track the registration expiration, renewal, and optional document.',
    intentLabel: 'Track my vehicle registration',
    icon: Car,
    associatedItemType: 'vehicle',
    existingItemCanBeUsed: true,
    newItemCanBeCreated: true,
    itemTitleConfiguration: {
      label: 'Vehicle name',
      placeholder: 'Mazda3 or Family SUV',
      reviewLabel: 'Vehicle',
    },
    requiredSteps: ['item', 'details', 'responsibility', 'document', 'review'],
    fields: [
      field('make', 'Make', 'details', 'text', {
        registryDetailKey: 'provider_or_brand',
        recordField: 'provider_or_brand',
        placeholder: 'Mazda',
      }),
      field('model', 'Model', 'details', 'text', {
        registryDetailKey: 'model',
        dynamicDetailKey: 'model',
        placeholder: 'Mazda3',
      }),
      field('year', 'Year', 'details', 'number', {
        registryDetailKey: 'year',
        dynamicDetailKey: 'year',
        placeholder: '2024',
      }),
      field('license_plate', 'License plate', 'details', 'password', {
        registryDetailKey: 'license_plate',
        dynamicDetailKey: 'license_plate',
        helperText: 'Optional. Stored as a protected detail and excluded from search.',
        protected: true,
        searchable: false,
      }),
      field('vin', 'VIN', 'details', 'password', {
        registryDetailKey: 'vin',
        protectedField: 'vin',
        helperText: 'Optional. This detail will be encrypted before storage and excluded from search.',
        protected: true,
        searchable: false,
      }),
      field('registration_expiration', 'Registration expiration date', 'responsibility', 'date', {
        required: true,
        reviewLabel: 'Registration expires',
        registryDetailKey: 'registration_expiration',
        dynamicDetailKey: 'registration_expiration',
      }),
      field('registration_authority', 'State or issuing authority', 'responsibility', 'text', {
        registryDetailKey: 'registration_authority',
        dynamicDetailKey: 'registration_authority',
        placeholder: 'Maryland',
      }),
    ],
    responsibilityConfiguration: {
      type: 'renewal',
      title: 'Registration renewal',
      defaultLeadValue: 1,
      defaultLeadUnit: 'months',
      defaultRepeat: 'Yearly',
    },
    documentPrompt: {
      title: 'Add your registration document',
      description: 'Keep the current registration document with this vehicle.',
      privacyGuidance: 'Optional. PDF, JPEG, and PNG files are scanned before becoming available.',
      optional: true,
    },
    relationshipDefaults: { type: 'reminder_for', presentation: 'Responsibility for this vehicle' },
    reviewPresentation: { title: 'Review registration tracking', saveLabel: 'Track registration' },
    completionPresentation: { title: 'Vehicle registration is now tracked' },
    defaultValues: scheduleDefaults(1, 'months', 'Yearly'),
  },
  pet_vaccination: {
    id: 'pet_vaccination',
    title: 'Track pet vaccination',
    shortDescription: 'Keep a vaccination and its next due date with your pet.',
    intentLabel: 'Track a pet vaccination',
    icon: PawPrint,
    associatedItemType: 'pet',
    existingItemCanBeUsed: true,
    newItemCanBeCreated: true,
    itemTitleConfiguration: {
      label: 'Pet name',
      placeholder: 'Baxter',
      reviewLabel: 'Pet',
    },
    requiredSteps: ['item', 'details', 'responsibility', 'document', 'review'],
    fields: [
      field('breed', 'Breed', 'details', 'text', {
        registryDetailKey: 'breed',
        dynamicDetailKey: 'breed',
        placeholder: 'Breed or mix',
      }),
      field('birthday', 'Birthday', 'details', 'date', {
        registryDetailKey: 'birthday',
        dynamicDetailKey: 'birthday',
      }),
      field('veterinarian', 'Veterinarian', 'details', 'text', {
        registryDetailKey: 'vet',
        dynamicDetailKey: 'vet',
        placeholder: 'Veterinarian or clinic',
      }),
      field('vaccination_name', 'Vaccination', 'responsibility', 'text', {
        required: true,
        reviewLabel: 'Vaccination',
        placeholder: 'Rabies',
        suggestions: ['Rabies', 'DHPP', 'Bordetella', 'Leptospirosis', 'Other vaccination'],
      }),
      field('administered_date', 'Date administered', 'responsibility', 'date', {
        reviewLabel: 'Last administered',
      }),
      field('next_due_date', 'Next due date', 'responsibility', 'date', {
        required: true,
        reviewLabel: 'Next due',
        registryDetailKey: 'next_vaccination_due_date',
        dynamicDetailKey: 'next_vaccination_due_date',
      }),
      field('vaccination_provider', 'Veterinarian for this vaccination', 'responsibility', 'text', {
        reviewLabel: 'Veterinarian',
        placeholder: 'Clinic or veterinarian',
      }),
      field('vaccination_notes', 'Notes', 'responsibility', 'textarea', {
        placeholder: 'Optional context only—do not store sensitive medical details.',
      }),
    ],
    responsibilityConfiguration: {
      type: 'maintenance',
      title: 'Vaccination',
      defaultLeadValue: 2,
      defaultLeadUnit: 'weeks',
      defaultRepeat: 'None',
    },
    documentPrompt: {
      title: 'Add a vaccination record',
      description: 'Keep a vaccination certificate or veterinary record with this pet.',
      privacyGuidance: 'Optional. LifeLedger does not interpret medical information or provide veterinary advice.',
      optional: true,
    },
    relationshipDefaults: { type: 'reminder_for', presentation: 'Responsibility for this pet' },
    reviewPresentation: { title: 'Review vaccination tracking', saveLabel: 'Save vaccination' },
    completionPresentation: { title: 'Pet vaccination is now tracked' },
    defaultValues: scheduleDefaults(2, 'weeks', 'None'),
  },
  subscription_renewal: {
    id: 'subscription_renewal',
    title: 'Track subscription renewal',
    shortDescription: 'Track the next charge, billing frequency, and renewal reminder.',
    intentLabel: 'Track a subscription renewal',
    icon: RefreshCcw,
    associatedItemType: 'subscription',
    existingItemCanBeUsed: true,
    newItemCanBeCreated: true,
    itemTitleConfiguration: {
      label: 'Subscription name',
      placeholder: 'Streaming service or gym membership',
      reviewLabel: 'Subscription',
    },
    requiredSteps: ['item', 'details', 'responsibility', 'document', 'review'],
    fields: [
      field('provider', 'Provider', 'details', 'text', {
        registryDetailKey: 'provider_or_brand',
        recordField: 'provider_or_brand',
        placeholder: 'Service or company',
      }),
      field('price', 'Price', 'details', 'money', {
        registryDetailKey: 'cost',
        dynamicDetailKey: 'cost',
        placeholder: '0.00',
      }),
      field('billing_frequency', 'Billing frequency', 'details', 'select', {
        required: true,
        registryDetailKey: 'billing_cycle',
        dynamicDetailKey: 'billing_cycle',
        options: ['Monthly', 'Quarterly', 'Yearly', 'Custom or non-recurring'],
      }),
      field('renewal_date', 'Next billing or renewal date', 'details', 'date', {
        required: true,
        reviewLabel: 'Next due',
        registryDetailKey: 'renewal_date',
        recordField: 'renewal_date',
      }),
      field('cancellation_info', 'Cancellation information', 'details', 'textarea', {
        registryDetailKey: 'cancellation_info',
        dynamicDetailKey: 'cancellation_info',
        placeholder: 'Notice period or cancellation steps',
      }),
      field('website', 'Website', 'details', 'url', {
        registryDetailKey: 'website',
        dynamicDetailKey: 'website',
        placeholder: 'https://example.com/account',
      }),
    ],
    responsibilityConfiguration: {
      type: 'renewal',
      title: 'Subscription renewal',
      defaultLeadValue: 2,
      defaultLeadUnit: 'weeks',
      defaultRepeat: 'Monthly',
    },
    documentPrompt: {
      title: 'Add a receipt, agreement, or cancellation policy',
      description: 'Keep useful subscription paperwork with this item.',
      privacyGuidance: 'Optional. Do not upload passwords, authentication codes, or full payment-card information.',
      optional: true,
    },
    relationshipDefaults: { type: 'reminder_for', presentation: 'Responsibility for this subscription' },
    reviewPresentation: { title: 'Review subscription tracking', saveLabel: 'Track subscription' },
    completionPresentation: { title: 'Subscription renewal is now tracked' },
    defaultValues: {
      ...scheduleDefaults(2, 'weeks', 'Monthly'),
      billing_frequency: 'Monthly',
    },
  },
}

export const guidedWorkflowOptions = guidedWorkflowIds.map((id) => guidedWorkflowRegistry[id])

export function getGuidedWorkflow(id: GuidedWorkflowId | string | null | undefined) {
  return id && Object.prototype.hasOwnProperty.call(guidedWorkflowRegistry, id)
    ? guidedWorkflowRegistry[id as GuidedWorkflowId]
    : null
}

export function getGuidedWorkflowsForItemType(type: RecordType | string | null | undefined) {
  return guidedWorkflowOptions.filter((workflow) => workflow.associatedItemType === type)
}

export function getCompatibleActiveItems(workflow: GuidedWorkflowDefinition, records: LifeRecord[]) {
  return records.filter((record) => record.record_type === workflow.associatedItemType && record.status !== 'archived')
}

export function initializeGuidedWorkflowValues(workflow: GuidedWorkflowDefinition, record?: LifeRecord | null): GuidedWorkflowValues {
  const values: GuidedWorkflowValues = {
    ...workflow.defaultValues,
    item_title: record?.title ?? '',
  }

  if (!record) return values

  for (const fieldDefinition of workflow.fields) {
    const stored = getGuidedStoredValue(record, fieldDefinition)
    if (stored.value !== null && !stored.protected) values[fieldDefinition.id] = stored.value
  }

  if (workflow.id === 'pet_vaccination') {
    values.vaccination_provider = values.veterinarian ?? ''
  }
  if (workflow.id === 'subscription_renewal') {
    values.reminder_repeat = repeatForBillingFrequency(values.billing_frequency)
  }

  return values
}

export function getGuidedStoredValue(record: LifeRecord, fieldDefinition: GuidedWorkflowField): {
  value: string | null
  protected: boolean
  hasValue: boolean
} {
  if (fieldDefinition.protectedField) {
    const hasValue = record.protected_field_names.includes(fieldDefinition.protectedField)
    return { value: null, protected: true, hasValue }
  }
  if (fieldDefinition.recordField) {
    const value = record[fieldDefinition.recordField]
    const normalized = value === null || value === undefined ? null : String(value)
    return { value: normalized, protected: false, hasValue: Boolean(normalized) }
  }
  if (fieldDefinition.dynamicDetailKey) {
    const dynamicField = record.dynamic_fields.find((item) => item.key === fieldDefinition.dynamicDetailKey)
    if (!dynamicField) return { value: null, protected: fieldDefinition.protected, hasValue: false }
    const value = dynamicField.is_sensitive || dynamicField.value === null ? null : String(dynamicField.value)
    return { value, protected: dynamicField.is_sensitive, hasValue: dynamicField.has_value }
  }
  return { value: null, protected: fieldDefinition.protected, hasValue: false }
}

export function buildGuidedNewRecordInput(workflow: GuidedWorkflowDefinition, values: GuidedWorkflowValues): RecordInput {
  const input = createRecordInput(workflow.associatedItemType)
  input.title = values.item_title.trim()
  if (workflow.itemTitleConfiguration.mirrorRecordField) {
    input[workflow.itemTitleConfiguration.mirrorRecordField] = input.title
  }

  for (const fieldDefinition of workflow.fields) {
    if (!fieldDefinition.recordField || fieldDefinition.protectedField) continue
    const value = normalizeValue(values[fieldDefinition.id])
    if (value !== null) input[fieldDefinition.recordField] = value
  }
  return input
}

export function buildGuidedExistingRecordInput(
  workflow: GuidedWorkflowDefinition,
  record: LifeRecord,
  values: GuidedWorkflowValues,
  approvedUpdates: Set<string>,
): RecordInput {
  const input = recordToInput(record)
  for (const fieldDefinition of workflow.fields) {
    if (!fieldDefinition.recordField || fieldDefinition.protectedField) continue
    const value = normalizeValue(values[fieldDefinition.id])
    if (value === null) continue
    const stored = getGuidedStoredValue(record, fieldDefinition)
    if (!stored.hasValue || stored.value === value || approvedUpdates.has(fieldDefinition.id)) {
      input[fieldDefinition.recordField] = value
    }
  }
  return input
}

export function recordInputChanged(record: LifeRecord, input: RecordInput) {
  return JSON.stringify(recordToInput(record)) !== JSON.stringify(input)
}

export interface GuidedDynamicDetailOperation {
  fieldDefinition: GuidedWorkflowField
  existingField: DynamicRecordField | null
  createInput?: DynamicRecordFieldInput
  updateInput?: DynamicRecordFieldUpdateInput
}

export function buildGuidedDynamicDetailOperations(
  workflow: GuidedWorkflowDefinition,
  values: GuidedWorkflowValues,
  record?: LifeRecord | null,
  approvedUpdates: Set<string> = new Set(),
): GuidedDynamicDetailOperation[] {
  const definition = getEntityDefinition(workflow.associatedItemType)
  return workflow.fields.flatMap<GuidedDynamicDetailOperation>((fieldDefinition) => {
    if (!fieldDefinition.dynamicDetailKey) return []
    const value = normalizeValue(values[fieldDefinition.id])
    if (value === null) return []
    const registryDetail = definition.suggestedDetails.find((detail) => detail.key === fieldDefinition.registryDetailKey)
    if (!registryDetail) return []
    const existingField = record?.dynamic_fields.find((item) => item.key === fieldDefinition.dynamicDetailKey) ?? null
    const input = toDynamicDetailInput(fieldDefinition, registryDetail, value)
    if (!existingField) return [{ fieldDefinition, existingField, createInput: input }]
    if (!existingField.is_sensitive && String(existingField.value ?? '') === value) return []
    if (existingField.is_sensitive || approvedUpdates.has(fieldDefinition.id)) {
      return [{
        fieldDefinition,
        existingField,
        updateInput: {
          label: input.label,
          value: input.value,
          is_sensitive: input.is_sensitive,
          select_options: input.select_options,
          display_order: input.display_order,
        },
      }]
    }
    return []
  })
}

export function buildGuidedProtectedInput(workflow: GuidedWorkflowDefinition, values: GuidedWorkflowValues): ProtectedRecordInput {
  const protectedInput: ProtectedRecordInput = {}
  for (const fieldDefinition of workflow.fields) {
    if (!fieldDefinition.protectedField) continue
    const value = normalizeValue(values[fieldDefinition.id])
    if (value !== null) protectedInput[fieldDefinition.protectedField] = value
  }
  return protectedInput
}

export function buildGuidedReminderInput(
  workflow: GuidedWorkflowDefinition,
  values: GuidedWorkflowValues,
  itemTitle: string,
): ReminderInput {
  const leadValue = positiveInteger(values.reminder_lead_value, workflow.responsibilityConfiguration.defaultLeadValue)
  const leadUnit = toLeadUnit(values.reminder_lead_unit, workflow.responsibilityConfiguration.defaultLeadUnit)
  const repeat = toRepeat(values.reminder_repeat, workflow.responsibilityConfiguration.defaultRepeat)

  if (workflow.id === 'pet_vaccination') {
    const vaccinationName = values.vaccination_name?.trim() || 'Vaccination'
    const provider = values.vaccination_provider?.trim()
    const notes = values.vaccination_notes?.trim()
    const instructions = [provider ? `Veterinarian: ${provider}` : null, notes].filter(Boolean).join('\n') || null
    return {
      ...createMaintenanceReminderInput({
      title: `${vaccinationName} vaccination`.replace(/vaccination vaccination$/i, 'vaccination'),
      category: 'Family',
      due_date: values.next_due_date,
      repeat,
      notes: instructions,
      reminder_lead_value: leadValue,
      reminder_lead_unit: leadUnit,
      maintenance_details: {
        ...emptyMaintenanceDetails(),
        item_name: itemTitle,
        maintenance_area: 'pet',
        last_completed_date: normalizeValue(values.administered_date),
        next_due_date: values.next_due_date,
        interval_value: null,
        interval_unit: null,
        instructions,
      },
      }),
      workflow_id: workflow.id,
    }
  }

  const dueDate = workflow.id === 'passport_expiration'
    ? values.expiration_date
    : workflow.id === 'vehicle_registration'
      ? values.registration_expiration
      : values.renewal_date
  const provider = workflow.id === 'passport_expiration'
    ? values.issuing_country
    : workflow.id === 'vehicle_registration'
      ? values.registration_authority
      : values.provider
  const frequency = workflow.id === 'subscription_renewal' ? values.billing_frequency : repeat
  const renewalKind = workflow.id === 'passport_expiration' ? 'expiration' as const : 'renewal' as const

  return {
    ...createRenewalReminderInput({
    title: workflow.responsibilityConfiguration.title,
    category: workflow.id === 'vehicle_registration' ? 'Car' : workflow.id === 'subscription_renewal' ? 'Subscriptions' : 'Other',
    due_date: dueDate,
    repeat,
    reminder_lead_value: leadValue,
    reminder_lead_unit: leadUnit,
    renewal_details: {
      ...emptyRenewalDetails(),
      item_name: itemTitle,
      renewal_kind: renewalKind,
      owner_name: workflow.id === 'passport_expiration' ? itemTitle : null,
      provider: normalizeValue(provider),
      renewal_date: renewalKind === 'renewal' ? dueDate : null,
      expiration_date: renewalKind === 'expiration' ? dueDate : null,
      frequency: normalizeValue(frequency),
    },
    }),
    workflow_id: workflow.id,
  }
}

export function getWorkflowDueDate(workflow: GuidedWorkflowDefinition, values: GuidedWorkflowValues) {
  if (workflow.id === 'passport_expiration') return values.expiration_date
  if (workflow.id === 'vehicle_registration') return values.registration_expiration
  if (workflow.id === 'pet_vaccination') return values.next_due_date
  return values.renewal_date
}

export function repeatForBillingFrequency(frequency: string | null | undefined): RepeatOption {
  if (frequency === 'Monthly') return 'Monthly'
  if (frequency === 'Quarterly') return 'Quarterly'
  if (frequency === 'Yearly') return 'Yearly'
  return 'None'
}

export function formatGuidedSchedule(values: GuidedWorkflowValues) {
  const value = positiveInteger(values.reminder_lead_value, 1)
  const unit = toLeadUnit(values.reminder_lead_unit, 'weeks')
  const singularUnit = value === 1 ? unit.slice(0, -1) : unit
  return `${value} ${singularUnit} before`
}

export function validateGuidedWorkflowConfiguration(workflow: GuidedWorkflowDefinition) {
  const entity = getEntityDefinition(workflow.associatedItemType)
  const registryKeys = new Set(entity.suggestedDetails.map((detail) => detail.key))
  return workflow.fields.every((item) => !item.registryDetailKey || registryKeys.has(item.registryDetailKey))
}

function toDynamicDetailInput(
  fieldDefinition: GuidedWorkflowField,
  registryDetail: SuggestedDetailDefinition,
  value: string,
): DynamicRecordFieldInput {
  return {
    key: fieldDefinition.dynamicDetailKey,
    label: registryDetail.label,
    field_type: guidedInputToDynamicType(fieldDefinition.inputType, registryDetail.dataType),
    value: fieldDefinition.inputType === 'number' || fieldDefinition.inputType === 'money' ? Number(value) : value,
    is_sensitive: fieldDefinition.protected || registryDetail.protectedByDefault,
    select_options: registryDetail.selectOptions ?? [],
    display_order: registryDetail.displayOrder,
  }
}

function guidedInputToDynamicType(inputType: GuidedInputType, fallback: DynamicFieldType): DynamicFieldType {
  if (inputType === 'textarea') return 'long_text'
  if (inputType === 'password' || inputType === 'text') return 'short_text'
  if (inputType === 'date' || inputType === 'number' || inputType === 'money' || inputType === 'url' || inputType === 'select') return inputType
  return fallback
}

function normalizeValue(value: string | null | undefined) {
  return value?.trim() || null
}

function positiveInteger(value: string | null | undefined, fallback: number) {
  const numberValue = Number(value)
  return Number.isInteger(numberValue) && numberValue > 0 ? numberValue : fallback
}

function toLeadUnit(value: string | null | undefined, fallback: ReminderLeadUnit): ReminderLeadUnit {
  return value === 'days' || value === 'weeks' || value === 'months' ? value : fallback
}

function toRepeat(value: string | null | undefined, fallback: RepeatOption): RepeatOption {
  return value === 'None' || value === 'Weekly' || value === 'Monthly' || value === 'Quarterly' || value === 'Yearly' ? value : fallback
}

export function getGuidedEntityDefinition(workflow: GuidedWorkflowDefinition): EntityCapabilityDefinition {
  return getEntityDefinition(workflow.associatedItemType)
}
