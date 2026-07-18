import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import {
  Archive,
  Bell,
  Bookmark,
  Calendar,
  ChevronRight,
  Clock,
  FileText,
  Folder,
  Layers,
  ListFilter,
  RotateCcw,
  Save,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { searchApi } from '../api/searchApi'
import {
  clearRecentSearches,
  isRememberRecentSearchesEnabled,
  loadRecentSearches,
  removeRecentSearch,
  saveRecentSearch,
  setRememberRecentSearches,
  type RecentSearch,
} from '../lib/recentSearches'
import type { LinkedEntityType } from '../types/linkedItem'
import type { SavedSearchView, SearchInput, SearchResponse, SearchResultItem, SearchSort, SearchStatus } from '../types/search'
import { ConfirmDialog } from './ConfirmDialog'

interface SearchViewProps {
  onViewRecord: (recordId: string) => void
  onViewReminder: (reminderId: string) => void
  onViewDocument: (recordId: string, documentId: string) => void
}

type TypeFilter = 'all' | LinkedEntityType
type StatusFilter = 'all' | SearchStatus

const typeOptions: Array<{ id: TypeFilter; label: string; icon: LucideIcon }> = [
  { id: 'all', label: 'All', icon: Layers },
  { id: 'record', label: 'Records', icon: Folder },
  { id: 'document', label: 'Documents', icon: FileText },
  { id: 'reminder', label: 'Reminders', icon: Bell },
]

const statusOptions: Array<{ id: StatusFilter; label: string }> = [
  { id: 'all', label: 'Any status' },
  { id: 'active', label: 'Active' },
  { id: 'overdue', label: 'Overdue' },
  { id: 'due_soon', label: 'Due soon' },
  { id: 'available', label: 'Available' },
  { id: 'archived', label: 'Archived' },
]

const sortOptions: Array<{ id: SearchSort; label: string }> = [
  { id: 'relevance', label: 'Relevance' },
  { id: 'updated_desc', label: 'Updated' },
  { id: 'relevant_date_asc', label: 'Date' },
  { id: 'title_asc', label: 'Title' },
]

export function SearchView({ onViewRecord, onViewReminder, onViewDocument }: SearchViewProps) {
  const [query, setQuery] = useState('')
  const [activeType, setActiveType] = useState<TypeFilter>('all')
  const [activeStatus, setActiveStatus] = useState<StatusFilter>('all')
  const [sort, setSort] = useState<SearchSort>('relevance')
  const [showArchived, setShowArchived] = useState(false)
  const [hasDocuments, setHasDocuments] = useState(false)
  const [hasLinkedItems, setHasLinkedItems] = useState(false)
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [items, setItems] = useState<SearchResultItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rememberRecentSearches, setRememberRecentSearchesState] = useState(() => isRememberRecentSearchesEnabled())
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>(() => loadRecentSearches())
  const [savedViews, setSavedViews] = useState<SavedSearchView[]>([])
  const [isFilterOpen, setIsFilterOpen] = useState(false)
  const [isSavedPanelOpen, setIsSavedPanelOpen] = useState(false)
  const [isSavingView, setIsSavingView] = useState(false)
  const [isDeletingSavedView, setIsDeletingSavedView] = useState(false)
  const [saveViewName, setSaveViewName] = useState('')
  const [pendingSavedViewDelete, setPendingSavedViewDelete] = useState<SavedSearchView | null>(null)
  const requestIdRef = useRef(0)

  const searchInput = useMemo<SearchInput>(
    () => ({
      q: query,
      itemTypes: activeType === 'all' ? undefined : [activeType],
      statuses: activeStatus === 'all' ? undefined : [activeStatus],
      archived: showArchived,
      hasDocuments: hasDocuments ? true : null,
      hasLinkedItems: hasLinkedItems ? true : null,
      sort,
      pageSize: 12,
    }),
    [activeStatus, activeType, hasDocuments, hasLinkedItems, query, showArchived, sort],
  )

  useEffect(() => {
    let isCancelled = false

    async function loadSavedViews() {
      try {
        const views = await searchApi.listSavedViews()
        if (!isCancelled) {
          setSavedViews(views)
        }
      } catch {
        if (!isCancelled) {
          setSavedViews([])
        }
      }
    }

    void loadSavedViews()

    return () => {
      isCancelled = true
    }
  }, [])

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void runSearch(searchInput, { append: false })
    }, 220)

    return () => window.clearTimeout(handle)
  }, [searchInput])

  async function runSearch(input: SearchInput, options: { append: boolean }) {
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    setError(null)
    if (options.append) {
      setIsLoadingMore(true)
    } else {
      setIsLoading(true)
    }

    try {
      const nextResponse = await searchApi.search(input)
      if (requestId !== requestIdRef.current) {
        return
      }
      setResponse(nextResponse)
      setItems((current) => (options.append ? [...current, ...nextResponse.items] : nextResponse.items))
    } catch (requestError) {
      if (requestId !== requestIdRef.current) {
        return
      }
      setError(requestError instanceof Error ? requestError.message : 'Unable to search.')
      if (!options.append) {
        setItems([])
        setResponse(null)
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoading(false)
        setIsLoadingMore(false)
      }
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setRecentSearches(saveRecentSearch(query))
    void runSearch(searchInput, { append: false })
  }

  function applySavedView(view: SavedSearchView) {
    const filters = view.filters
    setQuery(view.query)
    setSort(view.sort)
    setActiveType(getSingleFilterValue(filters.itemTypes, typeOptions.map((item) => item.id)) ?? 'all')
    setActiveStatus(getSingleFilterValue(filters.statuses, statusOptions.map((item) => item.id)) ?? 'all')
    setShowArchived(Boolean(filters.archived))
    setHasDocuments(Boolean(filters.hasDocuments))
    setHasLinkedItems(Boolean(filters.hasLinkedItems))
    setIsSavedPanelOpen(false)
  }

  async function saveCurrentView() {
    const name = saveViewName.trim()
    if (!name) {
      return
    }

    setIsSavingView(true)
    setError(null)
    try {
      const created = await searchApi.createSavedView({
        name,
        query: query.trim(),
        filters: buildSavedFilters(),
        sort,
        icon: activeType === 'document' ? 'document' : activeType === 'reminder' ? 'reminder' : 'folder',
        is_pinned: false,
      })
      setSavedViews((current) => [...current, created].sort(sortSavedViews))
      setSaveViewName('')
      setIsSavedPanelOpen(true)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to save this view.')
    } finally {
      setIsSavingView(false)
    }
  }

  async function deleteSavedView(viewId: string) {
    setIsDeletingSavedView(true)
    setError(null)
    try {
      await searchApi.deleteSavedView(viewId)
      setSavedViews((current) => current.filter((view) => view.saved_view_id !== viewId))
      setPendingSavedViewDelete(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to delete this view.')
    } finally {
      setIsDeletingSavedView(false)
    }
  }

  function clearRecents() {
    setRecentSearches(clearRecentSearches())
  }

  function toggleRememberRecents(enabled: boolean) {
    const storedSetting = setRememberRecentSearches(enabled)
    setRememberRecentSearchesState(storedSetting)
    setRecentSearches(storedSetting ? loadRecentSearches() : [])
  }

  function loadMore() {
    if (!response?.next_cursor || isLoadingMore) {
      return
    }
    void runSearch({ ...searchInput, cursor: response.next_cursor }, { append: true })
  }

  function openResult(item: SearchResultItem) {
    if (item.source_item_type === 'record') {
      onViewRecord(item.navigation_metadata.record_id ?? item.source_item_id)
      return
    }
    if (item.source_item_type === 'reminder') {
      onViewReminder(item.navigation_metadata.reminder_id ?? item.source_item_id)
      return
    }
    const recordId = item.navigation_metadata.record_id
    const documentId = item.navigation_metadata.attachment_id ?? item.navigation_metadata.document_id ?? item.source_item_id
    if (recordId) {
      onViewDocument(recordId, documentId)
    }
  }

  const hasActiveFilters = activeType !== 'all' || activeStatus !== 'all' || showArchived || hasDocuments || hasLinkedItems
  const isInitialEmpty = !query.trim() && !hasActiveFilters
  const resultCount = response?.result_count ?? 0

  return (
    <section className="search-view" aria-labelledby="search-heading">
      <div className="search-toolbar">
        <div>
          <h2 id="search-heading">Search</h2>
          <p>{resultCount === 1 ? '1 match' : `${resultCount} matches`}</p>
        </div>
        <button type="button" className="icon-button" onClick={() => setIsSavedPanelOpen(true)} aria-label="Open saved views">
          <Bookmark size={19} aria-hidden="true" />
        </button>
      </div>

      <form className="search-form" onSubmit={handleSubmit}>
        <label className="search-input-shell">
          <Search size={17} aria-hidden="true" />
          <input
            type="search"
            value={query}
            placeholder="Search records, docs, reminders..."
            onChange={(event) => setQuery(event.currentTarget.value)}
          />
          {query ? (
            <button type="button" onClick={() => setQuery('')} aria-label="Clear search">
              <X size={16} aria-hidden="true" />
            </button>
          ) : null}
        </label>
        <button type="button" className={hasActiveFilters ? 'search-filter-button active' : 'search-filter-button'} onClick={() => setIsFilterOpen(true)} aria-label="Open filters">
          <SlidersHorizontal size={18} aria-hidden="true" />
        </button>
      </form>

      <div className="search-chip-row" aria-label="Search type filters">
        {typeOptions.map((option) => {
          const Icon = option.icon
          return (
            <button
              type="button"
              key={option.id}
              className={activeType === option.id ? 'search-chip active' : 'search-chip'}
              onClick={() => setActiveType(option.id)}
              aria-pressed={activeType === option.id}
            >
              <Icon size={14} aria-hidden="true" />
              {option.label}
            </button>
          )
        })}
      </div>

      <div className="search-sort-row">
        <span>{hasActiveFilters ? 'Filters applied' : 'No filters'}</span>
        <label>
          <ListFilter size={14} aria-hidden="true" />
          <select value={sort} onChange={(event) => setSort(event.currentTarget.value as SearchSort)}>
            {sortOptions.map((option) => (
              <option value={option.id} key={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? <p className="search-error" role="alert">{error}</p> : null}

      {isInitialEmpty ? (
        <SearchStartState
          recentSearches={recentSearches}
          rememberRecentSearches={rememberRecentSearches}
          savedViews={savedViews}
          onClearRecent={clearRecents}
          onRemoveRecent={(createdAt) => setRecentSearches(removeRecentSearch(createdAt))}
          onRememberRecentChange={toggleRememberRecents}
          onRunRecent={(value) => {
            setQuery(value)
            setRecentSearches(saveRecentSearch(value))
          }}
          onApplySavedView={applySavedView}
        />
      ) : null}

      {!isInitialEmpty ? (
        <div className="search-results" aria-live="polite">
          {isLoading ? <p className="search-loading">Searching...</p> : null}
          {!isLoading && items.length === 0 ? (
            <div className="search-empty-state">
              <Search size={42} aria-hidden="true" />
              <strong>No results found</strong>
              <button type="button" className="secondary-button" onClick={resetFilters}>
                <RotateCcw size={16} aria-hidden="true" />
                Clear filters
              </button>
            </div>
          ) : null}
          {!isLoading && items.map((item) => <SearchResultCard item={item} key={`${item.source_item_type}-${item.source_item_id}`} onOpen={() => openResult(item)} />)}
          {!isLoading && response?.next_cursor ? (
            <button type="button" className="secondary-button search-load-more" disabled={isLoadingMore} onClick={loadMore}>
              {isLoadingMore ? 'Loading...' : 'Load more'}
            </button>
          ) : null}
        </div>
      ) : null}

      {isFilterOpen ? (
        <div className="search-sheet-backdrop" role="presentation">
          <aside className="search-filter-sheet" aria-label="Filters">
            <div className="search-sheet-header">
              <button type="button" className="icon-button" onClick={() => setIsFilterOpen(false)} aria-label="Close filters">
                <X size={18} aria-hidden="true" />
              </button>
              <strong>Filters</strong>
              <button type="button" className="text-button" onClick={resetFilters}>
                Clear
              </button>
            </div>

            <SearchFilterSection title="Type">
              <div className="search-filter-grid">
                {typeOptions.map((option) => {
                  const Icon = option.icon
                  return (
                    <button
                      type="button"
                      key={option.id}
                      className={activeType === option.id ? 'search-filter-tile active' : 'search-filter-tile'}
                      onClick={() => setActiveType(option.id)}
                    >
                      <Icon size={18} aria-hidden="true" />
                      {option.label}
                    </button>
                  )
                })}
              </div>
            </SearchFilterSection>

            <SearchFilterSection title="Status">
              <div className="search-chip-row search-chip-row-wrap">
                {statusOptions.map((option) => (
                  <button
                    type="button"
                    key={option.id}
                    className={activeStatus === option.id ? 'search-chip active' : 'search-chip'}
                    onClick={() => setActiveStatus(option.id)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </SearchFilterSection>

            <SearchFilterSection title="Has">
              <label className="search-toggle-row">
                <span>
                  <FileText size={16} aria-hidden="true" />
                  Documents
                </span>
                <input type="checkbox" checked={hasDocuments} onChange={(event) => setHasDocuments(event.currentTarget.checked)} />
              </label>
              <label className="search-toggle-row">
                <span>
                  <Layers size={16} aria-hidden="true" />
                  Linked items
                </span>
                <input type="checkbox" checked={hasLinkedItems} onChange={(event) => setHasLinkedItems(event.currentTarget.checked)} />
              </label>
              <label className="search-toggle-row">
                <span>
                  <Archive size={16} aria-hidden="true" />
                  Archived
                </span>
                <input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.currentTarget.checked)} />
              </label>
            </SearchFilterSection>

            <button type="button" className="primary-button search-apply-button" onClick={() => setIsFilterOpen(false)}>
              Apply filters
            </button>
          </aside>
        </div>
      ) : null}

      {isSavedPanelOpen ? (
        <div className="search-sheet-backdrop" role="presentation">
          <aside className="search-filter-sheet search-saved-sheet" aria-label="Saved views">
            <div className="search-sheet-header">
              <button type="button" className="icon-button" onClick={() => setIsSavedPanelOpen(false)} aria-label="Close saved views">
                <X size={18} aria-hidden="true" />
              </button>
              <strong>Saved views</strong>
              <span />
            </div>

            <div className="saved-view-form">
              <label>
                <span>View name</span>
                <input value={saveViewName} onChange={(event) => setSaveViewName(event.currentTarget.value)} placeholder="Travel documents" maxLength={80} />
              </label>
              <button type="button" className="primary-button" disabled={isSavingView || !saveViewName.trim()} onClick={saveCurrentView}>
                <Save size={16} aria-hidden="true" />
                {isSavingView ? 'Saving...' : 'Save view'}
              </button>
            </div>

            <div className="saved-view-list">
              {savedViews.length === 0 ? <p className="search-muted">No saved views yet.</p> : null}
              {savedViews.map((view) => (
                <div className="saved-view-row" key={view.saved_view_id}>
                  <button type="button" onClick={() => applySavedView(view)}>
                    <Bookmark size={17} aria-hidden="true" />
                    <span>
                      <strong>{view.name}</strong>
                      <small>{view.query || 'All items'} · {formatSavedFilters(view.filters)}</small>
                    </span>
                    <ChevronRight size={16} aria-hidden="true" />
                  </button>
                  <button type="button" className="icon-button" onClick={() => setPendingSavedViewDelete(view)} aria-label={`Delete ${view.name}`}>
                    <Trash2 size={16} aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          </aside>
        </div>
      ) : null}

      <ConfirmDialog
        body={pendingSavedViewDelete ? `The saved view "${pendingSavedViewDelete.name}" will be permanently deleted. Records, reminders, documents, and recent searches will remain.` : ''}
        confirmLabel="Delete saved view"
        isBusy={isDeletingSavedView}
        isOpen={pendingSavedViewDelete !== null}
        title="Delete saved view?"
        onCancel={() => setPendingSavedViewDelete(null)}
        onConfirm={() => pendingSavedViewDelete && void deleteSavedView(pendingSavedViewDelete.saved_view_id)}
      />
    </section>
  )

  function resetFilters() {
    setActiveType('all')
    setActiveStatus('all')
    setShowArchived(false)
    setHasDocuments(false)
    setHasLinkedItems(false)
  }

  function buildSavedFilters() {
    return {
      itemTypes: activeType === 'all' ? [] : [activeType],
      statuses: activeStatus === 'all' ? [] : [activeStatus],
      archived: showArchived,
      hasDocuments,
      hasLinkedItems,
    }
  }
}

function SearchStartState({
  recentSearches,
  rememberRecentSearches,
  savedViews,
  onClearRecent,
  onRemoveRecent,
  onRememberRecentChange,
  onRunRecent,
  onApplySavedView,
}: {
  recentSearches: RecentSearch[]
  rememberRecentSearches: boolean
  savedViews: SavedSearchView[]
  onClearRecent: () => void
  onRemoveRecent: (createdAt: string) => void
  onRememberRecentChange: (enabled: boolean) => void
  onRunRecent: (query: string) => void
  onApplySavedView: (view: SavedSearchView) => void
}) {
  return (
    <div className="search-start-state">
      <section className="search-panel" aria-labelledby="recent-searches-heading">
        <div className="search-section-header">
          <h3 id="recent-searches-heading">Recent searches</h3>
          {rememberRecentSearches && recentSearches.length > 0 ? (
            <button type="button" className="text-button" onClick={onClearRecent}>Clear all</button>
          ) : null}
        </div>
        <label className="search-toggle-row recent-search-setting">
          <span>Remember recent searches on this device</span>
          <input type="checkbox" checked={rememberRecentSearches} onChange={(event) => onRememberRecentChange(event.currentTarget.checked)} />
        </label>
        {!rememberRecentSearches ? <p className="search-muted">Off by default. Search text is not saved on this device.</p> : null}
        {rememberRecentSearches && recentSearches.length === 0 ? <p className="search-muted">No recent searches.</p> : null}
        {rememberRecentSearches ? recentSearches.map((item) => (
          <div className="recent-search-row-with-remove" key={`${item.query}-${item.createdAt}`}>
            <button type="button" className="recent-search-row" onClick={() => onRunRecent(item.query)}>
              <Clock size={15} aria-hidden="true" />
              <span>{item.query}</span>
              <small>{formatRelativeDate(item.createdAt)}</small>
            </button>
            <button type="button" className="icon-button" onClick={() => onRemoveRecent(item.createdAt)} aria-label={`Remove recent search ${item.query}`}>
              <X size={14} aria-hidden="true" />
            </button>
          </div>
        )) : null}
      </section>

      <section className="search-panel" aria-labelledby="saved-views-heading">
        <div className="search-section-header">
          <h3 id="saved-views-heading">Saved views</h3>
        </div>
        {savedViews.length === 0 ? <p className="search-muted">No saved views.</p> : null}
        {savedViews.slice(0, 4).map((view) => (
          <button type="button" className="recent-search-row" key={view.saved_view_id} onClick={() => onApplySavedView(view)}>
            <Bookmark size={15} aria-hidden="true" />
            <span>{view.name}</span>
            <ChevronRight size={15} aria-hidden="true" />
          </button>
        ))}
      </section>
    </div>
  )
}

function SearchFilterSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="search-filter-section">
      <h3>{title}</h3>
      {children}
    </section>
  )
}

function SearchResultCard({ item, onOpen }: { item: SearchResultItem; onOpen: () => void }) {
  const Icon = item.source_item_type === 'record' ? Folder : item.source_item_type === 'document' ? FileText : Calendar

  return (
    <article className="search-result-card">
      <button type="button" onClick={onOpen}>
        <span className={`search-result-icon type-${item.source_item_type}`} aria-hidden="true">
          <Icon size={20} />
        </span>
        <span className="search-result-copy">
          <span className="search-result-kicker">
            {formatItemType(item.source_item_type)}
            {item.status ? <em>{formatStatus(item.status)}</em> : null}
          </span>
          <strong>{item.title}</strong>
          {item.subtitle ? <span>{item.subtitle}</span> : null}
          <small>{formatResultMeta(item)}</small>
          {item.match_context.length > 0 || item.linked_context.length > 0 ? (
            <span className="search-result-context">{[...item.match_context, ...item.linked_context].slice(0, 2).join(' · ')}</span>
          ) : null}
        </span>
        <ChevronRight size={18} aria-hidden="true" />
      </button>
    </article>
  )
}

function getSingleFilterValue<T extends string>(value: unknown, allowed: T[]): T | null {
  if (!Array.isArray(value) || value.length !== 1 || typeof value[0] !== 'string') {
    return null
  }
  return allowed.includes(value[0] as T) ? (value[0] as T) : null
}

function sortSavedViews(a: SavedSearchView, b: SavedSearchView) {
  if (a.is_pinned !== b.is_pinned) {
    return a.is_pinned ? -1 : 1
  }
  return a.name.localeCompare(b.name)
}

function formatItemType(type: LinkedEntityType) {
  return type === 'record' ? 'Record' : type === 'document' ? 'Document' : 'Reminder'
}

function formatStatus(status: string) {
  return status.replace(/_/g, ' ').replace(/\b\w/g, (character) => character.toLocaleUpperCase())
}

function formatResultMeta(item: SearchResultItem) {
  const parts = [item.category, item.relevant_date ? formatDate(item.relevant_date) : null].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : formatDate(item.updated_at)
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 10)
  }
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

function formatRelativeDate(value: string) {
  const created = new Date(value).getTime()
  if (Number.isNaN(created)) {
    return ''
  }
  const days = Math.floor((Date.now() - created) / 86_400_000)
  if (days <= 0) {
    return 'Today'
  }
  if (days === 1) {
    return 'Yesterday'
  }
  return `${days} days ago`
}

function formatSavedFilters(filters: Record<string, unknown>) {
  const parts: string[] = []
  const itemTypes = Array.isArray(filters.itemTypes) ? filters.itemTypes : []
  const statuses = Array.isArray(filters.statuses) ? filters.statuses : []
  if (itemTypes.length > 0) {
    parts.push(itemTypes.map(String).join(', '))
  }
  if (statuses.length > 0) {
    parts.push(statuses.map(String).join(', '))
  }
  if (filters.hasDocuments) {
    parts.push('documents')
  }
  if (filters.hasLinkedItems) {
    parts.push('linked')
  }
  if (filters.archived) {
    parts.push('archived')
  }
  return parts.join(' · ') || 'All items'
}
