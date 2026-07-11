export const attachmentAccept = 'application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png'
export const attachmentMaxPerRecord = 5
export const attachmentMaxSizeBytes = 10 * 1024 * 1024

const allowedAttachmentTypes = new Set(['application/pdf', 'image/jpeg', 'image/png'])
const allowedAttachmentExtensions = new Set(['.pdf', '.jpg', '.jpeg', '.png'])

export function validateAttachmentFile(file: File, currentActiveCount: number) {
  if (currentActiveCount >= attachmentMaxPerRecord) {
    return 'Records can have up to 5 active attachments.'
  }
  if (file.size <= 0) {
    return 'File must not be empty.'
  }
  if (file.size > attachmentMaxSizeBytes) {
    return 'File is larger than the 10 MB limit.'
  }
  if (!allowedAttachmentTypes.has(file.type)) {
    return 'Only PDF, JPEG, and PNG files are supported.'
  }
  const extension = getFileExtension(file.name)
  if (!allowedAttachmentExtensions.has(extension)) {
    return 'Only PDF, JPEG, and PNG files are supported.'
  }
  if (file.type === 'application/pdf' && extension !== '.pdf') {
    return 'Filename extension does not match the selected file type.'
  }
  if (file.type === 'image/png' && extension !== '.png') {
    return 'Filename extension does not match the selected file type.'
  }
  if (file.type === 'image/jpeg' && extension !== '.jpg' && extension !== '.jpeg') {
    return 'Filename extension does not match the selected file type.'
  }
  return null
}

export function formatAttachmentSize(sizeBytes: number) {
  if (sizeBytes >= 1024 * 1024) {
    return `${(sizeBytes / (1024 * 1024)).toFixed(sizeBytes >= 10 * 1024 * 1024 ? 0 : 1)} MB`
  }
  return `${Math.max(1, Math.round(sizeBytes / 1024))} KB`
}

function getFileExtension(filename: string) {
  const dotIndex = filename.lastIndexOf('.')
  return dotIndex === -1 ? '' : filename.slice(dotIndex).toLowerCase()
}
