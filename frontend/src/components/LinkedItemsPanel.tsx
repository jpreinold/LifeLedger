import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArrowLeft,
  Bell,
  ChevronRight,
  FileText,
  Link2,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react'

import { linkedItemsApi } from '../api/linkedItemsApi'
import { formatDueDateLabel, getReminderTypeLabel } from '../lib/reminderDisplay'
import { getRecordTypeDefinition } from '../lib/recordTypes'
import { getRelationshipPresentation, productTerms } from '../lib/terminology'
import type { LinkedEntityType, LinkedItem, LinkedItemsResponse, RelationshipCandidate, RelationshipType } from '../types/linkedItem'
import type { LifeRecord } from '../types/record'
import type { Reminder } from '../types/reminder'
import { ConfirmDialog } from './ConfirmDialog'
import { SheetDrawer } from './SheetDrawer'

interface LinkedItemsPanelProps {
  documentsCount?: number | null
  records: LifeRecord[]
  reminders: Reminder[]
  showAdd?: boolean
  sourceId: string
  sourceTitle?: string
  sourceType: 'record' | 'reminder'
  title?: string
  tabLayout?: boolean
  onOpenDocument?: (recordId: string, documentId: string) => void
  onOpenRecord?: (recordId: string) => void
  onOpenReminder?: (reminderId: string) => void
}

type AddStep = 'type' | 'select' | 'relationship'
export type CandidateType = LinkedEntityType

export interface LinkDraft {
  targetType: CandidateType
  targetId: string
  relationshipType: RelationshipType
  label: string | null
}

const emptyLinks: LinkedItemsResponse = { records: [], reminders: [], documents: [] }

const relationshipOptions: Array<{ label: string; value: RelationshipType }> = [
  'related',
  'belongs_to',
  'owned_by',
  'covers',
  'provided_by',
  'reminder_for',
  'document_for',
  'insures',
  'warranty_for',
  'maintains',
  'appointment_for',
  'custom',
].map((value) => ({
  label: value === 'custom' ? 'Custom relationship' : getRelationshipPresentation(value),
  value: value as RelationshipType,
}))

export function LinkedItemsPanel({
  documentsCount = null,
  records,
  reminders,
  showAdd = false,
  sourceId,
  sourceTitle,
  sourceType,
  title = productTerms.relatedItems,
  tabLayout = false,
  onOpenDocument,
  onOpenRecord,
  onOpenReminder,
}: LinkedItemsPanelProps) {
  const [links, setLinks] = useState<LinkedItemsResponse>(emptyLinks)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isPickerOpen, setIsPickerOpen] = useState(false)
  const [editingLink, setEditingLink] = useState<LinkedItem | null>(null)
  const [pendingRemove, setPendingRemove] = useState<LinkedItem | null>(null)
  const [isRemoving, setIsRemoving] = useState(false)

  useEffect(() => {
    let isCancelled = false

    async function loadLinks() {
      setIsLoading(true)
      setError(null)
      try {
        const response = sourceType === 'record'
          ? await linkedItemsApi.listRecordLinks(sourceId)
          : await linkedItemsApi.listReminderLinks(sourceId)
        if (!isCancelled) {
          setLinks(normalizeLinks(response))
        }
      } catch (requestError) {
        if (!isCancelled) {
          setLinks(emptyLinks)
          setError(requestError instanceof Error ? requestError.message : 'Unable to load related items.')
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false)
        }
      }
    }

    void loadLinks()

    return () => {
      isCancelled = true
    }
  }, [sourceId, sourceType])

  async function reloadLinks() {
    setError(null)
    const response = sourceType === 'record'
      ? await linkedItemsApi.listRecordLinks(sourceId)
      : await linkedItemsApi.listReminderLinks(sourceId)
    setLinks(normalizeLinks(response))
  }

  async function handleCreateLink(input: { targetType: CandidateType; targetId: string; relationshipType: RelationshipType; label: string | null }) {
    setError(null)
    await linkedItemsApi.createRelationship({
      source_item_type: sourceType,
      source_item_id: sourceId,
      target_item_type: input.targetType,
      target_item_id: input.targetId,
      relationship_type: input.relationshipType,
      custom_label: input.label,
    })
    await reloadLinks()
    setIsPickerOpen(false)
  }

  async function handleEditLink(input: { relationshipType: RelationshipType; label: string | null }) {
    if (!editingLink) {
      return
    }

    setError(null)
    await linkedItemsApi.updateRelationship(editingLink.link_id, {
      relationship_type: input.relationshipType,
      custom_label: input.label,
    })
    await reloadLinks()
    setEditingLink(null)
  }

  async function confirmRemoveLink() {
    if (!pendingRemove) {
      return
    }

    setIsRemoving(true)
    setError(null)
    try {
      await linkedItemsApi.deleteRelationship(pendingRemove.link_id)
      await reloadLinks()
      setPendingRemove(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to remove this relationship.')
    } finally {
      setIsRemoving(false)
    }
  }

  const linkedRecordIds = useMemo(() => new Set(links.records.map((item) => item.linked_entity.id)), [links.records])
  const linkedReminderIds = useMemo(() => new Set(links.reminders.map((item) => item.linked_entity.id)), [links.reminders])
  const linkedDocumentIds = useMemo(() => new Set(links.documents.map((item) => item.linked_entity.id)), [links.documents])
  const hasLinks = links.records.length > 0 || links.reminders.length > 0 || links.documents.length > 0
  const canAdd = showAdd
  const usesTabLayout = tabLayout && sourceType === 'record'
  const overview = sourceType === 'record' ? (
    <div className="linked-overview" aria-label="Related items overview">
      <span><strong>{links.records.length}</strong> Related items</span>
      <span><strong>{links.reminders.length}</strong> Responsibilities</span>
      <span><strong>{links.documents.length}</strong> Related documents</span>
      {documentsCount !== null ? <span><strong>{documentsCount}</strong> Documents</span> : null}
    </div>
  ) : null

  return (
    <section className={`detail-section linked-items-section ${usesTabLayout ? 'linked-items-tab-section' : ''}`.trim()} aria-label={title}>
      {!usesTabLayout ? (
        <div className="linked-items-header">
          <div>
            <h3>{title}</h3>
            <p>{sourceType === 'record' ? 'Items, responsibilities, and documents connected to this item.' : 'Items connected to this reminder.'}</p>
          </div>
          {canAdd ? (
            <button type="button" className="small-outline-button linked-items-add-button" onClick={() => setIsPickerOpen(true)}>
              <Plus size={14} aria-hidden="true" />
              {productTerms.addRelatedItem}
            </button>
          ) : null}
        </div>
      ) : null}

      {!usesTabLayout ? overview : null}
      {isLoading ? <p className="linked-items-state">Loading related items...</p> : null}
      {error ? <p className="field-error linked-items-error" role="alert">{error}</p> : null}

      {!isLoading && !error && !hasLinks ? (
        <div className="linked-items-empty-state">
          <Link2 size={24} aria-hidden="true" />
          <p>Connect related items so LifeLedger can keep the full picture together.</p>
          {canAdd ? (
            <button type="button" className="secondary-button" onClick={() => setIsPickerOpen(true)}>
              <Plus size={16} aria-hidden="true" />
              {productTerms.addRelatedItem}
            </button>
          ) : null}
        </div>
      ) : null}

      {!isLoading && !error && hasLinks ? (
        <>
          <LinkedItemsGroup
            action={canAdd && usesTabLayout ? <AddGroupButton onClick={() => setIsPickerOpen(true)} /> : undefined}
            emptyText="No related items."
            items={links.records}
            title="Items"
            onEdit={setEditingLink}
            onOpen={onOpenRecord}
            onRemove={setPendingRemove}
          />
          <LinkedItemsGroup
            action={canAdd && usesTabLayout ? <AddGroupButton onClick={() => setIsPickerOpen(true)} /> : undefined}
            emptyText="No related responsibilities."
            items={links.reminders}
            title="Responsibilities"
            onEdit={setEditingLink}
            onOpen={onOpenReminder}
            onRemove={setPendingRemove}
          />
          <LinkedItemsGroup
            action={canAdd && usesTabLayout ? <AddGroupButton onClick={() => setIsPickerOpen(true)} /> : undefined}
            emptyText="No related documents."
            items={links.documents}
            title="Documents"
            onEdit={setEditingLink}
            onOpenDocument={onOpenDocument}
            onRemove={setPendingRemove}
          />
          {usesTabLayout ? overview : null}
        </>
      ) : null}

      <AddLinkedItemDrawer
        currentRecordId={sourceType === 'record' ? sourceId : null}
        isOpen={isPickerOpen}
        linkedDocumentIds={linkedDocumentIds}
        linkedRecordIds={linkedRecordIds}
        linkedReminderIds={linkedReminderIds}
        records={records}
        reminders={reminders}
        sourceId={sourceId}
        sourceType={sourceType}
        onClose={() => setIsPickerOpen(false)}
        onCreate={handleCreateLink}
      />

      <EditRelationshipDrawer
        isOpen={editingLink !== null}
        link={editingLink}
        onClose={() => setEditingLink(null)}
        onSave={handleEditLink}
      />

      <ConfirmDialog
        body={getRemoveLinkBody(sourceTitle, pendingRemove)}
        busyLabel="Removing"
        confirmLabel="Remove relationship"
        isBusy={isRemoving}
        isOpen={pendingRemove !== null}
        title="Remove relationship?"
        onCancel={() => setPendingRemove(null)}
        onConfirm={() => void confirmRemoveLink()}
      />
    </section>
  )
}

function LinkedItemsGroup({
  action,
  emptyText,
  items,
  onEdit,
  onOpen,
  onOpenDocument,
  onRemove,
  title,
}: {
  action?: ReactNode
  emptyText: string
  items: LinkedItem[]
  title: string
  onEdit: (item: LinkedItem) => void
  onOpen?: (id: string) => void
  onOpenDocument?: (recordId: string, documentId: string) => void
  onRemove: (item: LinkedItem) => void
}) {
  return (
    <div className="linked-items-group" aria-label={title}>
      <div className="linked-items-group-header">
        <h4>{title}</h4>
        {action ?? <span>{items.length}</span>}
      </div>
      {items.length === 0 ? <p className="linked-items-state linked-items-group-empty">{emptyText}</p> : null}
      {items.length > 0 ? (
        <div className="linked-items-list">
          {items.map((item) => (
            <LinkedItemCard
              item={item}
              key={item.link_id}
              onEdit={() => onEdit(item)}
              onOpen={onOpen}
              onOpenDocument={onOpenDocument}
              onRemove={() => onRemove(item)}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

function AddGroupButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="small-outline-button linked-group-add-button" onClick={onClick}>
      <Plus size={14} aria-hidden="true" />
      Add
    </button>
  )
}

function LinkedItemCard({
  item,
  onEdit,
  onOpen,
  onOpenDocument,
  onRemove,
}: {
  item: LinkedItem
  onEdit: () => void
  onOpen?: (id: string) => void
  onOpenDocument?: (recordId: string, documentId: string) => void
  onRemove: () => void
}) {
  const entity = item.linked_entity
  const Icon = getLinkedItemIcon(item)
  const meta = getLinkedItemMeta(item)
  const canOpen = entity.entity_type === 'document' ? Boolean(entity.document_record_id && onOpenDocument) : Boolean(onOpen)

  function openLinkedItem() {
    if (entity.entity_type === 'document' && entity.document_record_id) {
      onOpenDocument?.(entity.document_record_id, entity.id)
      return
    }
    onOpen?.(entity.id)
  }

  return (
    <article className="linked-item-card">
      <button
        type="button"
        className="linked-item-main"
        disabled={!canOpen}
        onClick={openLinkedItem}
        aria-label={`Open ${entity.title}`}
      >
        <span className={`linked-item-icon ${getLinkedItemToneClass(item)}`} aria-hidden="true">
          <Icon size={19} />
        </span>
        <span className="linked-item-copy">
          <strong>{entity.title}</strong>
          <span>{meta}</span>
        </span>
        {canOpen ? <ChevronRight size={17} aria-hidden="true" className="linked-item-chevron" /> : null}
      </button>
      <span className="linked-item-actions">
        <button type="button" className="icon-button linked-item-edit-button" onClick={onEdit} aria-label={`Edit relationship to ${entity.title}`}>
          <Pencil size={15} aria-hidden="true" />
        </button>
        <button type="button" className="icon-button linked-item-remove-button" onClick={onRemove} aria-label={`Remove relationship to ${entity.title}`}>
          <Trash2 size={15} aria-hidden="true" />
        </button>
      </span>
    </article>
  )
}

export function AddLinkedItemDrawer({
  currentRecordId,
  isOpen,
  linkedDocumentIds = new Set<string>(),
  linkedRecordIds,
  linkedReminderIds,
  records,
  reminders,
  sourceId = currentRecordId,
  sourceType = 'record',
  onClose,
  onCreate,
}: {
  currentRecordId: string | null
  isOpen: boolean
  linkedDocumentIds?: Set<string>
  linkedRecordIds: Set<string>
  linkedReminderIds: Set<string>
  records: LifeRecord[]
  reminders: Reminder[]
  sourceId?: string | null
  sourceType?: 'record' | 'reminder'
  onClose: () => void
  onCreate: (input: LinkDraft) => Promise<void>
}) {
  const [step, setStep] = useState<AddStep>('type')
  const [targetType, setTargetType] = useState<CandidateType | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [relationshipType, setRelationshipType] = useState<RelationshipType>('related')
  const [label, setLabel] = useState('')
  const [search, setSearch] = useState('')
  const [documentCandidates, setDocumentCandidates] = useState<RelationshipCandidate[]>([])
  const [isSearchingDocuments, setIsSearchingDocuments] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState<RelationshipCandidate | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setStep('type')
      setTargetType(null)
      setSelectedId(null)
      setSelectedDocument(null)
      setRelationshipType('related')
      setLabel('')
      setSearch('')
      setDocumentCandidates([])
      setSelectedDocument(null)
      setError(null)
      setIsSaving(false)
      setIsSearchingDocuments(false)
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen || step !== 'select' || targetType !== 'document' || !sourceId) {
      return undefined
    }

    let isCancelled = false
    setIsSearchingDocuments(true)
    setError(null)
    void linkedItemsApi.listCandidates({
      sourceItemType: sourceType,
      sourceItemId: sourceId,
      itemType: 'document',
      query: search,
      limit: 30,
    }).then((response) => {
      if (!isCancelled) {
        setDocumentCandidates(response.items.filter((item) => !linkedDocumentIds.has(item.item_id)))
      }
    }).catch((requestError) => {
      if (!isCancelled) {
        setDocumentCandidates([])
        setError(requestError instanceof Error ? requestError.message : 'Unable to search documents.')
      }
    }).finally(() => {
      if (!isCancelled) {
        setIsSearchingDocuments(false)
      }
    })

    return () => {
      isCancelled = true
    }
  }, [isOpen, linkedDocumentIds, search, sourceId, sourceType, step, targetType])

  const recordCandidates = useMemo(
    () => records
      .filter((record) => record.id !== currentRecordId)
      .filter((record) => record.status !== 'archived')
      .filter((record) => !linkedRecordIds.has(record.id)),
    [currentRecordId, linkedRecordIds, records],
  )
  const reminderCandidates = useMemo(
    () => reminders.filter((reminder) => !linkedReminderIds.has(reminder.id)),
    [linkedReminderIds, reminders],
  )

  const selectedRecord = targetType === 'record' ? recordCandidates.find((record) => record.id === selectedId) ?? null : null
  const selectedReminder = targetType === 'reminder' ? reminderCandidates.find((reminder) => reminder.id === selectedId) ?? null : null
  const selectedTitle = selectedRecord?.title ?? selectedReminder?.title ?? selectedDocument?.title ?? ''

  const filteredRecords = filterRecords(recordCandidates, search)
  const filteredReminders = filterReminders(reminderCandidates, search)

  function chooseType(type: CandidateType) {
    setTargetType(type)
    setSelectedId(null)
    setSelectedDocument(null)
    setRelationshipType(type === 'reminder' ? 'reminder_for' : type === 'document' ? 'document_for' : 'related')
    setSearch('')
    setDocumentCandidates([])
    setStep('select')
  }

  function chooseRecord(record: LifeRecord) {
    setSelectedId(record.id)
    setSelectedDocument(null)
    setRelationshipType(getDefaultRecordRelationship(record))
    setStep('relationship')
  }

  function chooseReminder(reminder: Reminder) {
    setSelectedId(reminder.id)
    setSelectedDocument(null)
    setRelationshipType('reminder_for')
    setStep('relationship')
  }

  function chooseDocument(candidate: RelationshipCandidate) {
    setSelectedId(candidate.item_id)
    setSelectedDocument(candidate)
    setRelationshipType('document_for')
    setStep('relationship')
  }

  function goBack() {
    setError(null)
    if (step === 'relationship') {
      setStep('select')
      return
    }
    if (step === 'select') {
      setStep('type')
      setTargetType(null)
      setSelectedId(null)
      setSelectedDocument(null)
    }
  }

  async function submit() {
    if (!targetType || !selectedId) {
      return
    }

    setIsSaving(true)
    setError(null)
    try {
      await onCreate({
        targetType,
        targetId: selectedId,
        relationshipType,
        label: label.trim() || null,
      })
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to add related item.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <SheetDrawer className="add-dialog linked-picker-dialog" isOpen={isOpen} labelledBy="linked-picker-heading" onClose={onClose}>
      <div className="sheet-header linked-picker-header">
        <div className="linked-picker-title-row">
          {step !== 'type' ? (
            <button type="button" className="icon-button ghost-icon-button linked-picker-back" onClick={goBack} aria-label="Back">
              <ArrowLeft size={18} aria-hidden="true" />
            </button>
          ) : null}
          <div>
            <h2 id="linked-picker-heading">{productTerms.addRelatedItem}</h2>
            <p>{getPickerSubcopy(step, targetType)}</p>
          </div>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close add related item">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="sheet-body linked-picker-body">
        {step === 'type' ? (
          <div className="linked-picker-type-options">
            <button type="button" className="linked-picker-type-card" onClick={() => chooseType('record')}>
              <span className="linked-picker-type-icon linked-picker-record-icon" aria-hidden="true"><FileText size={24} /></span>
              <span><strong>Item</strong><small>Connect another item, such as insurance, a warranty, or a vehicle.</small></span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
            <button type="button" className="linked-picker-type-card" onClick={() => chooseType('reminder')}>
              <span className="linked-picker-type-icon linked-picker-reminder-icon" aria-hidden="true"><Bell size={24} /></span>
              <span><strong>Responsibility</strong><small>Connect a renewal, maintenance date, or other reminder.</small></span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
            {sourceId ? (
              <button type="button" className="linked-picker-type-card" onClick={() => chooseType('document')}>
                <span className="linked-picker-type-icon linked-picker-document-icon" aria-hidden="true"><FileText size={24} /></span>
                <span><strong>Document</strong><small>Connect a document stored with one of your items.</small></span>
                <ChevronRight size={18} aria-hidden="true" />
              </button>
            ) : null}
          </div>
        ) : null}

        {step === 'select' && targetType ? (
          <div className="linked-picker-select-step">
            <label className="linked-picker-search">
              <Search size={16} aria-hidden="true" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={`Search ${targetType === 'document' ? 'documents' : targetType === 'record' ? 'items' : 'responsibilities'}...`}
              />
            </label>
            {targetType === 'record' ? (
              <CandidateList
                emptyText="No items available to connect."
                records={filteredRecords}
                onChooseRecord={chooseRecord}
              />
            ) : null}
            {targetType === 'reminder' ? (
              <CandidateList
                emptyText="No responsibilities available to connect."
                reminders={filteredReminders}
                onChooseReminder={chooseReminder}
              />
            ) : null}
            {targetType === 'document' ? (
              isSearchingDocuments ? <p className="linked-items-state linked-picker-empty">Searching documents...</p> : (
                <CandidateList
                  documents={documentCandidates}
                  emptyText="No documents available to connect."
                  onChooseDocument={chooseDocument}
                />
              )
            ) : null}
            <p className="linked-picker-footnote">Items already related to this item are hidden.</p>
          </div>
        ) : null}

        {step === 'relationship' && targetType && selectedId ? (
          <div className="linked-picker-relationship-step">
            <div className="linked-picker-selected-item">
              <span className="linked-item-icon tone-other" aria-hidden="true">
                {targetType === 'reminder' ? <Bell size={18} /> : <FileText size={18} />}
              </span>
              <div>
                <strong>{selectedTitle}</strong>
                <span>{targetType === 'record' ? selectedRecord ? getRecordTypeDefinition(selectedRecord.record_type).singularLabel : productTerms.item : targetType === 'document' ? productTerms.document : productTerms.responsibility}</span>
              </div>
            </div>

            <p className="linked-picker-default-relationship">Relationship: <strong>{getRelationshipPresentation(relationshipType)}</strong></p>
            <details className="linked-relationship-advanced">
              <summary>Customize relationship</summary>
              <fieldset className="linked-relationship-options">
                <legend>Relationship</legend>
                {relationshipOptions.map((option) => (
                  <label key={option.value}>
                    <input
                      checked={relationshipType === option.value}
                      name="relationship_type"
                      type="radio"
                      value={option.value}
                      onChange={() => setRelationshipType(option.value)}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </fieldset>

              <label className="linked-picker-label-field">
                <span>Custom description</span>
                <input maxLength={40} value={label} onChange={(event) => setLabel(event.target.value)} placeholder="For example, primary insurance" />
                <small>{label.length}/40</small>
              </label>
            </details>

            {error ? <p className="field-error" role="alert">{error}</p> : null}

            <button type="button" className="primary-button" disabled={isSaving} onClick={() => void submit()}>
              <Link2 size={17} aria-hidden="true" />
              {isSaving ? 'Adding...' : productTerms.addRelatedItem}
            </button>
          </div>
        ) : null}
      </div>
    </SheetDrawer>
  )
}

function EditRelationshipDrawer({
  isOpen,
  link,
  onClose,
  onSave,
}: {
  isOpen: boolean
  link: LinkedItem | null
  onClose: () => void
  onSave: (input: { relationshipType: RelationshipType; label: string | null }) => Promise<void>
}) {
  const [relationshipType, setRelationshipType] = useState<RelationshipType>('related')
  const [label, setLabel] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (link) {
      setRelationshipType(link.relationship_type)
      setLabel(link.label ?? '')
      setIsSaving(false)
      setError(null)
    }
  }, [link])

  if (!link) {
    return null
  }

  async function submit() {
    setIsSaving(true)
    setError(null)
    try {
      await onSave({ relationshipType, label: label.trim() || null })
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to update relationship.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <SheetDrawer className="add-dialog linked-picker-dialog" isOpen={isOpen} labelledBy="edit-relationship-heading" onClose={onClose}>
      <div className="sheet-header linked-picker-header">
        <div>
          <h2 id="edit-relationship-heading">Edit relationship</h2>
          <p>{link.linked_entity.title}</p>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close edit relationship">
          <X size={19} aria-hidden="true" />
        </button>
      </div>
      <div className="sheet-body linked-picker-body">
        <div className="linked-picker-relationship-step">
          <fieldset className="linked-relationship-options">
            <legend>How are they related?</legend>
            {relationshipOptions.map((option) => (
              <label key={option.value}>
                <input
                  checked={relationshipType === option.value}
                  name="edit_relationship_type"
                  type="radio"
                  value={option.value}
                  onChange={() => setRelationshipType(option.value)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </fieldset>
          <label className="linked-picker-label-field">
            <span>Optional label</span>
            <input maxLength={40} value={label} onChange={(event) => setLabel(event.target.value)} placeholder="e.g. Primary insurance" />
            <small>{label.length}/40</small>
          </label>
          {error ? <p className="field-error" role="alert">{error}</p> : null}
          <button type="button" className="primary-button" disabled={isSaving} onClick={() => void submit()}>
            <Link2 size={17} aria-hidden="true" />
            {isSaving ? 'Saving...' : 'Save relationship'}
          </button>
        </div>
      </div>
    </SheetDrawer>
  )
}

function CandidateList({
  documents = [],
  emptyText,
  records = [],
  reminders = [],
  onChooseDocument,
  onChooseRecord,
  onChooseReminder,
}: {
  documents?: RelationshipCandidate[]
  emptyText: string
  records?: LifeRecord[]
  reminders?: Reminder[]
  onChooseDocument?: (document: RelationshipCandidate) => void
  onChooseRecord?: (record: LifeRecord) => void
  onChooseReminder?: (reminder: Reminder) => void
}) {
  const hasRecords = records.length > 0
  const hasReminders = reminders.length > 0
  const hasDocuments = documents.length > 0

  if (!hasRecords && !hasReminders && !hasDocuments) {
    return <p className="linked-items-state linked-picker-empty">{emptyText}</p>
  }

  return (
    <div className="linked-picker-candidate-list">
      {records.map((record) => {
        const definition = getRecordTypeDefinition(record.record_type)
        const Icon = definition.icon
        return (
          <button type="button" className="linked-picker-candidate" key={record.id} onClick={() => onChooseRecord?.(record)}>
            <span className={`linked-item-icon tone-${definition.tone}`} aria-hidden="true"><Icon size={18} /></span>
            <span><strong>{record.title}</strong><small>{definition.label}{record.provider_or_brand ? ` - ${record.provider_or_brand}` : ''}</small></span>
            <ChevronRight size={17} aria-hidden="true" />
          </button>
        )
      })}
      {reminders.map((reminder) => (
        <button type="button" className="linked-picker-candidate" key={reminder.id} onClick={() => onChooseReminder?.(reminder)}>
          <span className="linked-item-icon tone-other" aria-hidden="true"><Bell size={18} /></span>
          <span><strong>{reminder.title}</strong><small>{getReminderTypeLabel(reminder.reminder_type)} - {formatDueDateLabel(reminder.due_date)}</small></span>
          <ChevronRight size={17} aria-hidden="true" />
        </button>
      ))}
      {documents.map((document) => (
        <button type="button" className="linked-picker-candidate" key={document.item_id} onClick={() => onChooseDocument?.(document)}>
          <span className="linked-item-icon tone-finance" aria-hidden="true"><FileText size={18} /></span>
          <span><strong>{document.title}</strong><small>{[document.subtitle || 'Document', formatDocumentStatus(document.status)].filter(Boolean).join(' - ')}</small></span>
          <ChevronRight size={17} aria-hidden="true" />
        </button>
      ))}
    </div>
  )
}

function filterRecords(records: LifeRecord[], search: string) {
  const query = search.trim().toLocaleLowerCase()
  if (!query) {
    return records
  }

  return records.filter((record) => [
    record.title,
    record.subtitle,
    record.provider_or_brand,
    record.owner_name,
    getRecordTypeDefinition(record.record_type).label,
  ].some((value) => value?.toLocaleLowerCase().includes(query)))
}

function filterReminders(reminders: Reminder[], search: string) {
  const query = search.trim().toLocaleLowerCase()
  if (!query) {
    return reminders
  }

  return reminders.filter((reminder) => [
    reminder.title,
    reminder.category,
    getReminderTypeLabel(reminder.reminder_type),
  ].some((value) => value.toLocaleLowerCase().includes(query)))
}

function getPickerSubcopy(step: AddStep, targetType: CandidateType | null) {
  if (step === 'type') {
    return 'Choose what you want to connect.'
  }
  if (step === 'select') {
    return targetType === 'record' ? 'Choose the item to connect.' : targetType === 'document' ? 'Choose the document to connect.' : 'Choose the responsibility to connect.'
  }
  return 'Review the contextual relationship, or customize it if needed.'
}

function getDefaultRecordRelationship(record: LifeRecord): RelationshipType {
  if (record.record_type === 'insurance') {
    return 'insures'
  }
  if (record.record_type === 'warranty') {
    return 'warranty_for'
  }
  return 'related'
}

function getLinkedItemMeta(item: LinkedItem) {
  const entity = item.linked_entity
  const relationship = item.label || getRelationshipPresentation(item.relationship_type)

  if (entity.entity_type === 'record') {
    const typeLabel = entity.record_type ? getRecordTypeDefinition(entity.record_type).singularLabel : productTerms.item
    const status = entity.status === 'archived' ? 'Archived' : null
    return [typeLabel, relationship, status].filter(Boolean).join(' - ')
  }

  if (entity.entity_type === 'document') {
    return [relationship, entity.subtitle || 'Document', formatDocumentStatus(entity.status)].filter(Boolean).join(' - ')
  }

  const typeLabel = getReminderTypeLabel(entity.reminder_type ?? 'generic')
  const dueLabel = entity.due_date ? formatDueDateLabel(entity.due_date) : entity.status
  return [typeLabel, dueLabel, relationship].filter(Boolean).join(' - ')
}

function getLinkedItemIcon(item: LinkedItem) {
  const entity = item.linked_entity
  if (entity.entity_type === 'record' && entity.record_type) {
    return getRecordTypeDefinition(entity.record_type).icon
  }

  if (entity.entity_type === 'document') {
    return FileText
  }

  return Bell
}

function getLinkedItemToneClass(item: LinkedItem) {
  const entity = item.linked_entity
  if (entity.entity_type === 'record' && entity.record_type) {
    return `tone-${getRecordTypeDefinition(entity.record_type).tone}`
  }
  if (entity.entity_type === 'document') {
    return 'tone-finance'
  }
  return 'tone-other'
}

function normalizeLinks(response: LinkedItemsResponse): LinkedItemsResponse {
  return {
    records: response.records ?? [],
    reminders: response.reminders ?? [],
    documents: response.documents ?? [],
  }
}

function getRemoveLinkBody(sourceTitle: string | undefined, item: LinkedItem | null) {
  if (!item) {
    return ''
  }
  const left = sourceTitle || 'This item'
  return `The relationship between ${left} and ${item.linked_entity.title} will be removed. Neither item will be deleted. You can add the relationship again later.`
}

function formatDocumentStatus(status: string | null) {
  if (!status) {
    return null
  }
  const labels: Record<string, string> = {
    pending_upload: 'Waiting for upload',
    uploaded: 'Scanning',
    scanning: 'Scanning',
    available: 'Security scanned',
    rejected: 'Rejected',
    scan_failed: 'Scan failed',
    deleting: 'Deleting',
    deleted: 'Deleted',
  }
  return labels[status] ?? status
}
