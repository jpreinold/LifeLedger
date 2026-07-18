import { apiRequest } from './apiClient'
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
  listRecordLinks: (recordId: string) => apiRequest<LinkedItemsResponse>(`/records/${recordId}/links`),

  createRecordLink: (recordId: string, input: LinkCreateRequest) =>
    apiRequest<LinkedItem>(`/records/${recordId}/links`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  deleteRecordLink: (recordId: string, linkId: string) =>
    apiRequest<void>(`/records/${recordId}/links/${linkId}`, {
      method: 'DELETE',
    }),

  listReminderLinks: (reminderId: string) => apiRequest<LinkedItemsResponse>(`/reminders/${reminderId}/links`),

  deleteReminderLink: (reminderId: string, linkId: string) =>
    apiRequest<void>(`/reminders/${reminderId}/links/${linkId}`, {
      method: 'DELETE',
    }),

  createRelationship: (input: RelationshipCreateRequest) =>
    apiRequest<RelationshipResponse>('/relationships', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  updateRelationship: (relationshipId: string, input: RelationshipUpdateRequest) =>
    apiRequest<RelationshipResponse>(`/relationships/${relationshipId}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }),

  deleteRelationship: (relationshipId: string) =>
    apiRequest<void>(`/relationships/${relationshipId}`, {
      method: 'DELETE',
    }),

  listCandidates: (input: {
    sourceItemType: LinkedEntityType
    sourceItemId: string
    itemType?: LinkedEntityType | null
    query?: string
    includeArchived?: boolean
    limit?: number
  }) => apiRequest<RelationshipCandidatesResponse>(`/relationships/candidates${buildQuery({
    source_item_type: input.sourceItemType,
    source_item_id: input.sourceItemId,
    item_type: input.itemType,
    q: input.query,
    include_archived: input.includeArchived,
    limit: input.limit,
  })}`),
}
