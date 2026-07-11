import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Plus, Save, ShieldCheck, X } from 'lucide-react'

import {
  createRecordInput,
  getRecordTypeDefinition,
  normalizeRecordInput,
  recordToInput,
  tagsFromText,
  tagsToText,
  type RecordField,
} from '../lib/recordTypes'
import type { LifeRecord, RecordInput, RecordType } from '../types/record'
import { SheetDrawer } from './SheetDrawer'

interface RecordFormProps {
  isOpen: boolean
  isSaving: boolean
  record: LifeRecord | null
  recordType: RecordType
  onClose: () => void
  onCreate: (input: RecordInput) => Promise<boolean>
  onUpdate: (id: string, input: RecordInput) => Promise<boolean>
}

const dateFields: RecordField[] = ['start_date', 'issue_date', 'expiration_date', 'purchase_date', 'renewal_date']

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
  const [tagsText, setTagsText] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const definition = getRecordTypeDefinition(form.record_type)
  const Icon = definition.icon
  const isEditing = record !== null

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const nextForm = record ? recordToInput(record) : createRecordInput(recordType)
    setForm(nextForm)
    setTagsText(tagsToText(nextForm.tags))
    setValidationError(null)
  }, [isOpen, record, recordType])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const input = normalizeRecordInput({ ...form, tags: tagsFromText(tagsText) })
    if (!input.title) {
      setValidationError('Title is required.')
      return
    }

    setValidationError(null)
    const wasSaved = record ? await onUpdate(record.id, input) : await onCreate(input)

    if (wasSaved) {
      onClose()
    }
  }

  function updateField(field: keyof RecordInput, value: string | null) {
    setForm((current) => ({ ...current, [field]: value }))
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

      <form className="reminder-form sheet-body record-form" onSubmit={handleSubmit}>
        <section className="record-safety-note" aria-label="Record privacy guardrails">
          <ShieldCheck size={16} aria-hidden="true" />
          <span>Keep numbers, passwords, account details, and document identifiers out of records.</span>
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

        {validationError ? <p className="field-error">{validationError}</p> : null}

        <button className="primary-button" type="submit" disabled={isSaving}>
          {isEditing ? <Save size={18} aria-hidden="true" /> : <Plus size={18} aria-hidden="true" />}
          {isSaving ? 'Saving' : isEditing ? 'Save record' : 'Add record'}
        </button>
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
