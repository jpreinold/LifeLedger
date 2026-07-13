import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArrowLeft,
  Bell,
  ChevronRight,
  FileText,
  Link2,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react'

import { linkedItemsApi } from '../api/linkedItemsApi'
import { formatDueDateLabel, getReminderTypeLabel } from '../lib/reminderDisplay'
import { getRecordTypeDefinition } from '../lib/recordTypes'
import type { LinkedItem, LinkedItemsResponse, RelationshipType } from '../types/linkedItem'
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
  sourceType: 'record' | 'reminder'
  title?: string
  tabLayout?: boolean
  onOpenRecord?: (recordId: string) => void
  onOpenReminder?: (reminderId: string) => void
}

type AddStep = 'type' | 'select' | 'relationship'
export type CandidateType = 'record' | 'reminder'

export interface LinkDraft {
  targetType: CandidateType
  targetId: string
  relationshipType: RelationshipType
  label: string | null
}

const emptyLinks: LinkedItemsResponse = { records: [], reminders: [] }

const relationshipOptions: Array<{ label: string; value: RelationshipType }> = [
  { label: 'Related to', value: 'related' },
  { label: 'Insurance for', value: 'insures' },
  { label: 'Warranty for', value: 'warranty_for' },
  { label: 'Maintenance for', value: 'maintains' },
  { label: 'Reminder for', value: 'renews' },
  { label: 'Covers', value: 'covers' },
  { label: 'Custom', value: 'custom' },
]

const relationshipLabels: Record<RelationshipType, string> = {
  related: 'Related to',
  belongs_to: 'Belongs to',
  covers: 'Covers',
  renews: 'Reminder for',
  maintains: 'Maintenance for',
  insures: 'Insurance for',
  warranty_for: 'Warranty for',
  document_for: 'Document for',
  appointment_for: 'Appointment for',
  custom: 'Custom',
}

export function LinkedItemsPanel({
  documentsCount = null,
  records,
  reminders,
  showAdd = false,
  sourceId,
  sourceType,
  title = 'Linked items',
  tabLayout = false,
  onOpenRecord,
  onOpenReminder,
}: LinkedItemsPanelProps) {
  const [links, setLinks] = useState<LinkedItemsResponse>(emptyLinks)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isPickerOpen, setIsPickerOpen] = useState(false)
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
          setLinks(response)
        }
      } catch (requestError) {
        if (!isCancelled) {
          setLinks(emptyLinks)
          setError(requestError instanceof Error ? requestError.message : 'Unable to load linked items.')
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
    setLinks(response)
  }

  async function handleCreateLink(input: { targetType: CandidateType; targetId: string; relationshipType: RelationshipType; label: string | null }) {
    if (sourceType !== 'record') {
      return
    }

    setError(null)
    await linkedItemsApi.createRecordLink(sourceId, {
      target_type: input.targetType,
      target_id: input.targetId,
      relationship_type: input.relationshipType,
      label: input.label,
    })
    await reloadLinks()
    setIsPickerOpen(false)
  }

  async function confirmRemoveLink() {
    if (!pendingRemove) {
      return
    }

    setIsRemoving(true)
    setError(null)
    try {
      if (sourceType === 'record') {
        await linkedItemsApi.deleteRecordLink(sourceId, pendingRemove.link_id)
      } else {
        await linkedItemsApi.deleteReminderLink(sourceId, pendingRemove.link_id)
      }
      await reloadLinks()
      setPendingRemove(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to remove link.')
    } finally {
      setIsRemoving(false)
    }
  }

  const linkedRecordIds = useMemo(() => new Set(links.records.map((item) => item.linked_entity.id)), [links.records])
  const linkedReminderIds = useMemo(() => new Set(links.reminders.map((item) => item.linked_entity.id)), [links.reminders])
  const hasLinks = links.records.length > 0 || links.reminders.length > 0
  const canAdd = showAdd && sourceType === 'record'
  const usesTabLayout = tabLayout && sourceType === 'record'
  const overview = sourceType === 'record' ? (
    <div className="linked-overview" aria-label="Linked items overview">
      <span><strong>{links.records.length}</strong> Linked records</span>
      <span><strong>{links.reminders.length}</strong> Linked reminders</span>
      {documentsCount !== null ? <span><strong>{documentsCount}</strong> Documents</span> : null}
    </div>
  ) : null

  return (
    <section className={`detail-section linked-items-section ${usesTabLayout ? 'linked-items-tab-section' : ''}`.trim()} aria-label={title}>
      {!usesTabLayout ? (
        <div className="linked-items-header">
          <div>
            <h3>{title}</h3>
            <p>{sourceType === 'record' ? 'Records and reminders connected to this record.' : 'Records connected to this reminder.'}</p>
          </div>
          {canAdd ? (
            <button type="button" className="small-outline-button linked-items-add-button" onClick={() => setIsPickerOpen(true)}>
              <Plus size={14} aria-hidden="true" />
              Link item
            </button>
          ) : null}
        </div>
      ) : null}

      {!usesTabLayout ? overview : null}
      {isLoading ? <p className="linked-items-state">Loading linked items...</p> : null}
      {error ? <p className="field-error linked-items-error" role="alert">{error}</p> : null}

      {!isLoading && !error && sourceType === 'record' && !hasLinks && !usesTabLayout ? (
        <div className="linked-items-empty-state">
          <Link2 size={24} aria-hidden="true" />
          <p>Nothing is linked to this record yet.</p>
          {canAdd ? (
            <button type="button" className="secondary-button" onClick={() => setIsPickerOpen(true)}>
              <Plus size={16} aria-hidden="true" />
              Link an item
            </button>
          ) : null}
        </div>
      ) : null}

      {!isLoading && !error && sourceType === 'reminder' && links.records.length === 0 ? (
        <p className="linked-items-state">This reminder is not linked to a record.</p>
      ) : null}

      {!isLoading && !error && sourceType === 'record' ? (
        <>
          <LinkedItemsGroup
            action={canAdd && usesTabLayout ? <AddGroupButton onClick={() => setIsPickerOpen(true)} /> : undefined}
            emptyText="No linked records."
            items={links.records}
            title="Linked records"
            onOpen={onOpenRecord}
            onRemove={setPendingRemove}
          />
          <LinkedItemsGroup
            action={canAdd && usesTabLayout ? <AddGroupButton onClick={() => setIsPickerOpen(true)} /> : undefined}
            emptyText="No linked reminders."
            items={links.reminders}
            title="Linked reminders"
            onOpen={onOpenReminder}
            onRemove={setPendingRemove}
          />
          {usesTabLayout ? overview : null}
        </>
      ) : null}

      {!isLoading && !error && sourceType === 'reminder' && links.records.length > 0 ? (
        <LinkedItemsGroup
          emptyText="This reminder is not linked to a record."
          items={links.records}
          title="Linked to"
          onOpen={onOpenRecord}
          onRemove={setPendingRemove}
        />
      ) : null}

      {sourceType === 'record' ? (
        <AddLinkedItemDrawer
          currentRecordId={sourceId}
          isOpen={isPickerOpen}
          linkedRecordIds={linkedRecordIds}
          linkedReminderIds={linkedReminderIds}
          records={records}
          reminders={reminders}
          onClose={() => setIsPickerOpen(false)}
          onCreate={handleCreateLink}
        />
      ) : null}

      <ConfirmDialog
        body="Remove this link? The record or reminder itself will not be deleted."
        busyLabel="Removing"
        confirmLabel="Remove link"
        isBusy={isRemoving}
        isOpen={pendingRemove !== null}
        title="Remove link"
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
  onOpen,
  onRemove,
  title,
}: {
  action?: ReactNode
  emptyText: string
  items: LinkedItem[]
  title: string
  onOpen?: (id: string) => void
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
            <LinkedItemCard item={item} key={item.link_id} onOpen={onOpen} onRemove={() => onRemove(item)} />
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

function LinkedItemCard({ item, onOpen, onRemove }: { item: LinkedItem; onOpen?: (id: string) => void; onRemove: () => void }) {
  const entity = item.linked_entity
  const isRecord = entity.entity_type === 'record'
  const Icon = getLinkedItemIcon(item)
  const meta = getLinkedItemMeta(item)
  const canOpen = Boolean(onOpen)

  return (
    <article className="linked-item-card">
      <button
        type="button"
        className="linked-item-main"
        disabled={!canOpen}
        onClick={() => onOpen?.(entity.id)}
        aria-label={`Open ${entity.title}`}
      >
        <span className={`linked-item-icon ${isRecord ? getRecordToneClass(entity.record_type) : 'tone-other'}`} aria-hidden="true">
          <Icon size={19} />
        </span>
        <span className="linked-item-copy">
          <strong>{entity.title}</strong>
          <span>{meta}</span>
        </span>
        {canOpen ? <ChevronRight size={17} aria-hidden="true" className="linked-item-chevron" /> : null}
      </button>
      <button type="button" className="icon-button linked-item-remove-button" onClick={onRemove} aria-label={`Remove link to ${entity.title}`}>
        <Trash2 size={15} aria-hidden="true" />
      </button>
    </article>
  )
}

export function AddLinkedItemDrawer({
  currentRecordId,
  isOpen,
  linkedRecordIds,
  linkedReminderIds,
  records,
  reminders,
  onClose,
  onCreate,
}: {
  currentRecordId: string | null
  isOpen: boolean
  linkedRecordIds: Set<string>
  linkedReminderIds: Set<string>
  records: LifeRecord[]
  reminders: Reminder[]
  onClose: () => void
  onCreate: (input: LinkDraft) => Promise<void>
}) {
  const [step, setStep] = useState<AddStep>('type')
  const [targetType, setTargetType] = useState<CandidateType | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [relationshipType, setRelationshipType] = useState<RelationshipType>('related')
  const [label, setLabel] = useState('')
  const [search, setSearch] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setStep('type')
      setTargetType(null)
      setSelectedId(null)
      setRelationshipType('related')
      setLabel('')
      setSearch('')
      setError(null)
      setIsSaving(false)
    }
  }, [isOpen])

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
  const selectedTitle = selectedRecord?.title ?? selectedReminder?.title ?? ''

  const filteredRecords = filterRecords(recordCandidates, search)
  const filteredReminders = filterReminders(reminderCandidates, search)

  function chooseType(type: CandidateType) {
    setTargetType(type)
    setSelectedId(null)
    setRelationshipType(type === 'reminder' ? 'renews' : 'related')
    setSearch('')
    setStep('select')
  }

  function chooseRecord(record: LifeRecord) {
    setSelectedId(record.id)
    setRelationshipType(getDefaultRecordRelationship(record))
    setStep('relationship')
  }

  function chooseReminder(reminder: Reminder) {
    setSelectedId(reminder.id)
    setRelationshipType('renews')
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
      setError(requestError instanceof Error ? requestError.message : 'Unable to link item.')
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
            <h2 id="linked-picker-heading">Add linked item</h2>
            <p>{getPickerSubcopy(step, targetType)}</p>
          </div>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close add linked item">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="sheet-body linked-picker-body">
        {step === 'type' ? (
          <div className="linked-picker-type-options">
            <button type="button" className="linked-picker-type-card" onClick={() => chooseType('record')}>
              <span className="linked-picker-type-icon linked-picker-record-icon" aria-hidden="true"><FileText size={24} /></span>
              <span><strong>Record</strong><small>Link another record like insurance, warranty, or a vehicle.</small></span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
            <button type="button" className="linked-picker-type-card" onClick={() => chooseType('reminder')}>
              <span className="linked-picker-type-icon linked-picker-reminder-icon" aria-hidden="true"><Bell size={24} /></span>
              <span><strong>Reminder</strong><small>Link a reminder like registration renewal or maintenance.</small></span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </div>
        ) : null}

        {step === 'select' && targetType ? (
          <div className="linked-picker-select-step">
            <label className="linked-picker-search">
              <Search size={16} aria-hidden="true" />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={`Search ${targetType}s...`} />
            </label>
            {targetType === 'record' ? (
              <CandidateList
                emptyText="No records available to link."
                records={filteredRecords}
                onChooseRecord={chooseRecord}
              />
            ) : (
              <CandidateList
                emptyText="No reminders available to link."
                reminders={filteredReminders}
                onChooseReminder={chooseReminder}
              />
            )}
            <p className="linked-picker-footnote">Items already linked to this record are hidden.</p>
          </div>
        ) : null}

        {step === 'relationship' && targetType && selectedId ? (
          <div className="linked-picker-relationship-step">
            <div className="linked-picker-selected-item">
              <span className="linked-item-icon tone-other" aria-hidden="true">
                {targetType === 'record' ? <FileText size={18} /> : <Bell size={18} />}
              </span>
              <div>
                <strong>{selectedTitle}</strong>
                <span>{targetType === 'record' ? 'Record' : 'Reminder'}</span>
              </div>
            </div>

            <fieldset className="linked-relationship-options">
              <legend>How are they related?</legend>
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
              <span>Optional label</span>
              <input maxLength={40} value={label} onChange={(event) => setLabel(event.target.value)} placeholder="e.g. Primary insurance" />
              <small>{label.length}/40</small>
            </label>

            {error ? <p className="field-error" role="alert">{error}</p> : null}

            <button type="button" className="primary-button" disabled={isSaving} onClick={() => void submit()}>
              <Link2 size={17} aria-hidden="true" />
              {isSaving ? 'Linking...' : 'Link item'}
            </button>
          </div>
        ) : null}
      </div>
    </SheetDrawer>
  )
}

function CandidateList({
  emptyText,
  records = [],
  reminders = [],
  onChooseRecord,
  onChooseReminder,
}: {
  emptyText: string
  records?: LifeRecord[]
  reminders?: Reminder[]
  onChooseRecord?: (record: LifeRecord) => void
  onChooseReminder?: (reminder: Reminder) => void
}) {
  const hasRecords = records.length > 0
  const hasReminders = reminders.length > 0

  if (!hasRecords && !hasReminders) {
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
    return 'Choose what you want to link.'
  }
  if (step === 'select') {
    return targetType === 'record' ? 'Pick the record to link.' : 'Pick the reminder to link.'
  }
  return 'Pick how the items are related.'
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
  const relationship = item.label || relationshipLabels[item.relationship_type]

  if (entity.entity_type === 'record') {
    const typeLabel = entity.record_type ? getRecordTypeDefinition(entity.record_type).label : 'Record'
    return `${typeLabel} \u2022 ${relationship}`
  }

  const typeLabel = getReminderTypeLabel(entity.reminder_type ?? 'generic')
  const dueLabel = entity.due_date ? formatDueDateLabel(entity.due_date) : entity.status
  return [typeLabel, dueLabel, relationship].filter(Boolean).join(' \u2022 ')
}

function getLinkedItemIcon(item: LinkedItem) {
  const entity = item.linked_entity
  if (entity.entity_type === 'record' && entity.record_type) {
    return getRecordTypeDefinition(entity.record_type).icon
  }

  return Bell
}

function getRecordToneClass(recordType: LifeRecord['record_type'] | null) {
  if (!recordType) {
    return 'tone-other'
  }

  return `tone-${getRecordTypeDefinition(recordType).tone}`
}
