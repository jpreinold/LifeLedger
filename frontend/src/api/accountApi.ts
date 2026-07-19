import { apiRequest } from './apiClient'
import type { AccountOperation, AccountStatus, ExportDownload } from '../types/account'

export const accountApi = {
  getStatus: (signal?: AbortSignal) => apiRequest<AccountStatus>('/account/status', { signal }),

  createExport: (includeProtectedDetails: boolean) =>
    apiRequest<AccountOperation>('/account/exports', {
      method: 'POST',
      body: JSON.stringify({
        include_protected_details: includeProtectedDetails,
        confirm_sensitive_export: includeProtectedDetails,
      }),
    }),

  getExport: (operationId: string, signal?: AbortSignal) =>
    apiRequest<AccountOperation>(`/account/exports/${encodeURIComponent(operationId)}`, { signal }),

  createDownload: (operationId: string) =>
    apiRequest<ExportDownload>(`/account/exports/${encodeURIComponent(operationId)}/download`, {
      method: 'POST',
    }),

  requestDeletion: (confirmation: string) =>
    apiRequest<AccountOperation>('/account/deletion', {
      method: 'POST',
      body: JSON.stringify({ confirmation }),
    }),

  getDeletion: (operationId: string, signal?: AbortSignal) =>
    apiRequest<AccountOperation>(`/account/deletion/${encodeURIComponent(operationId)}`, { signal }),
}
