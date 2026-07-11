import { useCallback, useEffect, useRef, useState } from 'react'
import { Archive, Pencil, RotateCcw, Trash2, X } from 'lucide-react'

import {
  formatRecordDate,
  formatRecordKeyDate,
  formatRecordTimestamp,
  getRecordProviderLine,
  getRecordStatusClass,
  getRecordStatusLabel,
} from '../lib/recordDisplay'
import { getRecordTypeDefinition } from '../lib/recordTypes'
import type { LifeRecord } from '../types/record'
import { SheetDrawer } from './SheetDrawer'

interface RecordDetailDrawerProps {
  record: LifeRecord
  onArchive: (record: LifeRecord) => Promise<void>
  onClose: () => void
  onEdit: (record: LifeRecord) => void
  onRequestDelete: (record: LifeRecord) => void
  onRestore: (record: LifeRecord) => Promise<void>
}

interface DetailRow {
  label: string
  value: string | null | undefined
}

const drawerCloseMs = 220

export function RecordDetailDrawer({
  record,
  onArchive,
  onClose,
  onEdit,
  onRequestDelete,
  onRestore,
}: RecordDetailDrawerProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [isArchiving, setIsArchiving] = useState(false)
  const closeTimerRef = useRef<number | null>(null)
  const detailBodyRef = useRef<HTMLDivElement | null>(null)
  const openFrameRef = useRef<number | null>(null)
  const definition = getRecordTypeDefinition(record.record_type)
  const Icon = definition.icon
  const providerLine = getRecordProviderLine(record)
  const keyDate = formatRecordKeyDate(record) ?? 'No expiration date'
  const isArchived = record.status === 'archived'
  const resetDetailScroll = useCallback(() => {
    detailBodyRef.current?.scrollTo({ top: 0 })
  }, [])

  useEffect(() => {
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
  }, [record.id, resetDetailScroll])

  useEffect(() => {
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current)
      }
    }
  }, [])

  const requestClose = useCallback(() => {
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onClose()
    }, drawerCloseMs)
  }, [onClose])

  function handleEdit() {
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onEdit(record)
    }, drawerCloseMs)
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

        <DetailSection
          title="History"
          rows={[
            { label: 'Created', value: formatRecordTimestamp(record.created_at) },
            { label: 'Updated', value: formatRecordTimestamp(record.updated_at) },
          ]}
        />
      </div>

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

function hasValue(value: string | null | undefined) {
  return value !== null && value !== undefined && value.trim().length > 0
}
