import { getAuthorizationHeaders } from '../auth/session'
import type {
  LinkCreateRequest,
  LinkedEntityType,
  LinkedItemsResponse,
  LinkedItem,
  RelationshipCandidatesResponse,
  RelationshipCreateRequest,
  RelationshipResponse,
  RelationshipUpdateRequest,
} from '../types/linkedItem'

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

function buildQuery(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

export const linkedItemsApi = {
  listRecordLinks: (recordId: string) => request<LinkedItemsResponse>(`/records/${recordId}/links`),

  createRecordLink: (recordId: string, input: LinkCreateRequest) =>
    request<LinkedItem>(`/records/${recordId}/links`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  deleteRecordLink: (recordId: string, linkId: string) =>
    request<void>(`/records/${recordId}/links/${linkId}`, {
      method: 'DELETE',
    }),

  listReminderLinks: (reminderId: string) => request<LinkedItemsResponse>(`/reminders/${reminderId}/links`),

  deleteReminderLink: (reminderId: string, linkId: string) =>
    request<void>(`/reminders/${reminderId}/links/${linkId}`, {
      method: 'DELETE',
    }),

  createRelationship: (input: RelationshipCreateRequest) =>
    request<RelationshipResponse>('/relationships', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  updateRelationship: (relationshipId: string, input: RelationshipUpdateRequest) =>
    request<RelationshipResponse>(`/relationships/${relationshipId}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }),

  deleteRelationship: (relationshipId: string) =>
    request<void>(`/relationships/${relationshipId}`, {
      method: 'DELETE',
    }),

  listCandidates: (input: {
    sourceItemType: LinkedEntityType
    sourceItemId: string
    itemType?: LinkedEntityType | null
    query?: string
    includeArchived?: boolean
    limit?: number
  }) => request<RelationshipCandidatesResponse>(`/relationships/candidates${buildQuery({
    source_item_type: input.sourceItemType,
    source_item_id: input.sourceItemId,
    item_type: input.itemType,
    q: input.query,
    include_archived: input.includeArchived,
    limit: input.limit,
  })}`),
}
