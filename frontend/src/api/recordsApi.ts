import { apiRequest } from './apiClient'
import type {
  DynamicRecordFieldInput,
  DynamicRecordFieldReveal,
  DynamicRecordFieldUpdateInput,
  LifeRecord,
  PresignedPostUpload,
  ProtectedRecordInput,
  ProtectedRecordPayload,
  ProtectedRecordStatus,
  RecordAttachment,
  RecordAttachmentDownloadUrl,
  RecordAttachmentUploadIntent,
  RecordAttachmentUploadIntentInput,
  RecordInput,
} from '../types/record'

export const recordsApi = {
  list: (includeArchived = false) =>
    apiRequest<LifeRecord[]>(`/records${includeArchived ? '?include_archived=true' : ''}`),

  get: (id: string) => apiRequest<LifeRecord>(`/records/${id}`),

  revealProtected: (id: string) =>
    apiRequest<ProtectedRecordPayload>(`/records/${id}/protected`, {
      cache: 'no-store',
    }),

  setProtected: (id: string, input: ProtectedRecordInput) =>
    apiRequest<ProtectedRecordStatus>(`/records/${id}/protected`, {
      method: 'PUT',
      body: JSON.stringify(input),
      cache: 'no-store',
    }),

  updateProtected: (id: string, input: ProtectedRecordInput) =>
    apiRequest<ProtectedRecordStatus>(`/records/${id}/protected`, {
      method: 'PATCH',
      body: JSON.stringify(input),
      cache: 'no-store',
    }),

  clearProtected: (id: string) =>
    apiRequest<ProtectedRecordStatus>(`/records/${id}/protected`, {
      method: 'DELETE',
      cache: 'no-store',
    }),

  addField: (id: string, input: DynamicRecordFieldInput) =>
    apiRequest<LifeRecord>(`/records/${id}/fields`, {
      method: 'POST',
      body: JSON.stringify(input),
      cache: 'no-store',
    }),

  updateField: (id: string, fieldId: string, input: DynamicRecordFieldUpdateInput) =>
    apiRequest<LifeRecord>(`/records/${id}/fields/${fieldId}`, {
      method: 'PUT',
      body: JSON.stringify(input),
      cache: 'no-store',
    }),

  revealField: (id: string, fieldId: string) =>
    apiRequest<DynamicRecordFieldReveal>(`/records/${id}/fields/${fieldId}/reveal`, {
      cache: 'no-store',
    }),

  deleteField: (id: string, fieldId: string) =>
    apiRequest<LifeRecord>(`/records/${id}/fields/${fieldId}`, {
      method: 'DELETE',
      cache: 'no-store',
    }),

  listAttachments: (id: string) =>
    apiRequest<RecordAttachment[]>(`/records/${id}/attachments`, {
      cache: 'no-store',
    }),

  createAttachmentUploadIntent: (id: string, input: RecordAttachmentUploadIntentInput) =>
    apiRequest<RecordAttachmentUploadIntent>(`/records/${id}/attachments/upload-intent`, {
      method: 'POST',
      body: JSON.stringify(input),
      cache: 'no-store',
    }),

  completeAttachmentUpload: (id: string, attachmentId: string) =>
    apiRequest<RecordAttachment>(`/records/${id}/attachments/${attachmentId}/complete`, {
      method: 'POST',
      cache: 'no-store',
    }),

  createAttachmentDownloadUrl: (id: string, attachmentId: string) =>
    apiRequest<RecordAttachmentDownloadUrl>(`/records/${id}/attachments/${attachmentId}/download-url`, {
      method: 'POST',
      cache: 'no-store',
    }),

  createAttachmentPreviewUrl: (id: string, attachmentId: string) =>
    apiRequest<RecordAttachmentDownloadUrl>(`/records/${id}/attachments/${attachmentId}/preview-url`, {
      method: 'POST',
      cache: 'no-store',
    }),

  deleteAttachment: (id: string, attachmentId: string) =>
    apiRequest<void>(`/records/${id}/attachments/${attachmentId}`, {
      method: 'DELETE',
      cache: 'no-store',
    }),

  uploadAttachmentFile: async (upload: PresignedPostUpload, file: File) => {
    const formData = new FormData()
    Object.entries(upload.fields).forEach(([key, value]) => {
      formData.append(key, value)
    })
    formData.append('file', file)

    const response = await fetch(upload.url, {
      method: 'POST',
      body: formData,
      cache: 'no-store',
    })

    if (!response.ok) {
      throw new Error('Unable to upload the file. Try again with a supported PDF, JPEG, or PNG.')
    }
  },

  uploadRecordAttachment: async (id: string, file: File) => {
    const intent = await recordsApi.createAttachmentUploadIntent(id, {
      filename: file.name,
      content_type: file.type,
      size_bytes: file.size,
    })
    await recordsApi.uploadAttachmentFile(intent.upload, file)
    return recordsApi.completeAttachmentUpload(id, intent.attachment_id)
  },

  create: (input: RecordInput, idempotencyKey?: string) =>
    apiRequest<LifeRecord>('/records', {
      method: 'POST',
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
      body: JSON.stringify(input),
    }),

  update: (id: string, input: RecordInput) =>
    apiRequest<LifeRecord>(`/records/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    }),

  archive: (id: string) =>
    apiRequest<LifeRecord>(`/records/${id}/archive`, {
      method: 'POST',
    }),

  restore: (id: string) =>
    apiRequest<LifeRecord>(`/records/${id}/restore`, {
      method: 'POST',
    }),

  remove: (id: string) =>
    apiRequest<void>(`/records/${id}`, {
      method: 'DELETE',
    }),
}
