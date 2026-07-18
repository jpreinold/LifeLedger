import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Archive,
  Bell,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Eye,
  EyeOff,
  LockKeyhole,
  Pencil,
  Plus,
  RotateCcw,
  Trash2,
} from 'lucide-react'

import { recordsApi } from '../api/recordsApi'
import {
  formatRecordDate,
  formatRecordKeyDate,
  formatRecordTimestamp,
  getRecordProviderLine,
  getRecordStatusClass,
  getRecordStatusLabel,
} from '../lib/recordDisplay'
import {
  formatLongDate,
  formatReminderAttentionLabel,
  formatReminderStatusLabel,
  getReminderEffectiveDate,
  isActionableReminder,
  sortActionCenterReminders,
} from '../lib/reminderDisplay'
import { formatDynamicFieldValue, getVisibleDynamicFieldCount, hasDisplayValue, hasSensitiveDynamicFields, maskedValue } from '../lib/fieldRendering'
import { getProtectedFieldLabel, getRecordTypeDefinition } from '../lib/recordTypes'
import type { SuggestedResponsibilityDefinition } from '../lib/entityRegistry'
import { getCategoryPresentation, getResponsibilityPresentation, getSectionLabel, productTerms } from '../lib/terminology'
import type { DynamicFieldValue, DynamicRecordField, LifeRecord, ProtectedRecordPayload, ProtectedRecordStatus } from '../types/record'
import type { Reminder } from '../types/reminder'
import { AddFieldDrawer } from './AddFieldDrawer'
import { ConfirmDialog } from './ConfirmDialog'
import { DetailSection } from './DetailSection'
import { LinkedItemsPanel } from './LinkedItemsPanel'
import { RecordDocumentsPanel } from './RecordDocumentsPanel'
import { SheetDrawer } from './SheetDrawer'

export type RecordDetailTab = 'details' | 'responsibilities' | 'documents' | 'linkedItems'

interface RecordDetailDrawerProps {
  canGoBack?: boolean
  initialDocumentId?: string
  initialTab?: RecordDetailTab
  record: LifeRecord
  records: LifeRecord[]
  reminders: Reminder[]
  onArchive: (record: LifeRecord) => Promise<void>
  onAddResponsibility: (record: LifeRecord, suggestion?: SuggestedResponsibilityDefinition) => void
  onBack?: () => void
  onClose: () => void
  onEdit: (record: LifeRecord) => void
  onOpenLinkedDocument?: (recordId: string, documentId: string) => void
  onOpenLinkedRecord: (recordId: string) => void
  onOpenLinkedReminder: (reminderId: string) => void
  onProtectedStatusChange: (id: string, status: ProtectedRecordStatus) => void
  onRecordChange: (record: LifeRecord) => void
  onRequestDelete: (record: LifeRecord) => void
  onRestore: (record: LifeRecord) => Promise<void>
}

const drawerCloseMs = 220
const sensitiveRevealMs = 60_000

export function RecordDetailDrawer({
  canGoBack = false,
  initialDocumentId,
  initialTab = 'details',
  record,
  records,
  reminders,
  onArchive,
  onAddResponsibility,
  onBack,
  onClose,
  onEdit,
  onOpenLinkedDocument,
  onOpenLinkedRecord,
  onOpenLinkedReminder,
  onProtectedStatusChange,
  onRecordChange,
  onRequestDelete,
  onRestore,
}: RecordDetailDrawerProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<RecordDetailTab>(initialTab)
  const [isArchiving, setIsArchiving] = useState(false)
  const [isRevealingProtected, setIsRevealingProtected] = useState(false)
  const [isClearingProtected, setIsClearingProtected] = useState(false)
  const [protectedPayload, setProtectedPayload] = useState<ProtectedRecordPayload | null>(null)
  const [protectedError, setProtectedError] = useState<string | null>(null)
  const [documentsCount, setDocumentsCount] = useState<number | null>(null)
  const [isAddFieldOpen, setIsAddFieldOpen] = useState(false)
  const [editingField, setEditingField] = useState<DynamicRecordField | null>(null)
  const [revealedFields, setRevealedFields] = useState<Record<string, DynamicFieldValue>>({})
  const [revealingFieldId, setRevealingFieldId] = useState<string | null>(null)
  const [removingFieldId, setRemovingFieldId] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [pendingFieldRemoval, setPendingFieldRemoval] = useState<DynamicRecordField | null>(null)
  const [isProtectedClearConfirmOpen, setIsProtectedClearConfirmOpen] = useState(false)
  const closeTimerRef = useRef<number | null>(null)
  const detailBodyRef = useRef<HTMLDivElement | null>(null)
  const openFrameRef = useRef<number | null>(null)
  const revealTimerRef = useRef<number | null>(null)
  const dynamicRevealTimersRef = useRef<Record<string, number>>({})
  const definition = getRecordTypeDefinition(record.record_type)
  const Icon = definition.icon
  const providerLine = getRecordProviderLine(record)
  const keyDate = formatRecordKeyDate(record)
  const updatedLabel = formatRecordTimestamp(record.updated_at)
  const dynamicFieldCount = getVisibleDynamicFieldCount(record.dynamic_fields)
  const hasSensitiveFields = record.has_protected_data || hasSensitiveDynamicFields(record.dynamic_fields)
  const isArchived = record.status === 'archived'
  const categoryPresentation = getCategoryPresentation(record.record_type, record.category)
  const protectedFieldKeys = new Set<string>(definition.protectedFields)
  const suggestedDynamicFields = definition.dynamicFieldPresets.filter(
    (field) => !protectedFieldKeys.has(field.key) && !record.dynamic_fields.some((existing) => existing.key === field.key),
  )

  const recordReminders = reminders.filter((reminder) =>
    reminder.linked_records.some((linkedRecord) => linkedRecord.id === record.id),
  )
  const activeRecordReminders = recordReminders.filter(isActionableReminder).sort(sortActionCenterReminders)
  const nextRecordReminder = activeRecordReminders[0] ?? null
  const overdueRecordReminderCount = activeRecordReminders.filter((reminder) => reminder.status === 'Overdue').length
  const recentReminderEvents = getRecentRecordReminderEvents(recordReminders)
  const resetDetailScroll = useCallback(() => {
    detailBodyRef.current?.scrollTo({ top: 0 })
  }, [])

  const clearDynamicReveals = useCallback(() => {
    setRevealedFields({})
    setRevealingFieldId(null)
    for (const timerId of Object.values(dynamicRevealTimersRef.current)) {
      window.clearTimeout(timerId)
    }
    dynamicRevealTimersRef.current = {}
  }, [])

  const clearProtectedState = useCallback(() => {
    setProtectedPayload(null)
    setProtectedError(null)
    setIsRevealingProtected(false)
    if (revealTimerRef.current !== null) {
      window.clearTimeout(revealTimerRef.current)
      revealTimerRef.current = null
    }
  }, [])

  const clearSensitiveState = useCallback(() => {
    clearProtectedState()
    clearDynamicReveals()
    setFieldError(null)
  }, [clearDynamicReveals, clearProtectedState])

  useEffect(() => {
    clearSensitiveState()
    setIsAddFieldOpen(false)
    setEditingField(null)
    setActiveTab(initialTab)
    setIsDrawerOpen(false)
    resetDetailScroll()
    openFrameRef.current = window.requestAnimationFrame(() => {
      resetDetailScroll()
      setIsDrawerOpen(true)
      openFrameRef.current = null
    })

    return () => {
      if (openFrameRef.current !== null) {
        window.cancelAnimationFrame(openFrameRef.current)
      }
    }
  }, [clearSensitiveState, initialTab, record.id, resetDetailScroll])

  useEffect(() => {
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current)
      }
      if (revealTimerRef.current !== null) {
        window.clearTimeout(revealTimerRef.current)
      }
      for (const timerId of Object.values(dynamicRevealTimersRef.current)) {
        window.clearTimeout(timerId)
      }
    }
  }, [])

  useEffect(() => {
    let isCancelled = false
    setDocumentsCount(null)

    async function loadDocumentCount() {
      try {
        const attachments = await recordsApi.listAttachments(record.id)
        if (!isCancelled) {
          setDocumentsCount(attachments.length)
        }
      } catch {
        if (!isCancelled) {
          setDocumentsCount(null)
        }
      }
    }

    void loadDocumentCount()

    return () => {
      isCancelled = true
    }
  }, [record.id])

  useEffect(() => {
    if (protectedPayload === null) {
      return undefined
    }

    revealTimerRef.current = window.setTimeout(clearProtectedState, sensitiveRevealMs)
    return () => {
      if (revealTimerRef.current !== null) {
        window.clearTimeout(revealTimerRef.current)
        revealTimerRef.current = null
      }
    }
  }, [clearProtectedState, protectedPayload])

  useEffect(() => {
    function handleVisibilityChange() {
      if (document.visibilityState === 'hidden') {
        clearSensitiveState()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [clearSensitiveState])

  const requestClose = useCallback(() => {
    clearSensitiveState()
    setIsAddFieldOpen(false)
    setEditingField(null)
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onClose()
    }, drawerCloseMs)
  }, [clearSensitiveState, onClose])

  function selectTab(tab: RecordDetailTab) {
    setActiveTab(tab)
    window.requestAnimationFrame(resetDetailScroll)
  }

  function handleEdit() {
    clearSensitiveState()
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onEdit(record)
    }, drawerCloseMs)
  }

  async function handleRevealProtected() {
    setIsRevealingProtected(true)
    setProtectedError(null)
    try {
      const revealed = await recordsApi.revealProtected(record.id)
      setProtectedPayload(revealed)
    } catch (requestError) {
      setProtectedPayload(null)
      setProtectedError(requestError instanceof Error ? requestError.message : 'Unable to reveal protected details.')
    } finally {
      setIsRevealingProtected(false)
    }
  }

  async function handleClearProtected() {
    setIsClearingProtected(true)
    setProtectedError(null)
    try {
      const nextStatus = await recordsApi.clearProtected(record.id)
      clearProtectedState()
      onProtectedStatusChange(record.id, nextStatus)
      setIsProtectedClearConfirmOpen(false)
    } catch (requestError) {
      setProtectedError(requestError instanceof Error ? requestError.message : 'Unable to clear protected details.')
    } finally {
      setIsClearingProtected(false)
    }
  }

  function hideDynamicField(fieldId: string) {
    setRevealedFields((current) => {
      const next = { ...current }
      delete next[fieldId]
      return next
    })
    const timerId = dynamicRevealTimersRef.current[fieldId]
    if (timerId !== undefined) {
      window.clearTimeout(timerId)
      delete dynamicRevealTimersRef.current[fieldId]
    }
  }

  async function handleRevealField(field: DynamicRecordField) {
    setRevealingFieldId(field.field_id)
    setFieldError(null)
    try {
      const revealed = await recordsApi.revealField(record.id, field.field_id)
      setRevealedFields((current) => ({ ...current, [field.field_id]: revealed.value }))
      const existingTimer = dynamicRevealTimersRef.current[field.field_id]
      if (existingTimer !== undefined) {
        window.clearTimeout(existingTimer)
      }
      dynamicRevealTimersRef.current[field.field_id] = window.setTimeout(() => hideDynamicField(field.field_id), sensitiveRevealMs)
    } catch (requestError) {
      setFieldError(requestError instanceof Error ? requestError.message : 'Unable to reveal this detail.')
    } finally {
      setRevealingFieldId(null)
    }
  }

  async function handleRemoveField(field: DynamicRecordField) {
    setRemovingFieldId(field.field_id)
    setFieldError(null)
    try {
      const updated = await recordsApi.deleteField(record.id, field.field_id)
      hideDynamicField(field.field_id)
      setPendingFieldRemoval(null)
      onRecordChange(updated)
    } catch (requestError) {
      setFieldError(requestError instanceof Error ? requestError.message : 'Unable to remove this detail.')
    } finally {
      setRemovingFieldId(null)
    }
  }

  async function handleArchiveToggle() {
    setIsArchiving(true)
    try {
      if (isArchived) {
        await onRestore(record)
      } else {
        await onArchive(record)
      }
    } finally {
      setIsArchiving(false)
    }
  }

  return (
    <>
      <SheetDrawer
        bodyClassName="detail-body"
        bodyRef={detailBodyRef}
        className="detail-dialog record-detail-dialog"
        closeLabel="Close item details"
        footer={activeTab === 'details' ? (
          <section className="detail-actions" aria-label="Item actions">
            <button type="button" className="primary-button" onClick={handleEdit}>
              <Pencil size={17} aria-hidden="true" />
              Edit
            </button>
            <button type="button" className="secondary-button" onClick={() => void handleArchiveToggle()} disabled={isArchiving}>
              {isArchived ? <RotateCcw size={17} aria-hidden="true" /> : <Archive size={17} aria-hidden="true" />}
              {isArchiving ? 'Saving...' : isArchived ? 'Restore' : 'Archive'}
            </button>
            <button type="button" className="text-danger-button detail-delete-button" onClick={() => onRequestDelete(record)}>
              <Trash2 size={16} aria-hidden="true" />
              Delete
            </button>
          </section>
        ) : null}
        isOpen={isDrawerOpen}
        labelledBy="record-detail-heading"
        onBack={canGoBack && onBack ? onBack : undefined}
        onClose={requestClose}
        backLabel="Back to previous item"
        subtitle={definition.singularLabel}
        title="Item details"
      >
          <section className={`detail-hero tone-${definition.tone}`} aria-labelledby="record-detail-title">
            <div className={`category-icon category-icon-large tone-${definition.tone}`} aria-hidden="true">
              <Icon size={30} />
            </div>
            <div className="detail-hero-copy">
              <div className="card-chip-row">
                <span className="type-chip">{definition.singularLabel}</span>
                <span className={`status-chip ${getRecordStatusClass(record)}`}>{getRecordStatusLabel(record)}</span>
              </div>
              <h3 id="record-detail-title">{record.title}</h3>
              {updatedLabel ? <p className="detail-updated-label">Updated {updatedLabel}</p> : null}
              {record.subtitle ? <p>{record.subtitle}</p> : null}
              {keyDate ? (
                <p className="detail-smart-label">
                  <Icon size={15} aria-hidden="true" />
                  {keyDate}
                </p>
              ) : null}
              <div className="detail-hero-meta" aria-label="Item summary">
                {documentsCount !== null ? <span className="detail-hero-pill">{documentsCount} document{documentsCount === 1 ? '' : 's'}</span> : null}
                <span className="detail-hero-pill">{dynamicFieldCount} additional detail{dynamicFieldCount === 1 ? '' : 's'}</span>
                {hasSensitiveFields ? <span className="detail-hero-pill">Protected details saved</span> : null}
              </div>
            </div>
          </section>

          <div className="record-detail-tabs record-detail-tabs-four" role="tablist" aria-label="Item detail sections">
            <button
              type="button"
              className={activeTab === 'details' ? 'record-detail-tab active' : 'record-detail-tab'}
              id="record-details-tab"
              role="tab"
              aria-selected={activeTab === 'details'}
              aria-controls="record-details-panel"
              onClick={() => selectTab('details')}
            >
              {getSectionLabel('overview')}
            </button>
            {definition.supportedSections.includes('responsibilities') ? (
              <button
                type="button"
                className={activeTab === 'responsibilities' ? 'record-detail-tab active' : 'record-detail-tab'}
                id="record-responsibilities-tab"
                role="tab"
                aria-selected={activeTab === 'responsibilities'}
                aria-controls="record-responsibilities-panel"
                onClick={() => selectTab('responsibilities')}
              >
                {getSectionLabel('responsibilities')}
              </button>
            ) : null}
            <button
              type="button"
              className={activeTab === 'documents' ? 'record-detail-tab active' : 'record-detail-tab'}
              id="record-documents-tab"
              role="tab"
              aria-selected={activeTab === 'documents'}
              aria-controls="record-documents-panel"
              onClick={() => selectTab('documents')}
            >
              {getSectionLabel('documents')}
            </button>
            <button
              type="button"
              className={activeTab === 'linkedItems' ? 'record-detail-tab active' : 'record-detail-tab'}
              id="record-linked-items-tab"
              role="tab"
              aria-selected={activeTab === 'linkedItems'}
              aria-controls="record-linked-items-panel"
              onClick={() => selectTab('linkedItems')}
            >
              {getSectionLabel('relatedItems')}
            </button>
          </div>

          <div
            className="record-tab-panel"
            hidden={activeTab !== 'details'}
            id="record-details-panel"
            role="tabpanel"
            aria-labelledby="record-details-tab"
          >
            <DetailSection
              title="Important details"
              rows={[
                { label: productTerms.itemType, value: definition.singularLabel },
                { label: 'Category', value: categoryPresentation },
                { label: definition.labels.owner_name ?? productTerms.owner, value: record.owner_name },
                { label: definition.labels.provider_or_brand ?? productTerms.provider, value: record.provider_or_brand },
                { label: 'Summary', value: providerLine },
                { label: definition.labels.location_hint ?? 'Location', value: record.location_hint },
              ]}
            />

            <DetailSection
              title="Important dates"
              className="detail-schedule-section"
              rows={[
                { label: 'Start date', value: formatRecordDate(record.start_date) },
                { label: 'Issue date', value: formatRecordDate(record.issue_date) },
                { label: 'Expiration date', value: formatRecordDate(record.expiration_date) },
                { label: 'Purchase date', value: formatRecordDate(record.purchase_date) },
                { label: 'Renewal date', value: formatRecordDate(record.renewal_date) },
              ]}
            />

            <DynamicFieldsSection
              error={fieldError}
              fields={record.dynamic_fields}
              revealedFields={revealedFields}
              revealingFieldId={revealingFieldId}
              removingFieldId={removingFieldId}
              suggestedCount={suggestedDynamicFields.length}
              onAddField={() => setIsAddFieldOpen(true)}
              onEditField={setEditingField}
              onHideField={hideDynamicField}
              onRemoveField={setPendingFieldRemoval}
              onRevealField={(field) => void handleRevealField(field)}
            />

            <ProtectedDetailsSection
              error={protectedError}
              isClearing={isClearingProtected}
              isRevealing={isRevealingProtected}
              payload={protectedPayload}
              record={record}
              onClear={() => setIsProtectedClearConfirmOpen(true)}
              onHide={clearProtectedState}
              onReveal={() => void handleRevealProtected()}
            />

            {record.tags.length > 0 ? (
              <section className="detail-section" aria-label="Tags">
                <h3>Tags</h3>
                <div className="record-tag-list">
                  {record.tags.map((tag) => (
                    <span className="record-tag" key={tag}>{tag}</span>
                  ))}
                </div>
              </section>
            ) : null}

            {record.notes ? (
              <section className="detail-section" aria-label="Notes">
                <h3>Notes</h3>
                <p className="detail-note">{record.notes}</p>
              </section>
            ) : null}

            <DetailSection
              title="Item information"
              rows={[
                { label: 'Created', value: formatRecordTimestamp(record.created_at) },
                { label: 'Updated', value: formatRecordTimestamp(record.updated_at) },
              ]}
            />
          </div>

          {definition.supportedSections.includes('responsibilities') ? (
            <div
              className="record-tab-panel"
              hidden={activeTab !== 'responsibilities'}
              id="record-responsibilities-panel"
              role="tabpanel"
              aria-labelledby="record-responsibilities-tab"
            >
              <RecordReminderActivitySection
                activeReminders={activeRecordReminders}
                overdueCount={overdueRecordReminderCount}
                recentEvents={recentReminderEvents}
                nextReminder={nextRecordReminder}
                suggestions={definition.suggestedResponsibilities}
                onAddResponsibility={(suggestion) => onAddResponsibility(record, suggestion)}
                onOpenReminder={onOpenLinkedReminder}
              />
            </div>
          ) : null}

          <div
            className="record-tab-panel"
            hidden={activeTab !== 'documents'}
            id="record-documents-panel"
            role="tabpanel"
            aria-labelledby="record-documents-tab"
          >
            <RecordDocumentsPanel
              emptyStateCopy={definition.emptyStateCopy.documents}
              initialAttachmentId={initialDocumentId}
              isActive={isDrawerOpen && activeTab === 'documents'}
              recordId={record.id}
            />
          </div>

          <div
            className="record-tab-panel"
            hidden={activeTab !== 'linkedItems'}
            id="record-linked-items-panel"
            role="tabpanel"
            aria-labelledby="record-linked-items-tab"
          >
            <LinkedItemsPanel
              documentsCount={documentsCount}
              records={records}
              reminders={reminders}
              showAdd
              tabLayout
              sourceId={record.id}
              sourceTitle={record.title}
              sourceType="record"
              title={productTerms.relatedItems}
              onOpenDocument={onOpenLinkedDocument}
              onOpenRecord={onOpenLinkedRecord}
              onOpenReminder={onOpenLinkedReminder}
            />
          </div>
      </SheetDrawer>


      <ConfirmDialog
        body="The encrypted protected details will be permanently removed from this item. The item, documents, reminders, and related items will remain. This cannot be undone."
        confirmLabel="Clear protected details"
        isBusy={isClearingProtected}
        isOpen={isProtectedClearConfirmOpen}
        title="Clear protected details?"
        onCancel={() => setIsProtectedClearConfirmOpen(false)}
        onConfirm={() => void handleClearProtected()}
      />
      <ConfirmDialog
        body={pendingFieldRemoval ? `${pendingFieldRemoval.label} will be permanently removed from this item. Related items, reminders, and documents will remain. This cannot be undone.` : ''}
        confirmLabel="Remove detail"
        isBusy={removingFieldId !== null}
        isOpen={pendingFieldRemoval !== null}
        title="Remove detail?"
        onCancel={() => setPendingFieldRemoval(null)}
        onConfirm={() => pendingFieldRemoval && void handleRemoveField(pendingFieldRemoval)}
      />
      <AddFieldDrawer
        field={editingField}
        isOpen={isAddFieldOpen || editingField !== null}
        record={record}
        suggestedFields={suggestedDynamicFields}
        onClose={() => {
          setIsAddFieldOpen(false)
          setEditingField(null)
        }}
        onSaved={onRecordChange}
      />
    </>
  )
}

interface RecordReminderEventSummary {
  eventId: string
  label: string
  occurredAt: string
  reminderId: string
  reminderTitle: string
  summary: string
}

function RecordReminderActivitySection({
  activeReminders,
  nextReminder,
  onAddResponsibility,
  onOpenReminder,
  overdueCount,
  recentEvents,
  suggestions,
}: {
  activeReminders: Reminder[]
  nextReminder: Reminder | null
  overdueCount: number
  recentEvents: RecordReminderEventSummary[]
  suggestions: SuggestedResponsibilityDefinition[]
  onAddResponsibility: (suggestion?: SuggestedResponsibilityDefinition) => void
  onOpenReminder: (reminderId: string) => void
}) {
  const presentation = getResponsibilityPresentation('item')
  return (
    <section className="detail-section record-reminder-section" aria-labelledby="record-responsibilities-heading">
      <div className="record-reminder-header">
        <div>
          <h3 id="record-responsibilities-heading">{presentation.plural}</h3>
          <p>{activeReminders.length === 0 ? 'Keep renewals, service dates, payments, and other tasks connected to this item.' : `${activeReminders.length} upcoming responsibilit${activeReminders.length === 1 ? 'y' : 'ies'}.`}</p>
        </div>
        <button type="button" className="small-outline-button" onClick={() => onAddResponsibility()}>
          <Bell size={14} aria-hidden="true" />
          {presentation.add}
        </button>
      </div>

      <div className="record-reminder-stats" aria-label="Responsibility summary">
        <div>
          <span>Next date</span>
          <strong>{nextReminder ? formatLongDate(getReminderEffectiveDate(nextReminder)) : 'None'}</strong>
        </div>
        <div>
          <span>Active</span>
          <strong>{activeReminders.length}</strong>
        </div>
        <div>
          <span>Overdue</span>
          <strong>{overdueCount}</strong>
        </div>
      </div>

      {activeReminders.length > 0 ? (
        <div className="record-reminder-list">
          {activeReminders.slice(0, 3).map((reminder) => (
            <button type="button" className="record-reminder-row" key={reminder.id} onClick={() => onOpenReminder(reminder.id)}>
              <span className="record-reminder-row-icon" aria-hidden="true">
                <CalendarDays size={16} />
              </span>
              <span className="record-reminder-row-copy">
                <strong>{reminder.title}</strong>
                <span>{formatReminderStatusLabel(reminder)} {'\u2022'} {formatReminderAttentionLabel(reminder, { includeDate: false })}</span>
              </span>
              <span className="record-reminder-row-action">
                {isRenewableReminder(reminder) ? 'Renew' : 'Open'}
                <ChevronRight size={15} aria-hidden="true" />
              </span>
            </button>
          ))}
        </div>
      ) : (
        <p className="linked-items-state">No upcoming responsibilities yet.</p>
      )}

      {suggestions.length > 0 ? (
        <div className="responsibility-suggestions" aria-label="Suggested responsibilities">
          <h4>Suggested for this item</h4>
          <div>
            {suggestions.map((suggestion) => (
              <button type="button" className="small-outline-button" key={suggestion.label} onClick={() => onAddResponsibility(suggestion)}>
                <Plus size={14} aria-hidden="true" />
                {suggestion.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="record-reminder-history">
        <h4>Recent activity</h4>
        {recentEvents.length === 0 ? <p className="linked-items-state">Completed and renewed responsibilities will appear here.</p> : null}
        {recentEvents.length > 0 ? (
          <ol>
            {recentEvents.map((event) => (
              <li key={event.eventId}>
                <CheckCircle2 size={15} aria-hidden="true" />
                <span>
                  <strong>{event.label}</strong>
                  <small>{event.reminderTitle} {'\u2022'} {event.summary}</small>
                </span>
                <time dateTime={event.occurredAt}>{formatReminderEventDate(event.occurredAt)}</time>
              </li>
            ))}
          </ol>
        ) : null}
      </div>
    </section>
  )
}

function getRecentRecordReminderEvents(reminders: Reminder[]): RecordReminderEventSummary[] {
  const visibleTypes = new Set(['completed', 'renewed', 'date_changed', 'snoozed', 'snooze_cleared'])

  return reminders
    .flatMap((reminder) => reminder.lifecycle_events
      .filter((event) => visibleTypes.has(event.event_type))
      .map((event) => ({
        eventId: event.event_id,
        label: formatReminderEventType(event.event_type),
        occurredAt: event.occurred_at,
        reminderId: reminder.id,
        reminderTitle: reminder.title,
        summary: event.summary,
      })))
    .sort((left, right) => new Date(right.occurredAt).getTime() - new Date(left.occurredAt).getTime())
    .slice(0, 4)
}

function formatReminderEventType(type: Reminder['lifecycle_events'][number]['event_type']) {
  const labels: Record<Reminder['lifecycle_events'][number]['event_type'], string> = {
    created: 'Created',
    edited: 'Edited',
    date_changed: 'Date changed',
    snoozed: 'Snoozed',
    snooze_cleared: 'Snooze cleared',
    completed: 'Completed',
    renewed: 'Renewed',
    archived: 'Archived',
    restored: 'Restored',
  }

  return labels[type]
}

function formatReminderEventDate(value: string) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) {
    return 'Date unknown'
  }

  return timestamp.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

function isRenewableReminder(reminder: Reminder) {
  return reminder.reminder_type === 'renewal' || reminder.reminder_type === 'maintenance' || reminder.repeat !== 'None'
}
function DynamicFieldsSection({
  error,
  fields,
  onAddField,
  onEditField,
  onHideField,
  onRemoveField,
  onRevealField,
  revealedFields,
  revealingFieldId,
  removingFieldId,
  suggestedCount,
}: {
  error: string | null
  fields: DynamicRecordField[]
  onAddField: () => void
  onEditField: (field: DynamicRecordField) => void
  onHideField: (fieldId: string) => void
  onRemoveField: (field: DynamicRecordField) => void
  onRevealField: (field: DynamicRecordField) => void
  revealedFields: Record<string, DynamicFieldValue>
  revealingFieldId: string | null
  removingFieldId: string | null
  suggestedCount: number
}) {
  const visibleFields = [...fields]
    .sort((left, right) => left.display_order - right.display_order || left.label.localeCompare(right.label))
    .filter((field) => field.is_sensitive ? field.has_value : hasDisplayValue(field.value))

  return (
    <section className="detail-section dynamic-fields-section" aria-label="Additional details">
      <div className="dynamic-fields-heading">
        <h3>Additional details</h3>
        {suggestedCount > 0 ? <span>{suggestedCount} suggested</span> : null}
      </div>

      {visibleFields.length > 0 ? (
        <dl className="detail-list dynamic-field-list">
          {visibleFields.map((field) => {
            const isRevealed = field.field_id in revealedFields
            const visibleValue = field.is_sensitive
              ? isRevealed
                ? revealedFields[field.field_id]
                : maskedValue
              : field.value
            const displayValue = field.is_sensitive && !isRevealed
              ? maskedValue
              : formatDynamicFieldValue(field.field_type, visibleValue)

            return (
              <div className="detail-row dynamic-field-row" key={field.field_id}>
                <dt>{field.label}</dt>
                <dd>
                  <DynamicFieldDisplay field={field} value={displayValue ?? ''} isMasked={field.is_sensitive && !isRevealed} />
                  <span className="dynamic-field-actions">
                    {field.is_sensitive ? (
                      isRevealed ? (
                        <button type="button" className="small-outline-button" onClick={() => onHideField(field.field_id)} aria-label={`Hide ${field.label}`}>
                          <EyeOff size={14} aria-hidden="true" />
                          Hide
                        </button>
                      ) : (
                        <button type="button" className="small-outline-button" disabled={revealingFieldId === field.field_id} onClick={() => onRevealField(field)} aria-label={`Reveal ${field.label}`}>
                          <Eye size={14} aria-hidden="true" />
                          {revealingFieldId === field.field_id ? 'Revealing...' : 'Reveal'}
                        </button>
                      )
                    ) : null}
                    <button type="button" className="icon-button ghost-icon-button dynamic-field-edit" onClick={() => onEditField(field)} aria-label={`Edit ${field.label}`}>
                      <Pencil size={15} aria-hidden="true" />
                    </button>
                    <button type="button" className="icon-button ghost-icon-button dynamic-field-remove" disabled={removingFieldId === field.field_id} onClick={() => onRemoveField(field)} aria-label={`Remove ${field.label}`}>
                      <Trash2 size={15} aria-hidden="true" />
                    </button>
                  </span>
                </dd>
              </div>
            )
          })}
        </dl>
      ) : null}

      {error ? <p className="field-error protected-detail-error">{error}</p> : null}

      <button type="button" className="secondary-button dynamic-add-field-button" onClick={onAddField}>
        <Plus size={16} aria-hidden="true" />
        {productTerms.addDetail}
      </button>
    </section>
  )
}

function DynamicFieldDisplay({ field, isMasked, value }: { field: DynamicRecordField; isMasked: boolean; value: string }) {
  if (isMasked || !value) {
    return <span className={isMasked ? 'masked-field-value' : ''}>{value}</span>
  }

  if (field.field_type === 'url') {
    const href = /^https?:\/\//i.test(value) ? value : `https://${value}`
    return <a href={href} target="_blank" rel="noreferrer">{value}</a>
  }

  if (field.field_type === 'email') {
    return <a href={`mailto:${value}`}>{value}</a>
  }

  if (field.field_type === 'phone') {
    return <a href={`tel:${value.replace(/\s+/g, '')}`}>{value}</a>
  }

  return <span>{value}</span>
}

function ProtectedDetailsSection({
  error,
  isClearing,
  isRevealing,
  onClear,
  onHide,
  onReveal,
  payload,
  record,
}: {
  error: string | null
  isClearing: boolean
  isRevealing: boolean
  onClear: () => void
  onHide: () => void
  onReveal: () => void
  payload: ProtectedRecordPayload | null
  record: LifeRecord
}) {
  const hasProtectedData = record.has_protected_data && record.protected_field_names.length > 0

  if (!hasProtectedData) {
    return null
  }

  const isRevealed = payload !== null
  const rows = record.protected_field_names.map((field) => ({
    field,
    label: getProtectedFieldLabel(field),
    value: isRevealed ? payload?.[field] ?? null : null,
  }))

  return (
    <section className="detail-section protected-details-section" aria-label="Protected details">
      <div className="protected-details-heading">
        <h3>Protected details</h3>
        <LockKeyhole size={18} aria-hidden="true" />
      </div>

      <p className="detail-note">Encrypted before storage, excluded from search, and hidden until you choose to reveal it.</p>
      <dl className="detail-list protected-detail-list">
        {rows.map((row) => (
          <div className="detail-row" key={row.field}>
            <dt>{row.label}</dt>
            <dd className={isRevealed && row.value ? '' : 'masked-field-value'}>{isRevealed && row.value ? row.value : maskedValue}</dd>
          </div>
        ))}
      </dl>

      {error ? <p className="field-error protected-detail-error">{error}</p> : null}

      <div className="protected-detail-actions">
        {isRevealed ? (
          <button type="button" className="secondary-button" onClick={onHide}>
            <EyeOff size={16} aria-hidden="true" />
            Hide
          </button>
        ) : (
          <button type="button" className="secondary-button" disabled={isRevealing} onClick={onReveal}>
            <Eye size={16} aria-hidden="true" />
            {isRevealing ? 'Revealing...' : 'Reveal'}
          </button>
        )}
        <button type="button" className="text-danger-button" disabled={isClearing} onClick={onClear}>
          <Trash2 size={15} aria-hidden="true" />
          {isClearing ? 'Clearing...' : 'Clear'}
        </button>
      </div>
    </section>
  )
}

