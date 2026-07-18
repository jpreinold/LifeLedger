import { ApiError } from '../api/apiClient'
import type { LinkCreateRequest } from '../types/linkedItem'
import type { ProtectedRecordInput, ProtectedRecordStatus } from '../types/record'
import { hasProtectedRecordInput } from './recordTypes'

export interface RecordSetupProgress {
  protectedSaved: boolean
  successfulFiles: Set<string>
  successfulLinks: Set<string>
}

export interface RecordSetupAttempt {
  failedFiles: string[]
  linkFailures: number
  protectedFailed: boolean
  protectedStatus: ProtectedRecordStatus | null
}

interface RecordSetupDependencies {
  saveProtected: (recordId: string, input: ProtectedRecordInput) => Promise<ProtectedRecordStatus>
  uploadFile: (recordId: string, file: File) => Promise<unknown>
  createLink: (recordId: string, link: LinkCreateRequest) => Promise<unknown>
}

export async function runRecordSetupAttempt(
  recordId: string,
  protectedInput: ProtectedRecordInput,
  files: File[],
  links: LinkCreateRequest[],
  progress: RecordSetupProgress,
  dependencies: RecordSetupDependencies,
): Promise<RecordSetupAttempt> {
  let protectedFailed = false
  let protectedStatus: ProtectedRecordStatus | null = null
  if (hasProtectedRecordInput(protectedInput) && !progress.protectedSaved) {
    try {
      protectedStatus = await dependencies.saveProtected(recordId, protectedInput)
      progress.protectedSaved = true
    } catch {
      protectedFailed = true
    }
  }

  const failedFiles: string[] = []
  for (const file of files) {
    const fileKey = getFileAttemptKey(file)
    if (progress.successfulFiles.has(fileKey)) continue
    try {
      await dependencies.uploadFile(recordId, file)
      progress.successfulFiles.add(fileKey)
    } catch {
      failedFiles.push(file.name)
    }
  }

  let linkFailures = 0
  for (const link of links) {
    const linkKey = getLinkAttemptKey(link)
    if (progress.successfulLinks.has(linkKey)) continue
    try {
      await dependencies.createLink(recordId, link)
      progress.successfulLinks.add(linkKey)
    } catch (error) {
      if (error instanceof ApiError && error.category === 'conflict') {
        progress.successfulLinks.add(linkKey)
      } else {
        linkFailures += 1
      }
    }
  }

  return { failedFiles, linkFailures, protectedFailed, protectedStatus }
}

function getFileAttemptKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`
}

function getLinkAttemptKey(link: LinkCreateRequest): string {
  return `${link.target_type}:${link.target_id}`
}
