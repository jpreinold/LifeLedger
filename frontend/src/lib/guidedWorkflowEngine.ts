import { ApiError } from '../api/apiClient'
import type { GuidedWorkflowDefinition, GuidedWorkflowValues } from './guidedWorkflows'
import {
  buildGuidedDynamicDetailOperations,
  buildGuidedExistingRecordInput,
  buildGuidedNewRecordInput,
  buildGuidedProtectedInput,
  buildGuidedReminderInput,
  recordInputChanged,
} from './guidedWorkflows'
import type { RelationshipType } from '../types/linkedItem'
import type {
  DynamicRecordFieldInput,
  DynamicRecordFieldUpdateInput,
  LifeRecord,
  ProtectedRecordInput,
  ProtectedRecordStatus,
  RecordAttachment,
  RecordInput,
} from '../types/record'
import type { Reminder, ReminderInput } from '../types/reminder'

export type GuidedOperation = 'item' | 'details' | 'protected' | 'responsibility' | 'relationship' | 'document'
export type GuidedOperationStatus = 'saved' | 'not_included' | 'needs_retry'

export interface GuidedWorkflowStage {
  id: GuidedOperation
  label: string
  status: GuidedOperationStatus
  detail?: string
}

export interface GuidedWorkflowProgress {
  correlationId: string
  item: LifeRecord | null
  reminder: Reminder | null
  itemSaved: boolean
  successfulDetails: Set<string>
  protectedSaved: boolean
  relationshipSaved: boolean
  documents: Map<string, RecordAttachment>
}

export interface GuidedWorkflowAttemptInput {
  workflow: GuidedWorkflowDefinition
  values: GuidedWorkflowValues
  existingItem: LifeRecord | null
  approvedUpdates: Set<string>
  document: File | null
  progress: GuidedWorkflowProgress
}

export interface GuidedWorkflowAttemptResult {
  complete: boolean
  requiredComplete: boolean
  item: LifeRecord | null
  reminder: Reminder | null
  document: RecordAttachment | null
  failedOperations: GuidedOperation[]
  stages: GuidedWorkflowStage[]
  message: string
}

export interface GuidedWorkflowDependencies {
  createItem: (input: RecordInput, idempotencyKey: string) => Promise<LifeRecord>
  updateItem: (recordId: string, input: RecordInput) => Promise<LifeRecord>
  createDetail: (recordId: string, input: DynamicRecordFieldInput) => Promise<LifeRecord>
  updateDetail: (recordId: string, fieldId: string, input: DynamicRecordFieldUpdateInput) => Promise<LifeRecord>
  saveProtected: (recordId: string, input: ProtectedRecordInput, existingItem: boolean) => Promise<ProtectedRecordStatus>
  createReminder: (input: ReminderInput, idempotencyKey: string) => Promise<Reminder>
  createRelationship: (recordId: string, reminderId: string, type: RelationshipType) => Promise<unknown>
  uploadDocument: (recordId: string, file: File, idempotencyKey: string) => Promise<RecordAttachment>
}

export function createGuidedWorkflowProgress(correlationId: string = crypto.randomUUID()): GuidedWorkflowProgress {
  return {
    correlationId,
    item: null,
    reminder: null,
    itemSaved: false,
    successfulDetails: new Set(),
    protectedSaved: false,
    relationshipSaved: false,
    documents: new Map(),
  }
}

export async function runGuidedWorkflowAttempt(
  input: GuidedWorkflowAttemptInput,
  dependencies: GuidedWorkflowDependencies,
): Promise<GuidedWorkflowAttemptResult> {
  const { approvedUpdates, document, existingItem, progress, values, workflow } = input
  const failed = new Set<GuidedOperation>()
  let item = progress.item ?? existingItem

  if (!item) {
    try {
      item = await dependencies.createItem(
        buildGuidedNewRecordInput(workflow, values),
        `${progress.correlationId}:item`,
      )
      progress.item = item
      progress.itemSaved = true
    } catch {
      failed.add('item')
      return resultForAttempt(workflow, progress, document, failed)
    }
  } else if (!progress.itemSaved) {
    const nextInput = buildGuidedExistingRecordInput(workflow, item, values, approvedUpdates)
    if (recordInputChanged(item, nextInput)) {
      try {
        item = await dependencies.updateItem(item.id, nextInput)
        progress.item = item
        progress.itemSaved = true
      } catch {
        failed.add('item')
      }
    } else {
      progress.item = item
      progress.itemSaved = true
    }
  }

  const itemForChildren = progress.item ?? item
  if (!itemForChildren) {
    failed.add('item')
    return resultForAttempt(workflow, progress, document, failed)
  }

  const detailOperations = buildGuidedDynamicDetailOperations(
    workflow,
    values,
    itemForChildren,
    approvedUpdates,
  )
  for (const operation of detailOperations) {
    const operationKey = `${operation.fieldDefinition.id}:${operation.existingField?.field_id ?? 'new'}`
    if (progress.successfulDetails.has(operationKey)) continue
    try {
      const updated = operation.existingField && operation.updateInput
        ? await dependencies.updateDetail(itemForChildren.id, operation.existingField.field_id, operation.updateInput)
        : operation.createInput
          ? await dependencies.createDetail(itemForChildren.id, operation.createInput)
          : null
      if (updated) {
        progress.item = updated
        item = updated
      }
      progress.successfulDetails.add(operationKey)
    } catch (error) {
      if (error instanceof ApiError && error.category === 'conflict') {
        progress.successfulDetails.add(operationKey)
      } else {
        failed.add('details')
      }
    }
  }

  const protectedInput = buildGuidedProtectedInput(workflow, values)
  const hasProtectedInput = Object.values(protectedInput).some((value) => Boolean(value?.trim()))
  if (hasProtectedInput && !progress.protectedSaved) {
    try {
      const status = await dependencies.saveProtected(itemForChildren.id, protectedInput, Boolean(existingItem))
      progress.protectedSaved = true
      progress.item = withProtectedStatus(progress.item ?? itemForChildren, status)
      item = progress.item
    } catch {
      failed.add('protected')
    }
  }

  if (!progress.reminder) {
    try {
      progress.reminder = await dependencies.createReminder(
        buildGuidedReminderInput(workflow, values, itemForChildren.title),
        `${progress.correlationId}:responsibility`,
      )
    } catch {
      failed.add('responsibility')
    }
  }

  if (progress.reminder && !progress.relationshipSaved) {
    try {
      await dependencies.createRelationship(
        itemForChildren.id,
        progress.reminder.id,
        workflow.relationshipDefaults.type,
      )
      progress.relationshipSaved = true
    } catch (error) {
      if (error instanceof ApiError && error.category === 'conflict') {
        progress.relationshipSaved = true
      } else {
        failed.add('relationship')
      }
    }
  }

  if (document) {
    const documentKey = getDocumentKey(document)
    if (!progress.documents.has(documentKey)) {
      try {
        const uploaded = await dependencies.uploadDocument(
          itemForChildren.id,
          document,
          `${progress.correlationId}:document`,
        )
        progress.documents.set(documentKey, uploaded)
      } catch {
        failed.add('document')
      }
    }
  }

  return resultForAttempt(workflow, progress, document, failed)
}

function resultForAttempt(
  workflow: GuidedWorkflowDefinition,
  progress: GuidedWorkflowProgress,
  document: File | null,
  failed: Set<GuidedOperation>,
): GuidedWorkflowAttemptResult {
  const requiredComplete = Boolean(progress.item && progress.reminder && progress.relationshipSaved)
    && !failed.has('item')
    && !failed.has('details')
    && !failed.has('protected')
    && !failed.has('responsibility')
    && !failed.has('relationship')
  const uploadedDocument = document ? progress.documents.get(getDocumentKey(document)) ?? null : null
  const documentComplete = !document || Boolean(uploadedDocument)
  const complete = requiredComplete && documentComplete
  const failedOperations = [...failed]
  const itemTitle = progress.item?.title || 'The item'
  const message = complete
    ? `${workflow.completionPresentation.title}. ${scheduleCompletionCopy(progress)}`
    : requiredComplete
      ? `${itemTitle} and its responsibility were saved, but the document upload did not finish.`
      : `${itemTitle} is available, but some guided setup still needs attention.`

  return {
    complete,
    requiredComplete,
    item: progress.item,
    reminder: progress.reminder,
    document: uploadedDocument,
    failedOperations,
    stages: [
      stage('item', 'Item', progress.itemSaved && Boolean(progress.item), failed.has('item')),
      stage('details', 'Details', true, failed.has('details')),
      stage('protected', 'Protected details', progress.protectedSaved, failed.has('protected'), workflow.fields.some((item) => item.protected)),
      stage('responsibility', 'Responsibility', Boolean(progress.reminder), failed.has('responsibility')),
      stage('relationship', 'Item connection', progress.relationshipSaved, failed.has('relationship')),
      stage('document', 'Document', Boolean(uploadedDocument), failed.has('document'), Boolean(document)),
    ],
    message,
  }
}

function stage(
  id: GuidedOperation,
  label: string,
  saved: boolean,
  failed: boolean,
  included = true,
): GuidedWorkflowStage {
  return {
    id,
    label,
    status: !included ? 'not_included' : saved && !failed ? 'saved' : failed ? 'needs_retry' : 'not_included',
  }
}

function scheduleCompletionCopy(progress: GuidedWorkflowProgress) {
  if (!progress.reminder) return ''
  const document = [...progress.documents.values()][0]
  const documentCopy = document
    ? document.status === 'available'
      ? 'The document is available.'
      : 'The document is being scanned and will appear when ready.'
    : ''
  return [`LifeLedger will remind you before ${progress.reminder.due_date}.`, documentCopy].filter(Boolean).join(' ')
}

function withProtectedStatus(record: LifeRecord, status: ProtectedRecordStatus): LifeRecord {
  return {
    ...record,
    has_protected_data: status.has_protected_data,
    protected_field_names: status.protected_field_names,
  }
}

function getDocumentKey(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`
}
