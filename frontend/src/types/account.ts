export type AccountState =
  | 'active'
  | 'export_pending'
  | 'deletion_requested'
  | 'deleting'
  | 'deletion_requires_attention'
  | 'deleted'

export type AccountOperationStatus = 'pending' | 'in_progress' | 'complete' | 'failed' | 'expired'

export interface AccountOperationStep {
  name: string
  status: 'pending' | 'in_progress' | 'complete' | 'failed'
  attempt_count: number
  retryable: boolean
  safe_error: string | null
  updated_at: string
}

export interface AccountOperation {
  operation_id: string
  operation_type: 'export' | 'deletion'
  status: AccountOperationStatus
  include_protected_details: boolean
  created_at: string
  updated_at: string
  expires_at: string | null
  artifact_size_bytes: number | null
  safe_error: string | null
  steps: AccountOperationStep[]
}

export interface AccountStatus {
  state: AccountState
  current_operation: AccountOperation | null
}

export interface ExportDownload {
  download_url: string
  expires_in_seconds: number
}
