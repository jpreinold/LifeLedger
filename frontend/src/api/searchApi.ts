import { apiRequest } from './apiClient'
import type { SavedSearchView, SavedSearchViewInput, SavedSearchViewUpdate, SearchInput, SearchResponse } from '../types/search'

function buildSearchQuery(input: SearchInput) {
  const search = new URLSearchParams()
  const entries: Record<string, string | number | boolean | null | undefined> = {
    q: input.q,
    itemTypes: input.itemTypes?.join(','),
    statuses: input.statuses?.join(','),
    archived: input.archived,
    dateFrom: input.dateFrom,
    dateTo: input.dateTo,
    category: input.category,
    owner: input.owner,
    hasDocuments: input.hasDocuments,
    hasLinkedItems: input.hasLinkedItems,
    sort: input.sort,
    pageSize: input.pageSize,
    cursor: input.cursor,
  }

  for (const [key, value] of Object.entries(entries)) {
    if (value !== null && value !== undefined && value !== '' && value !== false) {
      search.set(key, String(value))
    }
  }

  const query = search.toString()
  return query ? `?${query}` : ''
}

export const searchApi = {
  search: (input: SearchInput) => apiRequest<SearchResponse>(`/search${buildSearchQuery(input)}`),

  listSavedViews: () => apiRequest<SavedSearchView[]>('/saved-views'),

  createSavedView: (input: SavedSearchViewInput) =>
    apiRequest<SavedSearchView>('/saved-views', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  updateSavedView: (id: string, input: SavedSearchViewUpdate) =>
    apiRequest<SavedSearchView>(`/saved-views/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }),

  deleteSavedView: (id: string) =>
    apiRequest<void>(`/saved-views/${id}`, {
      method: 'DELETE',
    }),
}
