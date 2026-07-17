import type { LinkedEntityType } from './linkedItem'

export type SearchSort =
  | 'relevance'
  | 'updated_desc'
  | 'created_desc'
  | 'relevant_date_asc'
  | 'relevant_date_desc'
  | 'title_asc'

export type SearchStatus = 'active' | 'archived' | 'overdue' | 'due_today' | 'due_soon' | 'scheduled' | 'completed' | 'available' | 'scanning' | 'pending_upload' | 'uploaded' | 'rejected' | 'scan_failed'

export interface SearchResultItem {
  source_item_id: string
  source_item_type: LinkedEntityType
  title: string
  subtitle: string | null
  status: string | null
  category: string | null
  relevant_date: string | null
  archived: boolean
  match_context: string[]
  linked_context: string[]
  navigation_metadata: Record<string, string>
  updated_at: string
}

export interface SearchResponse {
  items: SearchResultItem[]
  next_cursor: string | null
  applied_filters: Record<string, unknown>
  result_count: number
}

export interface SearchInput {
  q?: string
  itemTypes?: LinkedEntityType[]
  statuses?: SearchStatus[]
  archived?: boolean
  dateFrom?: string | null
  dateTo?: string | null
  category?: string | null
  owner?: string | null
  hasDocuments?: boolean | null
  hasLinkedItems?: boolean | null
  sort?: SearchSort
  pageSize?: number
  cursor?: string | null
}

export interface SavedSearchView {
  saved_view_id: string
  name: string
  query: string
  filters: Record<string, unknown>
  sort: SearchSort
  icon: string | null
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export interface SavedSearchViewInput {
  name: string
  query: string
  filters: Record<string, unknown>
  sort: SearchSort
  icon?: string | null
  is_pinned?: boolean
}

export type SavedSearchViewUpdate = Partial<SavedSearchViewInput>
