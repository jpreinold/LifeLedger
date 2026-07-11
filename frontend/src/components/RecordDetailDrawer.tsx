import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Archive,
  Eye,
  EyeOff,
  LockKeyhole,
  Pencil,
  RotateCcw,
  Trash2,
  X,
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
import { getProtectedFieldLabel, getRecordTypeDefinition } from '../lib/recordTypes'
import type { LifeRecord, ProtectedRecordPayload, ProtectedRecordStatus } from '../types/record'
import { RecordDocumentsPanel } from './RecordDocumentsPanel'
import { SheetDrawer } from './SheetDrawer'

export type RecordDetailTab = 'details' | 'documents'

interface RecordDetailDrawerProps {
  initialTab?: RecordDetailTab
  record: LifeRecord
  onArchive: (record: LifeRecord) => Promise<void>
  onClose: () => void
  onEdit: (record: LifeRecord) => void
  onProtectedStatusChange: (id: string, status: ProtectedRecordStatus) => void
  onRequestDelete: (record: LifeRecord) => void
  onRestore: (record: LifeRecord) => Promise<void>
}

interface DetailRow {
  label: string
  value: string | null | undefined
}

const drawerCloseMs = 220
const protectedRevealMs = 60_000

export function RecordDetailDrawer({
  initialTab = 'details',
  record,
  onArchive,
  onClose,
  onEdit,
  onProtectedStatusChange,
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
  const closeTimerRef = useRef<number | null>(null)
  const detailBodyRef = useRef<HTMLDivElement | null>(null)
  const openFrameRef = useRef<number | null>(null)
  const revealTimerRef = useRef<number | null>(null)
  const definition = getRecordTypeDefinition(record.record_type)
  const Icon = definition.icon
  const providerLine = getRecordProviderLine(record)
  const keyDate = formatRecordKeyDate(record) ?? 'No expiration date'
  const isArchived = record.status === 'archived'

  const resetDetailScroll = useCallback(() => {
    detailBodyRef.current?.scrollTo({ top: 0 })
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

  useEffect(() => {
    clearProtectedState()
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
  }, [clearProtectedState, initialTab, record.id, resetDetailScroll])

  useEffect(() => {
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current)
      }
      if (revealTimerRef.current !== null) {
        window.clearTimeout(revealTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (protectedPayload === null) {
      return undefined
    }

    revealTimerRef.current = window.setTimeout(clearProtectedState, protectedRevealMs)
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
        clearProtectedState()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [clearProtectedState])

  const requestClose = useCallback(() => {
    clearProtectedState()
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onClose()
    }, drawerCloseMs)
  }, [clearProtectedState, onClose])

  function selectTab(tab: RecordDetailTab) {
    setActiveTab(tab)
    window.requestAnimationFrame(resetDetailScroll)
  }

  function handleEdit() {
    clearProtectedState()
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
    } catch (requestError) {
      setProtectedError(requestError instanceof Error ? requestError.message : 'Unable to clear protected details.')
    } finally {
      setIsClearingProtected(false)
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
    <SheetDrawer className="detail-dialog record-detail-dialog" isOpen={isDrawerOpen} labelledBy="record-detail-heading" onClose={requestClose}>
      <div className="sheet-header detail-header">
        <div>
          <h2 id="record-detail-heading">Record details</h2>
          <p>{definition.label}</p>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={requestClose} aria-label="Close record details">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="detail-body" data-drawer-scroll ref={detailBodyRef}>
        <section className={`detail-hero tone-${definition.tone}`} aria-labelledby="record-detail-title">
          <div className={`category-icon category-icon-large tone-${definition.tone}`} aria-hidden="true">
            <Icon size={30} />
          </div>
          <div className="detail-hero-copy">
            <div className="card-chip-row">
              <span className="type-chip">{definition.label}</span>
              <span className="category-chip">{definition.category}</span>
              <span className={`status-chip ${getRecordStatusClass(record)}`}>{getRecordStatusLabel(record)}</span>
            </div>
            <h3 id="record-detail-title">{record.title}</h3>
            {record.subtitle ? <p>{record.subtitle}</p> : null}
            <p className="detail-smart-label">
              <Icon size={15} aria-hidden="true" />
              {keyDate}
            </p>
          </div>
        </section>

        <div className="record-detail-tabs" role="tablist" aria-label="Record detail tabs">
          <button
            type="button"
            className={activeTab === 'details' ? 'record-detail-tab active' : 'record-detail-tab'}
            id="record-details-tab"
            role="tab"
            aria-selected={activeTab === 'details'}
            aria-controls="record-details-panel"
            onClick={() => selectTab('details')}
          >
            Details
          </button>
          <button
            type="button"
            className={activeTab === 'documents' ? 'record-detail-tab active' : 'record-detail-tab'}
            id="record-documents-tab"
            role="tab"
            aria-selected={activeTab === 'documents'}
            aria-controls="record-documents-panel"
            onClick={() => selectTab('documents')}
          >
            Attachments
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
            title="Record"
            rows={[
              { label: 'Type', value: definition.label },
              { label: 'Category', value: definition.category },
              { label: 'Owner', value: record.owner_name },
              { label: 'Provider/brand', value: record.provider_or_brand },
              { label: 'Summary', value: providerLine },
              { label: 'Location', value: record.location_hint },
            ]}
          />

          <DetailSection
            title="Dates"
            className="detail-schedule-section"
            rows={[
              { label: 'Start date', value: formatRecordDate(record.start_date) },
              { label: 'Issue date', value: formatRecordDate(record.issue_date) },
              { label: 'Expiration date', value: formatRecordDate(record.expiration_date) },
              { label: 'Purchase date', value: formatRecordDate(record.purchase_date) },
              { label: 'Renewal date', value: formatRecordDate(record.renewal_date) },
            ]}
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

          <ProtectedDetailsSection
            error={protectedError}
            isClearing={isClearingProtected}
            isRevealing={isRevealingProtected}
            payload={protectedPayload}
            record={record}
            onClear={() => void handleClearProtected()}
            onHide={clearProtectedState}
            onReveal={() => void handleRevealProtected()}
          />

          <DetailSection
            title="History"
            rows={[
              { label: 'Created', value: formatRecordTimestamp(record.created_at) },
              { label: 'Updated', value: formatRecordTimestamp(record.updated_at) },
            ]}
          />
        </div>

        <div
          className="record-tab-panel"
          hidden={activeTab !== 'documents'}
          id="record-documents-panel"
          role="tabpanel"
          aria-labelledby="record-documents-tab"
        >
          <RecordDocumentsPanel isActive={isDrawerOpen && activeTab === 'documents'} recordId={record.id} />
        </div>
      </div>

      {activeTab === 'details' ? (
        <section className="detail-actions" aria-label="Record actions">
          <button type="button" className="secondary-button" onClick={handleEdit}>
            <Pencil size={17} aria-hidden="true" />
            Edit
          </button>
          <button type="button" className="primary-button" onClick={() => void handleArchiveToggle()} disabled={isArchiving}>
            {isArchived ? <RotateCcw size={17} aria-hidden="true" /> : <Archive size={17} aria-hidden="true" />}
            {isArchiving ? 'Saving...' : isArchived ? 'Restore' : 'Archive'}
          </button>
          <button type="button" className="text-danger-button detail-delete-button" onClick={() => onRequestDelete(record)}>
            <Trash2 size={16} aria-hidden="true" />
            Delete
          </button>
        </section>
      ) : null}
    </SheetDrawer>
  )
}

function DetailSection({ className = '', rows, title }: { className?: string; rows: DetailRow[]; title: string }) {
  const visibleRows = rows.filter((row) => hasValue(row.value))

  if (visibleRows.length === 0) {
    return null
  }

  return (
    <section className={`detail-section ${className}`.trim()} aria-label={title}>
      <h3>{title}</h3>
      <dl className="detail-list">
        {visibleRows.map((row) => (
          <div className="detail-row" key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
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
  const definition = getRecordTypeDefinition(record.record_type)
  const hasProtectedFieldsForType = definition.protectedFields.length > 0
  const hasProtectedData = record.has_protected_data && record.protected_field_names.length > 0

  if (!hasProtectedFieldsForType && !hasProtectedData) {
    return null
  }

  const isRevealed = payload !== null
  const fieldNames = hasProtectedData ? record.protected_field_names : definition.protectedFields
  const rows = fieldNames.map((field) => ({
    field,
    label: getProtectedFieldLabel(field),
    value: isRevealed ? payload?.[field] ?? null : null,
  }))

  return (
    <section className="detail-section protected-details-section" aria-label="Protected details">
      <div className="protected-details-heading">
        <div>
          <h3>Protected details</h3>
          <p>Encrypted before storage and revealed only when requested.</p>
        </div>
        <LockKeyhole size={18} aria-hidden="true" />
      </div>

      {!hasProtectedData ? <p className="protected-details-empty">No protected details saved.</p> : null}

      {hasProtectedData ? (
        <dl className="detail-list protected-detail-list">
          {rows.map((row) => (
            <div className="detail-row" key={row.field}>
              <dt>{row.label}</dt>
              <dd>{isRevealed && row.value ? row.value : 'Hidden'}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {error ? <p className="field-error protected-detail-error">{error}</p> : null}

      {hasProtectedData ? (
        <div className="protected-detail-actions">
          {isRevealed ? (
            <button type="button" className="secondary-button" onClick={onHide}>
              <EyeOff size={16} aria-hidden="true" />
              Hide details
            </button>
          ) : (
            <button type="button" className="primary-button" disabled={isRevealing} onClick={onReveal}>
              <Eye size={16} aria-hidden="true" />
              {isRevealing ? 'Revealing...' : 'Reveal protected details'}
            </button>
          )}
          <button type="button" className="text-danger-button" disabled={isClearing} onClick={onClear}>
            <Trash2 size={15} aria-hidden="true" />
            {isClearing ? 'Clearing...' : 'Clear protected details'}
          </button>
        </div>
      ) : null}
    </section>
  )
}

function hasValue(value: string | null | undefined) {
  return value !== null && value !== undefined && value.trim().length > 0
}
