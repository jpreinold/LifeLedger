import {
  BadgeCheck,
  Car,
  FileText,
  Home,
  HousePlug,
  PawPrint,
  RefreshCcw,
  ShieldCheck,
  UserRound,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type {
  DynamicFieldType,
  ProtectedRecordField,
  RecordStatus,
  RecordType,
} from '../types/record'
import type { ReminderLeadUnit, ReminderType } from '../types/reminder'

export type EntitySection = 'overview' | 'details' | 'responsibilities' | 'documents' | 'relatedItems'
export type DetailSection = 'overview' | 'details'

export type RecordField =
  | 'subtitle'
  | 'owner_name'
  | 'provider_or_brand'
  | 'start_date'
  | 'issue_date'
  | 'expiration_date'
  | 'purchase_date'
  | 'renewal_date'
  | 'birthday'
  | 'relationship_context'
  | 'location_hint'
  | 'notes'
  | 'tags'

export interface SuggestedDetailDefinition {
  key: string
  label: string
  dataType: DynamicFieldType
  placeholder: string
  helperText: string
  protectedByDefault: boolean
  required: boolean
  searchable: boolean
  section: DetailSection
  displayOrder: number
  showByDefault?: boolean
  recordField?: RecordField
  protectedField?: ProtectedRecordField
  selectOptions?: string[]
}

export interface SuggestedResponsibilityDefinition {
  type: ReminderType
  label: string
  description: string
  relevantDateLabel: string
  defaultReminderOffsets: Array<{ value: number; unit: ReminderLeadUnit }>
  relationshipBehavior: 'responsibility_for_item'
}

export interface DynamicFieldPreset {
  key: string
  label: string
  field_type: DynamicFieldType
  is_sensitive?: boolean
  select_options?: string[]
  description?: string
  display_order?: number
  placeholder?: string
  searchable?: boolean
}

export interface EntityCapabilityDefinition {
  type: RecordType
  label: string
  description: string
  id: RecordType
  internalRecordType: RecordType
  singularLabel: string
  pluralLabel: string
  shortDescription: string
  icon: LucideIcon
  category: string
  defaultStatus: RecordStatus
  suggestedDetails: SuggestedDetailDefinition[]
  supportedSections: EntitySection[]
  suggestedResponsibilities: SuggestedResponsibilityDefinition[]
  suggestedDocumentKinds: string[]
  supportsOwnership: boolean
  supportsProviders: boolean
  supportsProtectedDetails: boolean
  supportsDates: boolean
  supportsRelationships: boolean
  searchPresentation: {
    resultLabel: string
    keywords: string[]
  }
  emptyStateCopy: {
    details: string
    responsibilities: string
    documents: string
    relatedItems: string
  }
  createActionLabel: string
  titleLabel: string
  defaultTitle: string
  tone: 'other' | 'car' | 'finance' | 'home' | 'family' | 'subscriptions' | 'health'
  legacyDuplicateCategories: string[]
  fields: RecordField[]
  coreFields: Array<'title' | RecordField>
  defaultSuggestedFields: RecordField[]
  dynamicFieldPresets: DynamicFieldPreset[]
  protectedFields: ProtectedRecordField[]
  labels: Partial<Record<RecordField, string>>
  placeholders: Partial<Record<RecordField, string>>
}

interface EntityDefinitionInput extends Omit<
  EntityCapabilityDefinition,
  'type' | 'label' | 'description' | 'id' | 'internalRecordType' | 'fields' | 'defaultSuggestedFields' | 'dynamicFieldPresets' | 'protectedFields' | 'labels' | 'placeholders'
> {
  type: RecordType
  additionalFields?: RecordField[]
}

const standardSections: EntitySection[] = ['overview', 'responsibilities', 'documents', 'relatedItems']

const standardEmptyCopy = {
  details: 'Add the details that will help you recognize and manage this item.',
  responsibilities: 'No upcoming responsibilities yet. Add a renewal, service date, payment, or other task connected to this item.',
  documents: 'Keep supporting documents with the item they belong to.',
  relatedItems: 'Connect related items so LifeLedger can keep the full picture together.',
}

const responsibility = (
  type: ReminderType,
  label: string,
  description: string,
  relevantDateLabel: string,
  value = 1,
  unit: ReminderLeadUnit = 'months',
): SuggestedResponsibilityDefinition => ({
  type,
  label,
  description,
  relevantDateLabel,
  defaultReminderOffsets: [{ value, unit }],
  relationshipBehavior: 'responsibility_for_item',
})

const detail = (
  key: string,
  label: string,
  dataType: DynamicFieldType,
  displayOrder: number,
  options: Partial<SuggestedDetailDefinition> = {},
): SuggestedDetailDefinition => ({
  key,
  label,
  dataType,
  placeholder: '',
  helperText: '',
  protectedByDefault: false,
  required: false,
  searchable: true,
  section: 'details',
  displayOrder,
  ...options,
})

function defineEntity(input: EntityDefinitionInput): EntityCapabilityDefinition {
  const recordDetails = input.suggestedDetails.filter((item) => item.recordField)
  const fields = [...new Set([
    ...recordDetails.map((item) => item.recordField as RecordField),
    ...(input.additionalFields ?? []),
  ])]

  return {
    ...input,
    type: input.type,
    label: input.singularLabel,
    description: input.shortDescription,
    id: input.type,
    internalRecordType: input.type,
    fields,
    defaultSuggestedFields: recordDetails.filter((item) => item.showByDefault).map((item) => item.recordField as RecordField),
    dynamicFieldPresets: input.suggestedDetails
      .filter((item) => !item.recordField && !item.protectedField)
      .map((item) => ({
        key: item.key,
        label: item.label,
        field_type: item.dataType,
        is_sensitive: item.protectedByDefault,
        select_options: item.selectOptions,
        description: item.helperText,
        display_order: item.displayOrder,
        placeholder: item.placeholder,
        searchable: item.searchable,
      })),
    protectedFields: input.suggestedDetails
      .map((item) => item.protectedField)
      .filter((item): item is ProtectedRecordField => Boolean(item)),
    labels: Object.fromEntries(
      recordDetails.map((item) => [item.recordField as RecordField, item.label]),
    ),
    placeholders: Object.fromEntries(
      recordDetails.filter((item) => item.placeholder).map((item) => [item.recordField as RecordField, item.placeholder]),
    ),
  }
}

export const entityCapabilityRegistry: Record<RecordType, EntityCapabilityDefinition> = {
  person: defineEntity({
    type: 'person',
    singularLabel: 'Person',
    pluralLabel: 'People',
    shortDescription: 'Remember a person, their birthday, and the responsibilities and documents connected to them.',
    icon: UserRound,
    category: 'People',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('relationship_context', 'Relationship', 'select', 110, { recordField: 'relationship_context', placeholder: 'Choose a relationship', showByDefault: true, section: 'overview', selectOptions: ['Friend', 'Family', 'Partner', 'Coworker', 'Neighbor', 'Acquaintance', 'Other'] }),
      detail('birthday', 'Birthday', 'short_text', 120, { recordField: 'birthday', placeholder: 'Month and day', helperText: 'A year is optional. LifeLedger never invents one.', showByDefault: true, section: 'overview' }),
      detail('aliases', 'Aliases', 'short_text', 130, { placeholder: 'Other names, separated by commas' }),
      detail('notes', 'Notes', 'long_text', 200, { recordField: 'notes', placeholder: 'A short, useful note' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [responsibility('birthday', 'Birthday reminder', 'Remember this person’s birthday every year.', 'Birthday', 7, 'days')],
    suggestedDocumentKinds: ['Supporting document', 'Shared reference'],
    supportsOwnership: false,
    supportsProviders: false,
    supportsProtectedDetails: false,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Person', keywords: ['person', 'people', 'friend', 'family', 'birthday'] },
    emptyStateCopy: {
      ...standardEmptyCopy,
      responsibilities: 'Add a birthday or another responsibility connected to this person.',
      documents: 'Keep only useful documents connected to this person.',
    },
    createActionLabel: 'Add person',
    titleLabel: 'Display name',
    defaultTitle: 'Person',
    tone: 'family',
    legacyDuplicateCategories: ['Person', 'People'],
    coreFields: ['title', 'birthday'],
    additionalFields: ['notes', 'tags'],
  }),
  general: defineEntity({
    type: 'general',
    singularLabel: 'Other item',
    pluralLabel: 'Other items',
    shortDescription: 'Keep track of something important that does not fit another item type.',
    icon: FileText,
    category: 'General',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('subtitle', 'Description', 'short_text', 100, { recordField: 'subtitle', placeholder: 'What makes this item useful to remember?', showByDefault: true, section: 'overview' }),
      detail('owner_name', 'Who it concerns', 'short_text', 110, { recordField: 'owner_name', placeholder: 'Me, a family member, or my household', showByDefault: true, section: 'overview' }),
      detail('provider_or_brand', 'Provider or organization', 'short_text', 120, { recordField: 'provider_or_brand', placeholder: 'Organization or provider', showByDefault: true, section: 'overview' }),
      detail('date', 'Important date', 'date', 200, { placeholder: 'Choose a date', helperText: 'A useful date connected to this item.' }),
      detail('sensitive_notes', 'Protected notes', 'long_text', 900, { protectedByDefault: true, searchable: false, protectedField: 'sensitive_notes', helperText: 'Encrypted before storage and hidden until you reveal it.' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [responsibility('generic', 'Review this item', 'Set a date to check that the information is still current.', 'Review date')],
    suggestedDocumentKinds: ['Supporting document', 'Receipt', 'Reference file'],
    supportsOwnership: true,
    supportsProviders: true,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Other item', keywords: ['item', 'other', 'general'] },
    emptyStateCopy: standardEmptyCopy,
    createActionLabel: 'Add other item',
    titleLabel: 'Item name',
    defaultTitle: 'Important item',
    tone: 'other',
    legacyDuplicateCategories: ['General', 'Other', 'Other item'],
    coreFields: ['title'],
    additionalFields: ['start_date', 'expiration_date', 'location_hint', 'notes', 'tags'],
  }),
  passport: defineEntity({
    type: 'passport',
    singularLabel: 'Passport',
    pluralLabel: 'Passports',
    shortDescription: 'Keep the holder, issuing country, expiration, and protected passport number together.',
    icon: BadgeCheck,
    category: 'Identity',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('expiration_date', 'Expiration date', 'date', 110, { recordField: 'expiration_date', showByDefault: true, section: 'overview' }),
      detail('provider_or_brand', 'Issuing country', 'short_text', 120, { recordField: 'provider_or_brand', placeholder: 'United States', showByDefault: true, section: 'overview' }),
      detail('issue_date', 'Issue date', 'date', 130, { recordField: 'issue_date' }),
      detail('document_number', 'Passport number', 'short_text', 140, { protectedByDefault: true, searchable: false, protectedField: 'document_number', helperText: 'Encrypted before storage and hidden until you reveal it.' }),
      detail('nationality', 'Nationality', 'short_text', 150, { placeholder: 'Nationality' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [responsibility('renewal', 'Passport renewal', 'Plan renewal before the passport expires.', 'Expiration date', 6)],
    suggestedDocumentKinds: ['Passport scan', 'Renewal receipt', 'Travel document'],
    supportsOwnership: true,
    supportsProviders: false,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Passport', keywords: ['passport', 'identity', 'travel document'] },
    emptyStateCopy: { ...standardEmptyCopy, documents: 'Keep a passport scan, renewal receipt, and related travel documents together.' },
    createActionLabel: 'Add passport',
    titleLabel: 'Passport holder',
    defaultTitle: 'Passport',
    tone: 'other',
    legacyDuplicateCategories: ['Passport'],
    coreFields: ['title', 'expiration_date'],
    additionalFields: ['location_hint', 'notes', 'tags'],
  }),
  driver_license: defineEntity({
    type: 'driver_license',
    singularLabel: 'Driver license',
    pluralLabel: 'Driver licenses',
    shortDescription: 'Keep the holder, issuing authority, expiration, and protected license number together.',
    icon: BadgeCheck,
    category: 'Identity',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('expiration_date', 'Expiration date', 'date', 110, { recordField: 'expiration_date', showByDefault: true, section: 'overview' }),
      detail('provider_or_brand', 'Issuing state or authority', 'short_text', 120, { recordField: 'provider_or_brand', placeholder: 'Maryland', showByDefault: true, section: 'overview' }),
      detail('issue_date', 'Issue date', 'date', 130, { recordField: 'issue_date' }),
      detail('license_number', 'License number', 'short_text', 140, { protectedByDefault: true, searchable: false, protectedField: 'license_number', helperText: 'Encrypted before storage and hidden until you reveal it.' }),
      detail('class', 'Class', 'short_text', 150, { placeholder: 'License class' }),
      detail('restrictions', 'Restrictions', 'short_text', 160, { placeholder: 'Restrictions, if any' }),
      detail('real_id', 'Real ID', 'boolean', 170),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [responsibility('renewal', 'License renewal', 'Renew before the license expires.', 'Expiration date', 2)],
    suggestedDocumentKinds: ['License scan', 'Renewal receipt', 'Supporting identity document'],
    supportsOwnership: true,
    supportsProviders: false,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Driver license', keywords: ['driver license', 'license', 'identity'] },
    emptyStateCopy: { ...standardEmptyCopy, documents: 'Keep a license scan, renewal receipt, and supporting identity documents together.' },
    createActionLabel: 'Add driver license',
    titleLabel: 'License holder',
    defaultTitle: 'Driver license',
    tone: 'other',
    legacyDuplicateCategories: ['Driver license', 'Driver License'],
    coreFields: ['title', 'expiration_date'],
    additionalFields: ['location_hint', 'notes', 'tags'],
  }),
  vehicle: defineEntity({
    type: 'vehicle',
    singularLabel: 'Vehicle',
    pluralLabel: 'Vehicles',
    shortDescription: 'Keep registration, ownership, service details, and documents with your vehicle.',
    icon: Car,
    category: 'Transportation',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('provider_or_brand', 'Make', 'short_text', 100, { recordField: 'provider_or_brand', placeholder: 'Toyota', showByDefault: true, section: 'overview' }),
      detail('model', 'Model', 'short_text', 110, { placeholder: 'Camry', showByDefault: true, section: 'overview' }),
      detail('year', 'Year', 'number', 120, { placeholder: '2024', showByDefault: true, section: 'overview' }),
      detail('license_plate', 'License plate', 'short_text', 130, { placeholder: 'Plate number', protectedByDefault: true, searchable: false, showByDefault: true, section: 'overview' }),
      detail('vin', 'VIN', 'short_text', 140, { protectedByDefault: true, searchable: false, protectedField: 'vin', helperText: 'Encrypted before storage and hidden until you reveal it.' }),
      detail('owner_name', 'Owner', 'short_text', 150, { recordField: 'owner_name', placeholder: 'Owner name' }),
      detail('purchase_date', 'Purchase date', 'date', 160, { recordField: 'purchase_date' }),
      detail('color', 'Color', 'short_text', 170, { placeholder: 'Vehicle color' }),
      detail('mileage', 'Mileage', 'number', 180, { placeholder: 'Current mileage' }),
      detail('registration_expiration', 'Registration expiration', 'date', 185, { helperText: 'The current registration expiration date.' }),
      detail('registration_authority', 'Registration state or authority', 'short_text', 187, { placeholder: 'State or issuing authority' }),
      detail('purchase_price', 'Purchase price', 'money', 190, { placeholder: 'Purchase price' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [
      responsibility('renewal', 'Registration renewal', 'Keep the registration current.', 'Registration renewal date', 1),
      responsibility('maintenance', 'Schedule service', 'Track the next maintenance or inspection.', 'Next service date', 2, 'weeks'),
    ],
    suggestedDocumentKinds: ['Registration', 'Insurance card', 'Purchase document', 'Service record'],
    supportsOwnership: true,
    supportsProviders: true,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Vehicle', keywords: ['vehicle', 'car', 'truck', 'transportation'] },
    emptyStateCopy: { ...standardEmptyCopy, documents: 'Keep registration, insurance cards, purchase documents, and service records together.' },
    createActionLabel: 'Add vehicle',
    titleLabel: 'Vehicle name',
    defaultTitle: 'My vehicle',
    tone: 'car',
    legacyDuplicateCategories: ['Vehicle'],
    coreFields: ['title', 'provider_or_brand'],
    additionalFields: ['subtitle', 'location_hint', 'notes', 'tags'],
  }),
  insurance: defineEntity({
    type: 'insurance',
    singularLabel: 'Insurance policy',
    pluralLabel: 'Insurance policies',
    shortDescription: 'Keep coverage, provider, renewal dates, and protected policy details together.',
    icon: ShieldCheck,
    category: 'Finance',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('provider_or_brand', 'Provider', 'short_text', 100, { recordField: 'provider_or_brand', placeholder: 'Insurance provider', showByDefault: true, section: 'overview' }),
      detail('owner_name', 'Policyholder', 'short_text', 110, { recordField: 'owner_name', placeholder: 'Policyholder name', showByDefault: true, section: 'overview' }),
      detail('renewal_date', 'Renewal date', 'date', 120, { recordField: 'renewal_date', showByDefault: true, section: 'overview' }),
      detail('expiration_date', 'Expiration date', 'date', 130, { recordField: 'expiration_date' }),
      detail('start_date', 'Coverage start date', 'date', 140, { recordField: 'start_date' }),
      detail('policy_number', 'Policy number', 'short_text', 150, { protectedByDefault: true, searchable: false, protectedField: 'policy_number' }),
      detail('member_number', 'Member number', 'short_text', 160, { protectedByDefault: true, searchable: false, protectedField: 'member_number' }),
      detail('coverage', 'Coverage', 'short_text', 170, { placeholder: 'Coverage summary' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [responsibility('renewal', 'Policy review', 'Review coverage and renew the policy when needed.', 'Review or renewal date', 1)],
    suggestedDocumentKinds: ['Policy document', 'Insurance card', 'Coverage summary', 'Claim document'],
    supportsOwnership: true,
    supportsProviders: true,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Insurance policy', keywords: ['insurance', 'policy', 'coverage'] },
    emptyStateCopy: { ...standardEmptyCopy, documents: 'Keep policy documents, insurance cards, coverage summaries, and claim records together.' },
    createActionLabel: 'Add insurance policy',
    titleLabel: 'Policy name',
    defaultTitle: 'Insurance policy',
    tone: 'finance',
    legacyDuplicateCategories: ['Insurance', 'Insurance policy'],
    coreFields: ['title', 'provider_or_brand'],
    additionalFields: ['subtitle', 'notes', 'tags'],
  }),
  appliance: defineEntity({
    type: 'appliance',
    singularLabel: 'Appliance',
    pluralLabel: 'Appliances',
    shortDescription: 'Keep model, warranty, purchase, and service information with an appliance.',
    icon: HousePlug,
    category: 'Home',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('provider_or_brand', 'Brand', 'short_text', 100, { recordField: 'provider_or_brand', placeholder: 'Bosch', showByDefault: true, section: 'overview' }),
      detail('model_number', 'Model number', 'short_text', 110, { placeholder: 'Model number', showByDefault: true, section: 'overview' }),
      detail('purchase_date', 'Purchase date', 'date', 120, { recordField: 'purchase_date', showByDefault: true, section: 'overview' }),
      detail('expiration_date', 'Warranty expiration', 'date', 130, { recordField: 'expiration_date', showByDefault: true, section: 'overview' }),
      detail('serial_number', 'Serial number', 'short_text', 140, { protectedByDefault: true, searchable: false, protectedField: 'serial_number' }),
      detail('location_hint', 'Location', 'short_text', 150, { recordField: 'location_hint', placeholder: 'Kitchen, basement, or room' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [responsibility('maintenance', 'Schedule maintenance', 'Track cleaning, filter replacement, or service.', 'Next service date', 2, 'weeks')],
    suggestedDocumentKinds: ['Receipt', 'Warranty', 'Manual', 'Service record'],
    supportsOwnership: false,
    supportsProviders: true,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Appliance', keywords: ['appliance', 'equipment', 'home'] },
    emptyStateCopy: { ...standardEmptyCopy, documents: 'Keep receipts, warranties, manuals, and service records with this appliance.' },
    createActionLabel: 'Add appliance',
    titleLabel: 'Appliance name',
    defaultTitle: 'Appliance',
    tone: 'home',
    legacyDuplicateCategories: ['Appliance'],
    coreFields: ['title', 'provider_or_brand'],
    additionalFields: ['subtitle', 'notes', 'tags'],
  }),
  pet: defineEntity({
    type: 'pet',
    singularLabel: 'Pet',
    pluralLabel: 'Pets',
    shortDescription: 'Keep care details, important dates, providers, and documents with your pet.',
    icon: PawPrint,
    category: 'Family',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('breed', 'Breed', 'short_text', 100, { placeholder: 'Breed or mix', showByDefault: true, section: 'overview' }),
      detail('birthday', 'Birthday', 'short_text', 110, { recordField: 'birthday', placeholder: 'Month and day', helperText: 'A year is optional. LifeLedger never invents one.', showByDefault: true, section: 'overview' }),
      detail('vet', 'Veterinarian', 'short_text', 120, { placeholder: 'Veterinarian or clinic', showByDefault: true, section: 'overview' }),
      detail('next_vaccination_due_date', 'Next vaccination due', 'date', 125, { placeholder: 'Choose a date', showByDefault: true, section: 'overview' }),
      detail('microchip', 'Microchip number', 'short_text', 130, { placeholder: 'Microchip number', protectedByDefault: true, searchable: false, showByDefault: true, section: 'overview' }),
      detail('owner_name', 'Owner', 'short_text', 140, { recordField: 'owner_name', placeholder: 'Owner name', showByDefault: true, section: 'overview' }),
      detail('start_date', 'Adoption or start date', 'date', 150, { recordField: 'start_date' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [
      responsibility('birthday', 'Birthday reminder', 'Remember this pet’s birthday every year.', 'Birthday', 7, 'days'),
      responsibility('renewal', 'Annual vaccination', 'Track the next vaccination due date.', 'Vaccination due date', 1),
      responsibility('generic', 'Wellness visit', 'Plan the next routine veterinary visit.', 'Visit date', 2, 'weeks'),
    ],
    suggestedDocumentKinds: ['Vaccination record', 'Adoption paperwork', 'Insurance document', 'Veterinary record'],
    supportsOwnership: true,
    supportsProviders: true,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Pet', keywords: ['pet', 'animal', 'family'] },
    emptyStateCopy: { ...standardEmptyCopy, documents: 'Keep vaccination records, adoption paperwork, insurance documents, and vet records together.' },
    createActionLabel: 'Add pet',
    titleLabel: 'Pet name',
    defaultTitle: 'My pet',
    tone: 'family',
    legacyDuplicateCategories: ['Pet'],
    coreFields: ['title', 'birthday'],
    additionalFields: ['subtitle', 'notes', 'tags'],
  }),
  home: defineEntity({
    type: 'home',
    singularLabel: 'Home',
    pluralLabel: 'Homes',
    shortDescription: 'Keep ownership, maintenance, provider, and document context for a home.',
    icon: Home,
    category: 'Property',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('location_hint', 'Location', 'short_text', 100, { recordField: 'location_hint', placeholder: 'City, neighborhood, or nickname', showByDefault: true, section: 'overview' }),
      detail('purchase_date', 'Purchase date', 'date', 110, { recordField: 'purchase_date', showByDefault: true, section: 'overview' }),
      detail('home_type', 'Home type', 'select', 120, { selectOptions: ['House', 'Condo', 'Apartment', 'Townhouse', 'Other'], showByDefault: true, section: 'overview' }),
      detail('year_built', 'Year built', 'number', 130, { placeholder: 'Year built' }),
      detail('start_date', 'Move-in date', 'date', 140, { recordField: 'start_date' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [
      responsibility('maintenance', 'Replace HVAC filter', 'Track the next filter replacement.', 'Replacement date', 1, 'weeks'),
      responsibility('maintenance', 'Seasonal home review', 'Review routine maintenance for the season.', 'Review date', 1),
    ],
    suggestedDocumentKinds: ['Purchase document', 'Inspection', 'Insurance document', 'Maintenance record'],
    supportsOwnership: true,
    supportsProviders: true,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Home', keywords: ['home', 'property', 'house'] },
    emptyStateCopy: { ...standardEmptyCopy, documents: 'Keep purchase documents, inspections, insurance, and maintenance records with this home.' },
    createActionLabel: 'Add home',
    titleLabel: 'Home name',
    defaultTitle: 'My home',
    tone: 'home',
    legacyDuplicateCategories: ['Home'],
    coreFields: ['title'],
    additionalFields: ['subtitle', 'notes', 'tags'],
  }),
  subscription: defineEntity({
    type: 'subscription',
    singularLabel: 'Subscription',
    pluralLabel: 'Subscriptions',
    shortDescription: 'Keep billing, renewal, provider, and account context together.',
    icon: RefreshCcw,
    category: 'Finance',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('provider_or_brand', 'Provider', 'short_text', 100, { recordField: 'provider_or_brand', placeholder: 'Service or company', showByDefault: true, section: 'overview' }),
      detail('billing_cycle', 'Billing frequency', 'select', 110, { selectOptions: ['Monthly', 'Quarterly', 'Yearly', 'Custom or non-recurring'], showByDefault: true, section: 'overview' }),
      detail('renewal_date', 'Renewal date', 'date', 120, { recordField: 'renewal_date', showByDefault: true, section: 'overview' }),
      detail('cost', 'Price', 'money', 130, { placeholder: 'Subscription price', showByDefault: true, section: 'overview' }),
      detail('start_date', 'Start date', 'date', 140, { recordField: 'start_date' }),
      detail('account_reference', 'Account reference', 'short_text', 150, { protectedByDefault: true, searchable: false, protectedField: 'account_reference' }),
      detail('cancellation_info', 'Cancellation information', 'long_text', 160, { placeholder: 'Notice period or cancellation steps' }),
      detail('website', 'Website', 'url', 170, { placeholder: 'https://example.com/account' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [responsibility('renewal', 'Subscription renewal', 'Review the price and whether to keep the subscription.', 'Renewal date', 2, 'weeks')],
    suggestedDocumentKinds: ['Receipt', 'Subscription terms', 'Cancellation confirmation'],
    supportsOwnership: true,
    supportsProviders: true,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Subscription', keywords: ['subscription', 'membership', 'billing'] },
    emptyStateCopy: { ...standardEmptyCopy, documents: 'Keep receipts, subscription terms, and cancellation confirmations together.' },
    createActionLabel: 'Add subscription',
    titleLabel: 'Subscription name',
    defaultTitle: 'Subscription',
    tone: 'subscriptions',
    legacyDuplicateCategories: ['Subscription'],
    coreFields: ['title', 'provider_or_brand'],
    additionalFields: ['subtitle', 'notes', 'tags'],
  }),
  warranty: defineEntity({
    type: 'warranty',
    singularLabel: 'Warranty',
    pluralLabel: 'Warranties',
    shortDescription: 'Keep coverage, purchase, expiration, and service documents together.',
    icon: Wrench,
    category: 'Purchases',
    defaultStatus: 'active',
    suggestedDetails: [
      detail('provider_or_brand', 'Brand or provider', 'short_text', 100, { recordField: 'provider_or_brand', placeholder: 'Brand or warranty provider', showByDefault: true, section: 'overview' }),
      detail('purchase_date', 'Purchase date', 'date', 110, { recordField: 'purchase_date', showByDefault: true, section: 'overview' }),
      detail('expiration_date', 'Expiration date', 'date', 120, { recordField: 'expiration_date', showByDefault: true, section: 'overview' }),
      detail('coverage', 'Coverage', 'short_text', 130, { placeholder: 'What is covered?', showByDefault: true, section: 'overview' }),
      detail('serial_number', 'Serial number', 'short_text', 140, { protectedByDefault: true, searchable: false, protectedField: 'serial_number' }),
    ],
    supportedSections: standardSections,
    suggestedResponsibilities: [responsibility('renewal', 'Warranty review', 'Review coverage before the warranty expires.', 'Expiration date', 1)],
    suggestedDocumentKinds: ['Warranty terms', 'Receipt', 'Proof of purchase', 'Service record'],
    supportsOwnership: false,
    supportsProviders: true,
    supportsProtectedDetails: true,
    supportsDates: true,
    supportsRelationships: true,
    searchPresentation: { resultLabel: 'Warranty', keywords: ['warranty', 'coverage', 'purchase'] },
    emptyStateCopy: { ...standardEmptyCopy, documents: 'Keep warranty terms, receipts, proof of purchase, and service records together.' },
    createActionLabel: 'Add warranty',
    titleLabel: 'Warranty name',
    defaultTitle: 'Warranty',
    tone: 'health',
    legacyDuplicateCategories: ['Warranty'],
    coreFields: ['title', 'provider_or_brand'],
    additionalFields: ['subtitle', 'notes', 'tags'],
  }),
}

export const entityTypeOrder: RecordType[] = [
  'person',
  'vehicle',
  'pet',
  'home',
  'passport',
  'driver_license',
  'insurance',
  'subscription',
  'warranty',
  'appliance',
  'general',
]

export const primaryEntityTypes: RecordType[] = [
  'vehicle',
  'pet',
  'home',
  'passport',
  'insurance',
  'subscription',
  'warranty',
  'general',
]

export function getEntityDefinition(type: RecordType | string | null | undefined): EntityCapabilityDefinition {
  if (type && Object.prototype.hasOwnProperty.call(entityCapabilityRegistry, type)) {
    return entityCapabilityRegistry[type as RecordType]
  }
  return entityCapabilityRegistry.general
}

export function getEntityDefinitions(types: RecordType[] = entityTypeOrder) {
  return types.map((type) => entityCapabilityRegistry[type])
}
