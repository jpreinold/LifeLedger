import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { FileUp, Plus, Save, ShieldCheck, X } from 'lucide-react'

import {
  createRecordInput,
  createProtectedRecordInput,
  getRecordTypeDefinition,
  getProtectedFieldLabel,
  normalizeRecordInput,
  normalizeProtectedRecordInput,
  recordToInput,
  tagsFromText,
  tagsToText,
  type RecordField,
} from '../lib/recordTypes'
import type { LifeRecord, ProtectedRecordField, ProtectedRecordInput, RecordInput, RecordType } from '../types/record'
import { RecordDocumentsPanel } from './RecordDocumentsPanel'
import { SheetDrawer } from './SheetDrawer'

interface RecordFormProps {
  isOpen: boolean
  isSaving: boolean
  record: LifeRecord | null
  recordType: RecordType
  onClose: () => void
  onCreate: (input: RecordInput, protectedInput: ProtectedRecordInput) => Promise<boolean>
  onUpdate: (id: string, input: RecordInput, protectedInput: ProtectedRecordInput) => Promise<boolean>
}

const dateFields: RecordField[] = ['start_date', 'issue_date', 'expiration_date', 'purchase_date', 'renewal_date']
type RecordFormTab = 'record' | 'documents'

export function RecordForm({
  isOpen,
  isSaving,
  record,
  recordType,
  onClose,
  onCreate,
  onUpdate,
}: RecordFormProps) {
  const [form, setForm] = useState<RecordInput>(() => createRecordInput(recordType))
  const [protectedForm, setProtectedForm] = useState<ProtectedRecordInput>(() => createProtectedRecordInput(recordType))
  const [activeTab, setActiveTab] = useState<RecordFormTab>('record')
  const [tagsText, setTagsText] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const formBodyRef = useRef<HTMLFormElement | null>(null)
  const definition = getRecordTypeDefinition(form.record_type)
  const Icon = definition.icon
  const isEditing = record !== null

  useEffect(() => {
    if (!isOpen) {
      setValidationError(null)
      setActiveTab('record')
      return
    }

    const nextForm = record ? recordToInput(record) : createRecordInput(recordType)
    setForm(nextForm)
    setProtectedForm(createProtectedRecordInput(nextForm.record_type))
    setTagsText(tagsToText(nextForm.tags))
    setValidationError(null)
    setActiveTab('record')
  }, [isOpen, record, recordType])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const input = normalizeRecordInput({ ...form, tags: tagsFromText(tagsText) })
    if (!input.title) {
      setActiveTab('record')
      setValidationError('Title is required.')
      return
    }

    setValidationError(null)
    const protectedInput = normalizeProtectedRecordInput(input.record_type, protectedForm)
    const wasSaved = record ? await onUpdate(record.id, input, protectedInput) : await onCreate(input, protectedInput)

    if (wasSaved) {
      onClose()
    }
  }

  function updateField(field: keyof RecordInput, value: string | null) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function updateProtectedField(field: ProtectedRecordField, value: string | null) {
    setProtectedForm((current) => ({ ...current, [field]: value }))
  }

  function selectTab(tab: RecordFormTab) {
    setActiveTab(tab)
    formBodyRef.current?.scrollTo({ top: 0 })
  }

  return (
    <SheetDrawer
      className="add-dialog record-form-dialog"
      isOpen={isOpen}
      labelledBy="record-form-heading"
      onClose={onClose}
    >
      <div className="sheet-header">
        <div>
          <h2 id="record-form-heading">{isEditing ? 'Edit Record' : 'Add Record'}</h2>
          <p>{definition.label}</p>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close record form">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="sheet-icon-lockup">
        <div className={`category-icon category-icon-large tone-${definition.tone}`} aria-hidden="true">
          <Icon size={30} />
        </div>
        <span className="record-type-lockup-label">{definition.category}</span>
      </div>

      <form className="reminder-form sheet-body record-form" ref={formBodyRef} onSubmit={handleSubmit}>
        <div className="record-form-tabs" role="tablist" aria-label="Edit record sections">
          <button
            type="button"
            className={activeTab === 'record' ? 'record-form-tab active' : 'record-form-tab'}
            id="record-form-record-tab"
            role="tab"
            aria-selected={activeTab === 'record'}
            aria-controls="record-form-record-panel"
            onClick={() => selectTab('record')}
          >
            Record
          </button>
          <button
            type="button"
            className={activeTab === 'documents' ? 'record-form-tab active' : 'record-form-tab'}
            id="record-form-documents-tab"
            role="tab"
            aria-selected={activeTab === 'documents'}
            aria-controls="record-form-documents-panel"
            onClick={() => selectTab('documents')}
          >
            Documents
          </button>
        </div>

        <div
          className="record-form-tab-panel"
          hidden={activeTab !== 'record'}
          id="record-form-record-panel"
          role="tabpanel"
          aria-labelledby="record-form-record-tab"
        >
          <section className="record-safety-note" aria-label="Record privacy guardrails">
            <ShieldCheck size={16} aria-hidden="true" />
            <span>Do not store SSNs, card or bank data, passwords, recovery codes, keys, or medical documents.</span>
          </section>

          <label>
            <span>{form.record_type === 'pet' ? 'Pet name' : 'Title'}</span>
            <input
              required
              maxLength={120}
              value={form.title}
              onChange={(event) => updateField('title', event.target.value)}
              placeholder={definition.defaultTitle}
            />
          </label>

          <div className="record-form-type-row">
            <span>Record type</span>
            <strong>{definition.label}</strong>
          </div>

          {definition.fields.includes('subtitle') ? (
            <RecordTextField
              field="subtitle"
              form={form}
              definitionType={form.record_type}
              onChange={updateField}
            />
          ) : null}

          <RecordFieldGrid fields={definition.fields.filter((field) => field !== 'subtitle' && field !== 'notes' && field !== 'tags')} form={form} onChange={updateField} />

          {definition.fields.includes('notes') ? (
            <RecordTextArea field="notes" form={form} definitionType={form.record_type} onChange={updateField} />
          ) : null}

          {definition.fields.includes('tags') ? (
            <label>
              <span>Tags</span>
              <input
                maxLength={240}
                value={tagsText}
                onChange={(event) => setTagsText(event.target.value)}
                placeholder="travel, home, renewal"
              />
            </label>
          ) : null}

          <ProtectedRecordFields
            input={protectedForm}
            isEditing={isEditing}
            recordType={form.record_type}
            onChange={updateProtectedField}
          />

          {validationError ? <p className="field-error">{validationError}</p> : null}

          <button className="primary-button" type="submit" disabled={isSaving}>
            {isEditing ? <Save size={18} aria-hidden="true" /> : <Plus size={18} aria-hidden="true" />}
            {isSaving ? 'Saving' : isEditing ? 'Save record' : 'Add record'}
          </button>
        </div>

        <div
          className="record-form-tab-panel"
          hidden={activeTab !== 'documents'}
          id="record-form-documents-panel"
          role="tabpanel"
          aria-labelledby="record-form-documents-tab"
        >
          {record ? (
            <RecordDocumentsPanel isActive={isOpen && activeTab === 'documents'} mode="edit" recordId={record.id} />
          ) : (
            <section className="record-documents-unavailable" aria-label="Documents unavailable until saved">
              <FileUp size={28} aria-hidden="true" />
              <div>
                <h3>Save the record first</h3>
                <p>Documents can be added after LifeLedger creates the record and can verify ownership.</p>
              </div>
            </section>
          )}
        </div>
      </form>
    </SheetDrawer>
  )
}

function RecordFieldGrid({
  fields,
  form,
  onChange,
}: {
  fields: RecordField[]
  form: RecordInput
  onChange: (field: keyof RecordInput, value: string | null) => void
}) {
  const visibleFields = fields.filter((field) => field !== 'location_hint' || form.record_type !== 'subscription')

  if (visibleFields.length === 0) {
    return null
  }

  return (
    <div className="record-form-grid">
      {visibleFields.map((field) =>
        dateFields.includes(field) ? (
          <RecordDateField field={field} form={form} key={field} onChange={onChange} />
        ) : (
          <RecordTextField field={field} form={form} definitionType={form.record_type} key={field} onChange={onChange} />
        ),
      )}
    </div>
  )
}

function ProtectedRecordFields({
  input,
  isEditing,
  onChange,
  recordType,
}: {
  input: ProtectedRecordInput
  isEditing: boolean
  onChange: (field: ProtectedRecordField, value: string | null) => void
  recordType: RecordType
}) {
  const definition = getRecordTypeDefinition(recordType)

  if (definition.protectedFields.length === 0) {
    return null
  }

  return (
    <section className="record-protected-section" aria-labelledby="record-protected-heading">
      <div className="record-protected-header">
        <div>
          <h3 id="record-protected-heading">Protected details</h3>
          <p>Encrypted before storage and revealed only when requested.</p>
        </div>
        <ShieldCheck size={17} aria-hidden="true" />
      </div>
      {isEditing ? <p className="record-protected-edit-note">Leave blank to keep existing protected details.</p> : null}
      <div className="record-form-grid">
        {definition.protectedFields.map((field) =>
          field === 'sensitive_notes' ? (
            <label className="record-protected-wide-field" key={field}>
              <span>{getProtectedFieldLabel(field)}</span>
              <textarea
                maxLength={1000}
                rows={3}
                value={getProtectedTextValue(input, field)}
                onChange={(event) => onChange(field, event.target.value || null)}
              />
            </label>
          ) : (
            <label key={field}>
              <span>{getProtectedFieldLabel(field)}</span>
              <input
                maxLength={field === 'vin' ? 17 : 120}
                value={getProtectedTextValue(input, field)}
                onChange={(event) => onChange(field, event.target.value || null)}
              />
            </label>
          ),
        )}
      </div>
    </section>
  )
}

function RecordTextField({
  field,
  form,
  definitionType,
  onChange,
}: {
  field: RecordField
  form: RecordInput
  definitionType: RecordType
  onChange: (field: keyof RecordInput, value: string | null) => void
}) {
  const definition = getRecordTypeDefinition(definitionType)

  return (
    <label>
      <span>{getFieldLabel(field, definitionType)}</span>
      <input
        maxLength={field === 'location_hint' ? 240 : 160}
        value={getTextValue(form, field)}
        onChange={(event) => onChange(field, event.target.value || null)}
        placeholder={definition.placeholders?.[field] ?? getFieldPlaceholder(field)}
      />
    </label>
  )
}

function RecordDateField({
  field,
  form,
  onChange,
}: {
  field: RecordField
  form: RecordInput
  onChange: (field: keyof RecordInput, value: string | null) => void
}) {
  return (
    <label>
      <span>{getFieldLabel(field, form.record_type)}</span>
      <input
        type="date"
        value={getTextValue(form, field)}
        onChange={(event) => onChange(field, event.target.value || null)}
      />
    </label>
  )
}

function RecordTextArea({
  field,
  form,
  definitionType,
  onChange,
}: {
  field: RecordField
  form: RecordInput
  definitionType: RecordType
  onChange: (field: keyof RecordInput, value: string | null) => void
}) {
  return (
    <label>
      <span>{getFieldLabel(field, definitionType)}</span>
      <textarea
        maxLength={1000}
        value={getTextValue(form, field)}
        onChange={(event) => onChange(field, event.target.value || null)}
        rows={4}
        placeholder="Optional safe notes"
      />
    </label>
  )
}

function getTextValue(form: RecordInput, field: RecordField) {
  const value = form[field]
  return typeof value === 'string' ? value : ''
}

function getProtectedTextValue(form: ProtectedRecordInput, field: ProtectedRecordField) {
  const value = form[field]
  return typeof value === 'string' ? value : ''
}

function getFieldLabel(field: RecordField, type: RecordType) {
  const definition = getRecordTypeDefinition(type)
  if (definition.labels?.[field]) {
    return definition.labels[field]
  }

  const labels: Record<RecordField, string> = {
    subtitle: 'Subtitle',
    owner_name: 'Owner/person',
    provider_or_brand: 'Provider or brand',
    start_date: 'Start date',
    issue_date: 'Issue date',
    expiration_date: 'Expiration date',
    purchase_date: 'Purchase date',
    renewal_date: 'Renewal date',
    location_hint: 'Location hint',
    notes: 'Notes',
    tags: 'Tags',
  }

  return labels[field]
}

function getFieldPlaceholder(field: RecordField) {
  const placeholders: Partial<Record<RecordField, string>> = {
    subtitle: 'Short context',
    owner_name: 'Owner',
    provider_or_brand: 'Provider, issuer, or brand',
    location_hint: 'Where to find it',
  }

  return placeholders[field] ?? ''
}
