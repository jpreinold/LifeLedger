import { Archive, ChevronRight, FileText, LockKeyhole, Plus } from 'lucide-react'

import {
  formatRecordKeyDate,
  getRecordProviderLine,
  getRecordStatusClass,
  getRecordStatusLabel,
} from '../lib/recordDisplay'
import { getRecordTypeDefinition, recordFilterOptions, type RecordFilter } from '../lib/recordTypes'
import type { LifeRecord } from '../types/record'

interface RecordsViewProps {
  activeFilter: RecordFilter
  isLoading: boolean
  records: LifeRecord[]
  showArchived: boolean
  onAddRecord: () => void
  onFilterChange: (filter: RecordFilter) => void
  onShowArchivedChange: (showArchived: boolean) => void
  onViewRecord: (record: LifeRecord) => void
}

export function RecordsView({
  activeFilter,
  isLoading,
  records,
  showArchived,
  onAddRecord,
  onFilterChange,
  onShowArchivedChange,
  onViewRecord,
}: RecordsViewProps) {
  const archivedCount = records.filter((record) => record.status === 'archived').length
  const activeCount = records.filter((record) => record.status !== 'archived').length
  const visibleRecords = records
    .filter((record) => (showArchived ? record.status === 'archived' : record.status !== 'archived'))
    .filter((record) => activeFilter === 'all' || getRecordTypeDefinition(record.record_type).category === activeFilter)

  return (
    <section className="records-page" aria-labelledby="records-heading">
      <div className="records-page-header">
        <div>
          <h2 id="records-heading">Records</h2>
          <p>Keep important personal details organized.</p>
        </div>
        <button type="button" className="primary-button records-add-button" onClick={onAddRecord}>
          <Plus size={17} aria-hidden="true" />
          Add record
        </button>
      </div>

      <div className="records-summary-strip" aria-label="Records summary">
        <span>
          <strong>{activeCount}</strong>
          Active
        </span>
        <span>
          <strong>{archivedCount}</strong>
          Archived
        </span>
      </div>

      <div className="filter-tabs record-filter-tabs" role="tablist" aria-label="Record filters">
        {recordFilterOptions.map((filter) => (
          <button
            type="button"
            className={activeFilter === filter.id ? 'filter-tab active' : 'filter-tab'}
            key={filter.id}
            onClick={() => onFilterChange(filter.id)}
            aria-pressed={activeFilter === filter.id}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {archivedCount > 0 ? (
        <button
          type="button"
          className={showArchived ? 'small-outline-button records-archive-toggle active' : 'small-outline-button records-archive-toggle'}
          onClick={() => onShowArchivedChange(!showArchived)}
          aria-pressed={showArchived}
        >
          <Archive size={14} aria-hidden="true" />
          {showArchived ? 'Showing archived' : 'Show archived'}
        </button>
      ) : null}

      {isLoading ? <p className="empty-state">Loading records...</p> : null}

      {!isLoading && visibleRecords.length === 0 ? (
        <div className="empty-state empty-state-card records-empty-state">
          <FileText size={28} aria-hidden="true" />
          <p>{showArchived ? 'No archived records match this filter.' : 'No records yet.'}</p>
          {!showArchived ? (
            <button type="button" className="primary-button empty-add-button" onClick={onAddRecord}>
              <Plus size={17} aria-hidden="true" />
              Add record
            </button>
          ) : null}
        </div>
      ) : null}

      {!isLoading && visibleRecords.length > 0 ? (
        <div className="records-list" aria-label="Records list">
          {visibleRecords.map((record) => (
            <RecordCard record={record} key={record.id} onView={() => onViewRecord(record)} />
          ))}
        </div>
      ) : null}
    </section>
  )
}

function RecordCard({ record, onView }: { record: LifeRecord; onView: () => void }) {
  const definition = getRecordTypeDefinition(record.record_type)
  const Icon = definition.icon
  const keyDate = formatRecordKeyDate(record)
  const providerLine = getRecordProviderLine(record)

  return (
    <article className="record-card">
      <button type="button" className="record-card-main" onClick={onView}>
        <span className={`category-icon tone-${definition.tone}`} aria-hidden="true">
          <Icon size={22} />
        </span>
        <span className="record-card-copy">
          <span className="card-chip-row">
            <span className="type-chip">{definition.label}</span>
            <span className={`status-chip ${getRecordStatusClass(record)}`}>{getRecordStatusLabel(record)}</span>
          </span>
          <strong>{record.title}</strong>
          <span>{record.subtitle || definition.category}</span>
          {keyDate ? <small>{keyDate}</small> : null}
          {providerLine ? <small>{providerLine}</small> : null}
          {record.has_protected_data ? (
            <small className="record-protected-indicator">
              <LockKeyhole size={13} aria-hidden="true" />
              Protected details saved
            </small>
          ) : null}
        </span>
        <ChevronRight size={18} aria-hidden="true" className="record-card-chevron" />
      </button>
    </article>
  )
}
