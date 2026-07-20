import type { RecordType } from './record'

export const responsibilityEventTypes = [
  'responsibility_created',
  'completed',
  'renewed',
  'snoozed',
  'snooze_cleared',
  'reopened',
  'due_date_changed',
  'supporting_document_added',
  'history_tracking_started',
] as const

export type ResponsibilityEventType = (typeof responsibilityEventTypes)[number]
export type LifecycleReconciliationStatus = 'pending' | 'consistent' | 'needs_attention'

export interface ResponsibilityDocumentEvidence {
  document_id: string
  record_id: string | null
  display_name: string
  status: string
  available: boolean
}

export interface ResponsibilityEvent {
  event_id: string
  reminder_id: string
  item_id: string | null
  occurrence_id: string | null
  event_type: ResponsibilityEventType
  occurred_at: string
  effective_date: string | null
  previous_due_date: string | null
  next_due_date: string | null
  completed_at: string | null
  note: string | null
  source: 'user' | 'guided_workflow' | 'reconciliation' | 'assistant_capture' | 'system'
  schema_version: number
  created_at: string
  responsibility_title_snapshot: string | null
  item_title_snapshot: string | null
  item_type_snapshot: RecordType | null
  related_event_id: string | null
  reconciliation_status: LifecycleReconciliationStatus
  search_sync_status: LifecycleReconciliationStatus
  document_reference_status: LifecycleReconciliationStatus
  documents: ResponsibilityDocumentEvidence[]
}

export interface LifecycleReconciliationResult {
  reminder_id: string
  dry_run: boolean
  inspected: number
  repaired: number
  remaining: number
  results: string[]
}

export interface ResponsibilityHistoryPage {
  items: ResponsibilityEvent[]
  next_cursor: string | null
}

export interface CompleteResponsibilityInput {
  completed_on: string
  occurrence_id: string | null
  note: string | null
}

export interface RenewResponsibilityInput {
  new_due_date: string
  renewed_on: string
  occurrence_id: string | null
  note: string | null
}
