import { getAuthorizationHeaders } from '../auth/session'
import type { SavedSearchView, SavedSearchViewInput, SavedSearchViewUpdate, SearchInput, SearchResponse } from '../types/search'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  const authorizationHeaders = await getAuthorizationHeaders()

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      cache: 'no-store',
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...authorizationHeaders,
        ...options.headers,
      },
    })
  } catch {
    throw new Error('Unable to reach the LifeLedger API. Make sure the Python backend is running.')
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`

    try {
      const body = await response.json()
      message = typeof body.detail === 'string' ? body.detail : message
    } catch {
      message = response.statusText || message
    }

    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

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
  search: (input: SearchInput) => request<SearchResponse>(`/search${buildSearchQuery(input)}`),

  listSavedViews: () => request<SavedSearchView[]>('/saved-views'),

  createSavedView: (input: SavedSearchViewInput) =>
    request<SavedSearchView>('/saved-views', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  updateSavedView: (id: string, input: SavedSearchViewUpdate) =>
    request<SavedSearchView>(`/saved-views/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }),

  deleteSavedView: (id: string) =>
    request<void>(`/saved-views/${id}`, {
      method: 'DELETE',
    }),
}
