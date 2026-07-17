import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { AlertCircle, Bell, Clock3, FileText, FileUp, Link2, Plus, Save, ShieldCheck, Trash2, X } from 'lucide-react'

import { linkedItemsApi } from '../api/linkedItemsApi'
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
import { formatDueDateLabel, getReminderTypeLabel } from '../lib/reminderDisplay'
import { relationshipLabels, type LinkedItem, type LinkedItemsResponse, type LinkCreateRequest, type RelationshipType } from '../types/linkedItem'
import type { LifeRecord, ProtectedRecordInput, RecordInput, RecordType } from '../types/record'
import type { Reminder } from '../types/reminder'
import { AddLinkedItemDrawer, LinkedItemsPanel, type LinkDraft } from './LinkedItemsPanel'
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
  onCreate: (input: RecordInput, protectedInput: ProtectedRecordInput, files: File[], links: LinkCreateRequest[]) => Promise<boolean>
  onOpenRecord?: (recordId: string) => void
  onOpenReminder?: (reminderId: string) => void
  onUpdate: (id: string, input: RecordInput, protectedInput: ProtectedRecordInput) => Promise<boolean>
}

interface StagedAttachment {
  id: string
  file: File
  previewUrl: string | null
}

interface StagedLink {
  id: string
  targetType: LinkDraft['targetType']
  targetId: string
  relationshipType: RelationshipType
  label: string | null
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
  onOpenRecord,
  onOpenReminder,
  onUpdate,
}: RecordFormProps) {
  const [form, setForm] = useState<RecordInput>(() => createRecordInput(recordType))
  const [activeTab, setActiveTab] = useState<RecordFormTab>('record')
  const [tagsText, setTagsText] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const [stagedAttachments, setStagedAttachments] = useState<StagedAttachment[]>([])
  const [stagedError, setStagedError] = useState<string | null>(null)
  const [stagedLinks, setStagedLinks] = useState<StagedLink[]>([])
  const [isStagedLinkPickerOpen, setIsStagedLinkPickerOpen] = useState(false)
  const formBodyRef = useRef<HTMLDivElement | null>(null)
  const stagedFileInputRef = useRef<HTMLInputElement | null>(null)
  const initialLinksRef = useRef<LinkedItemsResponse | null>(null)
  const wasSavedRef = useRef(false)
  const isClosingRef = useRef(false)
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
      setStagedLinks([])
      setIsStagedLinkPickerOpen(false)
      return
    }

    wasSavedRef.current = false
    isClosingRef.current = false
    initialLinksRef.current = null
    const nextForm = record ? recordToInput(record) : createRecordInput(recordType)
    setForm(nextForm)
    setTagsText(tagsToText(nextForm.tags))
    setVisibleOptionalFields(getInitialVisibleFields(nextForm, getRecordTypeDefinition(nextForm.record_type)))
    setValidationError(null)
    setActiveTab('record')
    clearStagedAttachments()
    setStagedLinks([])
    setIsStagedLinkPickerOpen(false)
  }, [isOpen, record, recordType])

  useEffect(() => {
    if (!isOpen || !record) {
      initialLinksRef.current = null
      return
    }

    let isCancelled = false
    const recordId = record.id

    async function loadInitialLinks() {
      try {
        const links = await linkedItemsApi.listRecordLinks(recordId)
        if (!isCancelled) {
          initialLinksRef.current = links
        }
      } catch {
        if (!isCancelled) {
          initialLinksRef.current = null
        }
      }
    }

    void loadInitialLinks()

    return () => {
      isCancelled = true
    }
  }, [isOpen, record])

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
      formBodyRef.current?.scrollTo({ top: 0 })
      setValidationError('Title is required.')
      return
    }

    setValidationError(null)
    const protectedInput: ProtectedRecordInput = {}
    const wasSaved = record
      ? await onUpdate(record.id, input, protectedInput)
      : await onCreate(
        input,
        protectedInput,
        stagedAttachments.map((item) => item.file),
        stagedLinks.map(toLinkCreateRequest),
      )

    if (wasSaved) {
      wasSavedRef.current = true
      onClose()
    }
  }

  async function handleRequestClose() {
    if (isClosingRef.current) {
      return
    }

    isClosingRef.current = true
    try {
      if (record && !wasSavedRef.current && initialLinksRef.current) {
        await restoreRecordLinks(record.id, initialLinksRef.current)
      }
    } finally {
      onClose()
      isClosingRef.current = false
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

  async function handleStageLink(input: LinkDraft) {
    setStagedLinks((current) => {
      if (current.some((item) => item.targetType === input.targetType && item.targetId === input.targetId)) {
        return current
      }

      return [
        ...current,
        {
          id: crypto.randomUUID(),
          ...input,
        },
      ]
    })
    setIsStagedLinkPickerOpen(false)
  }

  function handleRemoveStagedLink(id: string) {
    setStagedLinks((current) => current.filter((item) => item.id !== id))
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
      onClose={() => void handleRequestClose()}
    >
      <div className="sheet-header">
        <div>
          <h2 id="record-form-heading">{isEditing ? `Edit ${record.title}` : `Add ${definition.label}`}</h2>
          <p>{definition.category}</p>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={() => void handleRequestClose()} aria-label="Close record form">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <form className="record-form-shell" onSubmit={handleSubmit}>
        <div className="reminder-form sheet-body record-form" data-drawer-scroll ref={formBodyRef}>
          <div className="record-form-tabs record-form-tabs-three" role="tablist" aria-label="Edit record sections">
            <button
              type="button"
              className={activeTab === 'record' ? 'record-form-tab active' : 'record-form-tab'}
              id="record-form-record-tab"
              role="tab"
              aria-selected={activeTab === 'record'}
              aria-controls="record-form-record-panel"
              onClick={() => selectTab('record')}
            >
              Overview
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

          <div
            className="record-form-tab-panel"
            hidden={activeTab !== 'links'}
            id="record-form-links-panel"
            role="tabpanel"
            aria-labelledby="record-form-links-tab"
          >
            {record ? (
              <LinkedItemsPanel
                records={records}
                reminders={reminders}
                showAdd
                tabLayout
                sourceId={record.id}
                sourceType="record"
                onOpenRecord={onOpenRecord}
                onOpenReminder={onOpenReminder}
              />
            ) : (
              <StagedLinkedItemsPanel
                records={records}
                reminders={reminders}
                stagedLinks={stagedLinks}
                onAdd={() => setIsStagedLinkPickerOpen(true)}
                onRemove={handleRemoveStagedLink}
              />
            )}
          </div>
        </div>

        <div className="sheet-footer record-form-footer">
          <button className="primary-button" type="submit" disabled={isSaving}>
            {isEditing ? <Save size={18} aria-hidden="true" /> : <Plus size={18} aria-hidden="true" />}
            {isSaving ? 'Saving' : isEditing ? 'Save record' : 'Add record'}
          </button>
        </div>
      </form>

      {!record ? (
        <AddLinkedItemDrawer
          currentRecordId={null}
          isOpen={isStagedLinkPickerOpen}
          linkedRecordIds={new Set(stagedLinks.filter((item) => item.targetType === 'record').map((item) => item.targetId))}
          linkedReminderIds={new Set(stagedLinks.filter((item) => item.targetType === 'reminder').map((item) => item.targetId))}
          records={records}
          reminders={reminders}
          onClose={() => setIsStagedLinkPickerOpen(false)}
          onCreate={handleStageLink}
        />
      ) : null}

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

function toLinkCreateRequest(link: StagedLink): LinkCreateRequest {
  return {
    target_type: link.targetType,
    target_id: link.targetId,
    relationship_type: link.relationshipType,
    label: link.label,
  }
}

async function restoreRecordLinks(recordId: string, initialLinks: LinkedItemsResponse) {
  const currentLinks = await linkedItemsApi.listRecordLinks(recordId)
  const initialItems = flattenLinkedItems(initialLinks)
  const currentItems = flattenLinkedItems(currentLinks)
  const initialKeys = new Set(initialItems.map(getLinkedItemComparisonKey))
  const currentKeys = new Set(currentItems.map(getLinkedItemComparisonKey))

  for (const item of currentItems) {
    if (!initialKeys.has(getLinkedItemComparisonKey(item))) {
      await linkedItemsApi.deleteRecordLink(recordId, item.link_id)
    }
  }

  for (const item of initialItems) {
    if (!currentKeys.has(getLinkedItemComparisonKey(item))) {
      await linkedItemsApi.createRecordLink(recordId, {
        target_type: item.linked_entity.entity_type,
        target_id: item.linked_entity.id,
        relationship_type: item.relationship_type,
        label: item.label,
      })
    }
  }
}

function flattenLinkedItems(links: LinkedItemsResponse) {
  return [...links.records, ...links.reminders, ...links.documents]
}

function getLinkedItemComparisonKey(item: LinkedItem) {
  return [
    item.linked_entity.entity_type,
    item.linked_entity.id,
    item.relationship_type,
    item.label ?? '',
  ].join(':')
}

function StagedLinkedItemsPanel({
  onAdd,
  onRemove,
  records,
  reminders,
  stagedLinks,
}: {
  records: LifeRecord[]
  reminders: Reminder[]
  stagedLinks: StagedLink[]
  onAdd: () => void
  onRemove: (id: string) => void
}) {
  const recordLinks = stagedLinks.filter((link) => link.targetType === 'record')
  const reminderLinks = stagedLinks.filter((link) => link.targetType === 'reminder')
  const hasLinks = stagedLinks.length > 0

  return (
    <section className="detail-section linked-items-section linked-items-staged-section" aria-label="Linked items">
      <div className="linked-items-header">
        <div>
          <h3>Linked items</h3>
          <p>Choose records or reminders now. LifeLedger will link them after this record is saved.</p>
        </div>
        <button type="button" className="small-outline-button linked-items-add-button" onClick={onAdd}>
          <Plus size={14} aria-hidden="true" />
          Link item
        </button>
      </div>

      {!hasLinks ? (
        <div className="linked-items-empty-state">
          <Link2 size={24} aria-hidden="true" />
          <p>No linked items staged yet.</p>
          <button type="button" className="secondary-button" onClick={onAdd}>
            <Plus size={16} aria-hidden="true" />
            Link an item
          </button>
        </div>
      ) : null}

      {recordLinks.length > 0 ? (
        <StagedLinkGroup
          records={records}
          reminders={reminders}
          stagedLinks={recordLinks}
          title="Linked records"
          onRemove={onRemove}
        />
      ) : null}

      {reminderLinks.length > 0 ? (
        <StagedLinkGroup
          records={records}
          reminders={reminders}
          stagedLinks={reminderLinks}
          title="Linked reminders"
          onRemove={onRemove}
        />
      ) : null}
    </section>
  )
}

function StagedLinkGroup({
  onRemove,
  records,
  reminders,
  stagedLinks,
  title,
}: {
  records: LifeRecord[]
  reminders: Reminder[]
  stagedLinks: StagedLink[]
  title: string
  onRemove: (id: string) => void
}) {
  return (
    <div className="linked-items-group" aria-label={title}>
      <div className="linked-items-group-header">
        <h4>{title}</h4>
        <span>{stagedLinks.length}</span>
      </div>
      <div className="linked-items-list">
        {stagedLinks.map((link) => (
          <StagedLinkCard
            key={link.id}
            link={link}
            records={records}
            reminders={reminders}
            onRemove={() => onRemove(link.id)}
          />
        ))}
      </div>
    </div>
  )
}

function StagedLinkCard({
  link,
  onRemove,
  records,
  reminders,
}: {
  link: StagedLink
  records: LifeRecord[]
  reminders: Reminder[]
  onRemove: () => void
}) {
  const record = link.targetType === 'record' ? records.find((item) => item.id === link.targetId) ?? null : null
  const reminder = link.targetType === 'reminder' ? reminders.find((item) => item.id === link.targetId) ?? null : null
  const title = record?.title ?? reminder?.title ?? 'Linked item'
  const meta = getStagedLinkMeta(link, record, reminder)
  const Icon = record ? getRecordTypeDefinition(record.record_type).icon : link.targetType === 'reminder' ? Bell : FileText
  const toneClass = record ? `tone-${getRecordTypeDefinition(record.record_type).tone}` : 'tone-other'

  return (
    <article className="linked-item-card">
      <div className="linked-item-main linked-item-main-static" aria-label={title}>
        <span className={`linked-item-icon ${toneClass}`} aria-hidden="true">
          <Icon size={19} />
        </span>
        <span className="linked-item-copy">
          <strong>{title}</strong>
          <span>{meta}</span>
        </span>
      </div>
      <button type="button" className="icon-button linked-item-remove-button" onClick={onRemove} aria-label={`Remove link to ${title}`}>
        <Trash2 size={15} aria-hidden="true" />
      </button>
    </article>
  )
}

function getStagedLinkMeta(link: StagedLink, record: LifeRecord | null, reminder: Reminder | null) {
  const relationship = link.label || relationshipLabels[link.relationshipType]

  if (record) {
    return `${getRecordTypeDefinition(record.record_type).label} - ${relationship}`
  }

  if (reminder) {
    return `${getReminderTypeLabel(reminder.reminder_type)} - ${formatDueDateLabel(reminder.due_date)} - ${relationship}`
  }

  return relationship
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
