import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { AlertCircle, Clock3, FileText, FileUp, Plus, Save, ShieldCheck, Trash2, X } from 'lucide-react'

import {
  attachmentAccept,
  attachmentMaxPerRecord,
  formatAttachmentSize,
  validateAttachmentFile,
} from '../lib/attachmentFiles'
import {
  createRecordInput,
  getRecordTypeDefinition,
  normalizeRecordInput,
  recordToInput,
  tagsFromText,
  tagsToText,
  type RecordField,
} from '../lib/recordTypes'
import type { LifeRecord, ProtectedRecordInput, RecordInput, RecordType } from '../types/record'
import type { Reminder } from '../types/reminder'
import { LinkedItemsPanel } from './LinkedItemsPanel'
import { RecordDocumentsPanel } from './RecordDocumentsPanel'
import { SheetDrawer } from './SheetDrawer'

interface RecordFormProps {
  isOpen: boolean
  isSaving: boolean
  record: LifeRecord | null
  records: LifeRecord[]
  recordType: RecordType
  reminders: Reminder[]
  onClose: () => void
  onCreate: (input: RecordInput, protectedInput: ProtectedRecordInput, files: File[]) => Promise<boolean>
  onUpdate: (id: string, input: RecordInput, protectedInput: ProtectedRecordInput) => Promise<boolean>
}

interface StagedAttachment {
  id: string
  file: File
  previewUrl: string | null
}

const dateFields: RecordField[] = ['start_date', 'issue_date', 'expiration_date', 'purchase_date', 'renewal_date']
type RecordFormTab = 'record' | 'documents' | 'links'

export function RecordForm({
  isOpen,
  isSaving,
  record,
  records,
  recordType,
  reminders,
  onClose,
  onCreate,
  onUpdate,
}: RecordFormProps) {
  const [form, setForm] = useState<RecordInput>(() => createRecordInput(recordType))
  const [activeTab, setActiveTab] = useState<RecordFormTab>('record')
  const [tagsText, setTagsText] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const [stagedAttachments, setStagedAttachments] = useState<StagedAttachment[]>([])
  const [stagedError, setStagedError] = useState<string | null>(null)
  const formBodyRef = useRef<HTMLFormElement | null>(null)
  const stagedFileInputRef = useRef<HTMLInputElement | null>(null)
  const [visibleOptionalFields, setVisibleOptionalFields] = useState<Set<RecordField>>(() => new Set())
  const definition = getRecordTypeDefinition(form.record_type)
  const isEditing = record !== null

  function clearStagedAttachments() {
    setStagedAttachments((current) => {
      for (const item of current) {
        if (item.previewUrl) {
          URL.revokeObjectURL(item.previewUrl)
        }
      }
      return []
    })
    setStagedError(null)
    if (stagedFileInputRef.current) {
      stagedFileInputRef.current.value = ''
    }
  }

  useEffect(() => {
    if (!isOpen) {
      setValidationError(null)
      setActiveTab('record')
      clearStagedAttachments()
      return
    }

    const nextForm = record ? recordToInput(record) : createRecordInput(recordType)
    setForm(nextForm)
    setTagsText(tagsToText(nextForm.tags))
    setVisibleOptionalFields(getInitialVisibleFields(nextForm, getRecordTypeDefinition(nextForm.record_type)))
    setValidationError(null)
    setActiveTab('record')
    clearStagedAttachments()
  }, [isOpen, record, recordType])

  useEffect(() => {
    return () => {
      setStagedAttachments((current) => {
        for (const item of current) {
          if (item.previewUrl) {
            URL.revokeObjectURL(item.previewUrl)
          }
        }
        return current
      })
    }
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const input = normalizeRecordInput({ ...form, tags: tagsFromText(tagsText) })
    if (!input.title) {
      setActiveTab('record')
      setValidationError('Title is required.')
      return
    }

    setValidationError(null)
    const protectedInput: ProtectedRecordInput = {}
    const wasSaved = record
      ? await onUpdate(record.id, input, protectedInput)
      : await onCreate(input, protectedInput, stagedAttachments.map((item) => item.file))

    if (wasSaved) {
      onClose()
    }
  }

  function handleChooseStagedAttachment() {
    setStagedError(null)
    stagedFileInputRef.current?.click()
  }

  function handleStagedFilesSelected(event: ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.currentTarget.files ?? [])
    event.currentTarget.value = ''
    if (selectedFiles.length === 0) {
      return
    }

    const accepted: StagedAttachment[] = []
    let count = stagedAttachments.length
    let nextError: string | null = null

    for (const file of selectedFiles) {
      const fileValidationError = validateAttachmentFile(file, count)
      if (fileValidationError) {
        nextError = fileValidationError
        break
      }
      accepted.push({
        id: crypto.randomUUID(),
        file,
        previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : null,
      })
      count += 1
    }

    if (accepted.length > 0) {
      setStagedAttachments((current) => [...current, ...accepted])
    }
    setStagedError(nextError)
  }

  function handleRemoveStagedAttachment(id: string) {
    setStagedAttachments((current) => {
      const target = current.find((item) => item.id === id)
      if (target?.previewUrl) {
        URL.revokeObjectURL(target.previewUrl)
      }
      return current.filter((item) => item.id !== id)
    })
    setStagedError(null)
  }

  function updateField(field: keyof RecordInput, value: string | null) {
    setForm((current) => ({ ...current, [field]: value }))
  }


  function showOptionalField(field: RecordField) {
    setVisibleOptionalFields((current) => new Set([...current, field]))
  }

  function selectTab(tab: RecordFormTab) {
    setActiveTab(tab)
    formBodyRef.current?.scrollTo({ top: 0 })
  }

  const visibleRecordFields = definition.fields.filter((field) => visibleOptionalFields.has(field))
  const visibleEssentialFields = visibleRecordFields.filter((field) =>
    !dateFields.includes(field) &&
    field !== 'notes' &&
    field !== 'tags' &&
    (definition.coreFields.includes(field) || definition.defaultSuggestedFields.includes(field)),
  )
  const visibleDateFields = visibleRecordFields.filter((field) => dateFields.includes(field))
  const visibleAdditionalFields = visibleRecordFields.filter((field) =>
    !visibleEssentialFields.includes(field) &&
    !dateFields.includes(field) &&
    field !== 'notes' &&
    field !== 'tags',
  )
  const hiddenSuggestedFields = definition.fields.filter((field) =>
    field !== 'notes' && field !== 'tags' && !visibleOptionalFields.has(field),
  )
  const canShowNotes = definition.fields.includes('notes') && (visibleOptionalFields.has('notes') || Boolean(form.notes))
  const canShowTags = definition.fields.includes('tags') && (visibleOptionalFields.has('tags') || tagsText.trim().length > 0)

  return (
    <SheetDrawer
      className="add-dialog record-form-dialog"
      isOpen={isOpen}
      labelledBy="record-form-heading"
      onClose={onClose}
    >
      <div className="sheet-header">
        <div>
          <h2 id="record-form-heading">{isEditing ? `Edit ${record.title}` : `Add ${definition.label}`}</h2>
          <p>{definition.category}</p>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close record form">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <form className="reminder-form sheet-body record-form" ref={formBodyRef} onSubmit={handleSubmit}>
        <div className={record ? 'record-form-tabs record-form-tabs-three' : 'record-form-tabs'} role="tablist" aria-label="Edit record sections">
          <button
            type="button"
            className={activeTab === 'record' ? 'record-form-tab active' : 'record-form-tab'}
            id="record-form-record-tab"
            role="tab"
            aria-selected={activeTab === 'record'}
            aria-controls="record-form-record-panel"
            onClick={() => selectTab('record')}
          >
            Details
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
          {record ? (
            <button
              type="button"
              className={activeTab === 'links' ? 'record-form-tab active' : 'record-form-tab'}
              id="record-form-links-tab"
              role="tab"
              aria-selected={activeTab === 'links'}
              aria-controls="record-form-links-panel"
              onClick={() => selectTab('links')}
            >
              Linked items
            </button>
          ) : null}
        </div>

        <div
          className="record-form-tab-panel"
          hidden={activeTab !== 'record'}
          id="record-form-record-panel"
          role="tabpanel"
          aria-labelledby="record-form-record-tab"
        >
          <section className="record-progressive-section record-essentials-section" aria-labelledby="record-essentials-heading">
            <div className="form-section-heading">
              <span id="record-essentials-heading">Essentials</span>
            </div>
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

            <RecordFieldGrid fields={visibleEssentialFields} form={form} onChange={updateField} />
          </section>

          {(visibleDateFields.length > 0 || hiddenSuggestedFields.some((field) => dateFields.includes(field))) ? (
            <details className="record-progressive-section record-collapsible-section">
              <summary>Dates</summary>
              <RecordFieldGrid fields={visibleDateFields} form={form} onChange={updateField} />
              <SuggestedFieldButtons
                fields={hiddenSuggestedFields.filter((field) => dateFields.includes(field))}
                recordType={form.record_type}
                onAdd={showOptionalField}
              />
            </details>
          ) : null}

          {(visibleAdditionalFields.length > 0 || hiddenSuggestedFields.some((field) => !dateFields.includes(field))) ? (
            <details className="record-progressive-section record-collapsible-section">
              <summary>Additional details</summary>
              <RecordFieldGrid fields={visibleAdditionalFields} form={form} onChange={updateField} />
              <SuggestedFieldButtons
                fields={hiddenSuggestedFields.filter((field) => !dateFields.includes(field))}
                recordType={form.record_type}
                onAdd={showOptionalField}
              />
            </details>
          ) : null}

          {(canShowNotes || canShowTags || definition.fields.includes('notes') || definition.fields.includes('tags')) ? (
            <details className="record-progressive-section record-collapsible-section">
              <summary>Notes</summary>
              {canShowNotes ? (
                <RecordTextArea field="notes" form={form} definitionType={form.record_type} onChange={updateField} />
              ) : null}
              {canShowTags ? (
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
              <SuggestedFieldButtons
                fields={(['notes', 'tags'] as RecordField[]).filter((field) => definition.fields.includes(field) && !visibleOptionalFields.has(field))}
                recordType={form.record_type}
                onAdd={showOptionalField}
              />
            </details>
          ) : null}

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
            <StagedAttachmentsPanel
              attachments={stagedAttachments}
              error={stagedError}
              onChoose={handleChooseStagedAttachment}
              onRemove={handleRemoveStagedAttachment}
            />
          )}
        </div>

        {record ? (
          <div
            className="record-form-tab-panel"
            hidden={activeTab !== 'links'}
            id="record-form-links-panel"
            role="tabpanel"
            aria-labelledby="record-form-links-tab"
          >
            <LinkedItemsPanel
              records={records}
              reminders={reminders}
              showAdd
              tabLayout
              sourceId={record.id}
              sourceType="record"
            />
          </div>
        ) : null}
      </form>

      <input
        type="file"
        multiple
        accept={attachmentAccept}
        className="attachment-file-input"
        ref={stagedFileInputRef}
        onChange={handleStagedFilesSelected}
      />
    </SheetDrawer>
  )
}

function getInitialVisibleFields(input: RecordInput, definition: ReturnType<typeof getRecordTypeDefinition>) {
  const visibleFields = new Set<RecordField>()

  for (const field of definition.fields) {
    if (definition.coreFields.includes(field) || definition.defaultSuggestedFields.includes(field) || hasRecordFieldValue(input, field)) {
      visibleFields.add(field)
    }
  }

  return visibleFields
}

function hasRecordFieldValue(input: RecordInput, field: RecordField) {
  const value = input[field]
  if (Array.isArray(value)) {
    return value.length > 0
  }
  return typeof value === 'string' && value.trim().length > 0
}
function StagedAttachmentsPanel({
  attachments,
  error,
  onChoose,
  onRemove,
}: {
  attachments: StagedAttachment[]
  error: string | null
  onChoose: () => void
  onRemove: (id: string) => void
}) {
  const canAddAttachment = attachments.length < attachmentMaxPerRecord

  return (
    <section className="documents-panel documents-panel-create" aria-label="Attachments">
      <div className="documents-panel-header">
        <div className="documents-title-lockup">
          <span className="documents-title-icon" aria-hidden="true">
            <ShieldCheck size={18} />
          </span>
          <div>
            <h3>Attachments</h3>
            <p>Files upload automatically and are scanned right after LifeLedger saves this record.</p>
          </div>
        </div>
        <button
          type="button"
          className="primary-button documents-add-button"
          disabled={!canAddAttachment}
          onClick={onChoose}
        >
          <FileUp size={16} aria-hidden="true" />
          Add attachment
        </button>
      </div>

      <div className="documents-meta-strip" aria-label="Attachment limits">
        <span>{attachments.length} of {attachmentMaxPerRecord}</span>
        <span>PDF, JPEG, PNG</span>
        <span>10 MB max</span>
      </div>

      {error ? (
        <p className="field-error document-inline-message" role="alert">
          <AlertCircle size={14} aria-hidden="true" />
          {error}
        </p>
      ) : null}

      {attachments.length === 0 ? (
        <div className="documents-empty-state">
          <FileUp size={28} aria-hidden="true" />
          <div>
            <strong>No attachments yet</strong>
            <p>Add a scanned PDF, JPEG, or PNG. They upload as soon as the record is created.</p>
          </div>
          <button type="button" className="secondary-button" disabled={!canAddAttachment} onClick={onChoose}>
            <FileUp size={16} aria-hidden="true" />
            Add attachment
          </button>
        </div>
      ) : (
        <div className="documents-grid" aria-label="Attachments ready to upload">
          {attachments.map((attachment) => (
            <StagedAttachmentCard attachment={attachment} key={attachment.id} onRemove={() => onRemove(attachment.id)} />
          ))}
        </div>
      )}
    </section>
  )
}

function StagedAttachmentCard({
  attachment,
  onRemove,
}: {
  attachment: StagedAttachment
  onRemove: () => void
}) {
  const isImage = attachment.file.type.startsWith('image/')
  const isPdf = attachment.file.type === 'application/pdf'

  return (
    <article className="document-card">
      <div className="document-card-open document-card-static">
        {isImage && attachment.previewUrl ? (
          <span className="document-thumbnail document-thumbnail-image">
            <img src={attachment.previewUrl} alt="" />
          </span>
        ) : (
          <span className="document-thumbnail document-thumbnail-muted" aria-hidden="true">
            <FileText size={22} />
            {isPdf ? <span className="document-file-type-pill">PDF</span> : null}
          </span>
        )}
        <span className="document-card-copy">
          <strong>{attachment.file.name}</strong>
          <span>{formatAttachmentSize(attachment.file.size)}</span>
          <small className="document-status document-status-scanning">
            <Clock3 size={13} aria-hidden="true" />
            Ready to upload
          </small>
        </span>
      </div>

      <div className="document-card-actions" aria-label={`Actions for ${attachment.file.name}`}>
        <button
          type="button"
          className="icon-button document-action-button document-delete-button"
          onClick={onRemove}
          aria-label={`Remove ${attachment.file.name}`}
        >
          <Trash2 size={16} aria-hidden="true" />
        </button>
      </div>
    </article>
  )
}

function SuggestedFieldButtons({
  fields,
  onAdd,
  recordType,
}: {
  fields: RecordField[]
  onAdd: (field: RecordField) => void
  recordType: RecordType
}) {
  if (fields.length === 0) {
    return null
  }

  return (
    <div className="record-suggested-fields" aria-label="Suggested fields">
      {fields.map((field) => (
        <button type="button" className="small-outline-button" key={field} onClick={() => onAdd(field)}>
          <Plus size={14} aria-hidden="true" />
          {getFieldLabel(field, recordType)}
        </button>
      ))}
    </div>
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
