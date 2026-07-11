import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  FileText,
  FileUp,
  Maximize2,
  RotateCcw,
  ShieldCheck,
  Trash2,
  TriangleAlert,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'

import { recordsApi } from '../api/recordsApi'
import {
  attachmentAccept,
  attachmentMaxPerRecord,
  formatAttachmentSize,
  validateAttachmentFile,
} from '../lib/attachmentFiles'
import { createPdfPageRenderTask, loadPdfDocument, type PdfDocument, type PdfRenderTask } from '../lib/pdfPreview'
import type { RecordAttachment } from '../types/record'
import { ConfirmDialog } from './ConfirmDialog'

interface RecordDocumentsPanelProps {
  isActive: boolean
  mode?: 'detail' | 'edit'
  recordId: string
}

const attachmentPollMs = 4_000
const minViewerZoom = 0.75
const maxViewerZoom = 2.5
const viewerZoomStep = 0.25

export function RecordDocumentsPanel({ isActive, mode = 'detail', recordId }: RecordDocumentsPanelProps) {
  const [attachments, setAttachments] = useState<RecordAttachment[]>([])
  const [isAttachmentsLoading, setIsAttachmentsLoading] = useState(false)
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false)
  const [isDeletingAttachment, setIsDeletingAttachment] = useState(false)
  const [attachmentError, setAttachmentError] = useState<string | null>(null)
  const [attachmentMessage, setAttachmentMessage] = useState<string | null>(null)
  const [pendingAttachmentDelete, setPendingAttachmentDelete] = useState<RecordAttachment | null>(null)
  const [previewAttachment, setPreviewAttachment] = useState<RecordAttachment | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [thumbnailUrls, setThumbnailUrls] = useState<Record<string, string>>({})
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const previewRequestRef = useRef(0)

  const visibleAttachments = useMemo(
    () => attachments.filter((attachment) => attachment.status !== 'deleted'),
    [attachments],
  )
  const activeCount = activeAttachmentCount(visibleAttachments)
  const canAddAttachment = activeCount < attachmentMaxPerRecord && !isUploadingAttachment

  const clearPreviewState = useCallback(() => {
    previewRequestRef.current += 1
    setPreviewAttachment(null)
    setPreviewUrl(null)
    setIsPreviewLoading(false)
    setPreviewError(null)
  }, [])

  const clearTransientDocumentState = useCallback(() => {
    clearPreviewState()
    setAttachmentError(null)
    setAttachmentMessage(null)
    setPendingAttachmentDelete(null)
    setThumbnailUrls({})
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [clearPreviewState])

  const loadAttachments = useCallback(
    async (options: { quiet?: boolean } = {}) => {
      if (!options.quiet) {
        setIsAttachmentsLoading(true)
      }
      try {
        const nextAttachments = await recordsApi.listAttachments(recordId)
        setAttachments(nextAttachments)
      } catch (requestError) {
        setAttachmentError(requestError instanceof Error ? requestError.message : 'Unable to load documents.')
      } finally {
        if (!options.quiet) {
          setIsAttachmentsLoading(false)
        }
      }
    },
    [recordId],
  )

  useEffect(() => {
    setAttachments([])
    clearTransientDocumentState()
    void loadAttachments()
  }, [clearTransientDocumentState, loadAttachments, recordId])

  useEffect(() => {
    return () => {
      previewRequestRef.current += 1
    }
  }, [])

  useEffect(() => {
    function handleVisibilityChange() {
      if (document.visibilityState === 'hidden') {
        clearTransientDocumentState()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [clearTransientDocumentState])

  useEffect(() => {
    if (!isActive || !visibleAttachments.some((attachment) => isAttachmentPendingScan(attachment))) {
      return undefined
    }

    const pollId = window.setInterval(() => {
      void loadAttachments({ quiet: true })
    }, attachmentPollMs)

    return () => window.clearInterval(pollId)
  }, [isActive, loadAttachments, visibleAttachments])

  useEffect(() => {
    setThumbnailUrls((current) => {
      const validIds = new Set(
        visibleAttachments
          .filter((attachment) => attachment.status === 'available')
          .map((attachment) => attachment.attachment_id),
      )
      const nextEntries = Object.entries(current).filter(([attachmentId]) => validIds.has(attachmentId))

      if (nextEntries.length === Object.keys(current).length) {
        return current
      }

      return Object.fromEntries(nextEntries)
    })
  }, [visibleAttachments])

  useEffect(() => {
    if (!isActive) {
      return undefined
    }

    let isCancelled = false
    const attachmentsNeedingUrls = visibleAttachments.filter(
      (attachment) =>
        attachment.status === 'available' &&
        isPreviewableAttachment(attachment) &&
        !thumbnailUrls[attachment.attachment_id],
    )

    for (const attachment of attachmentsNeedingUrls) {
      void recordsApi.createAttachmentPreviewUrl(recordId, attachment.attachment_id)
        .then((preview) => {
          if (!isCancelled) {
            setThumbnailUrls((current) => ({ ...current, [attachment.attachment_id]: preview.url }))
          }
        })
        .catch(() => {
          // Thumbnail URLs are a convenience; opening the viewer still reports preview errors.
        })
    }

    return () => {
      isCancelled = true
    }
  }, [isActive, recordId, thumbnailUrls, visibleAttachments])

  function handleChooseAttachment() {
    setAttachmentError(null)
    setAttachmentMessage(null)
    fileInputRef.current?.click()
  }

  async function handleAttachmentFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0] ?? null
    event.currentTarget.value = ''
    if (!file) {
      return
    }

    const validationError = validateAttachmentFile(file, activeCount)
    if (validationError) {
      setAttachmentError(validationError)
      setAttachmentMessage(null)
      return
    }

    setIsUploadingAttachment(true)
    setAttachmentError(null)
    setAttachmentMessage(null)

    try {
      const intent = await recordsApi.createAttachmentUploadIntent(recordId, {
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      })
      await recordsApi.uploadAttachmentFile(intent.upload, file)
      const completed = await recordsApi.completeAttachmentUpload(recordId, intent.attachment_id)
      setAttachments((current) => upsertAttachment(current, completed))
      setAttachmentMessage('Document uploaded. Security scan in progress.')
      void loadAttachments({ quiet: true })
    } catch (requestError) {
      setAttachmentError(requestError instanceof Error ? requestError.message : 'Unable to upload document.')
    } finally {
      setIsUploadingAttachment(false)
    }
  }

  async function handleDownloadAttachment(attachment: RecordAttachment) {
    if (attachment.status !== 'available') {
      return
    }

    setAttachmentError(null)
    setAttachmentMessage(null)
    try {
      const download = await recordsApi.createAttachmentDownloadUrl(recordId, attachment.attachment_id)
      window.location.assign(download.url)
    } catch (requestError) {
      setAttachmentError(requestError instanceof Error ? requestError.message : 'Unable to download document.')
    }
  }

  async function handlePreviewAttachment(attachment: RecordAttachment) {
    if (attachment.status !== 'available') {
      return
    }

    const requestId = previewRequestRef.current + 1
    previewRequestRef.current = requestId
    setPreviewAttachment(attachment)
    setPreviewUrl(null)
    setPreviewError(null)
    setIsPreviewLoading(true)
    setAttachmentError(null)
    setAttachmentMessage(null)

    try {
      const preview = await recordsApi.createAttachmentPreviewUrl(recordId, attachment.attachment_id)
      if (previewRequestRef.current === requestId) {
        setPreviewUrl(preview.url)
      }
    } catch (requestError) {
      if (previewRequestRef.current === requestId) {
        setPreviewError(requestError instanceof Error ? requestError.message : 'Unable to preview document.')
      }
    } finally {
      if (previewRequestRef.current === requestId) {
        setIsPreviewLoading(false)
      }
    }
  }

  async function confirmDeleteAttachment() {
    if (!pendingAttachmentDelete) {
      return
    }

    const attachmentToDelete = pendingAttachmentDelete
    setIsDeletingAttachment(true)
    setAttachmentError(null)
    setAttachmentMessage(null)

    try {
      await recordsApi.deleteAttachment(recordId, attachmentToDelete.attachment_id)
      setAttachments((current) => current.filter((attachment) => attachment.attachment_id !== attachmentToDelete.attachment_id))
      setThumbnailUrls((current) => {
        const next = { ...current }
        delete next[attachmentToDelete.attachment_id]
        return next
      })
      if (previewAttachment?.attachment_id === attachmentToDelete.attachment_id) {
        clearPreviewState()
      }
      setPendingAttachmentDelete(null)
      setAttachmentMessage('Document deleted.')
    } catch (requestError) {
      setAttachmentError(requestError instanceof Error ? requestError.message : 'Unable to delete document.')
    } finally {
      setIsDeletingAttachment(false)
    }
  }

  return (
    <>
      <section className={`documents-panel documents-panel-${mode}`} aria-label="Documents">
        <div className="documents-panel-header">
          <div className="documents-title-lockup">
            <span className="documents-title-icon" aria-hidden="true">
              <ShieldCheck size={18} />
            </span>
            <div>
              <h3>Documents</h3>
              <p>Files are encrypted in storage and scanned before they become available.</p>
            </div>
          </div>
          <button type="button" className="primary-button documents-add-button" disabled={!canAddAttachment} onClick={handleChooseAttachment}>
            <FileUp size={16} aria-hidden="true" />
            {isUploadingAttachment ? 'Uploading...' : 'Add document'}
          </button>
        </div>

        <div className="documents-meta-strip" aria-label="Document attachment limits">
          <span>{activeCount} of {attachmentMaxPerRecord}</span>
          <span>PDF, JPEG, PNG</span>
          <span>10 MB max</span>
        </div>

        {attachmentError ? (
          <p className="field-error document-inline-message" role="alert">
            <AlertCircle size={14} aria-hidden="true" />
            {attachmentError}
          </p>
        ) : null}
        {attachmentMessage ? (
          <p className="document-inline-message document-inline-message-success" role="status">
            <CheckCircle2 size={14} aria-hidden="true" />
            {attachmentMessage}
          </p>
        ) : null}

        {isAttachmentsLoading ? <DocumentSkeletonGrid /> : null}

        {!isAttachmentsLoading && visibleAttachments.length === 0 ? (
          <div className="documents-empty-state">
            <FileUp size={28} aria-hidden="true" />
            <div>
              <strong>No documents yet</strong>
              <p>Add a scanned PDF, JPEG, or PNG after this record exists.</p>
            </div>
            <button type="button" className="secondary-button" disabled={!canAddAttachment} onClick={handleChooseAttachment}>
              <FileUp size={16} aria-hidden="true" />
              Add document
            </button>
          </div>
        ) : null}

        {!isAttachmentsLoading && visibleAttachments.length > 0 ? (
          <div className="documents-grid" aria-label="Document list">
            {visibleAttachments.map((attachment) => (
              <DocumentCard
                attachment={attachment}
                isPanelActive={isActive}
                key={attachment.attachment_id}
                thumbnailUrl={thumbnailUrls[attachment.attachment_id] ?? null}
                onDelete={() => setPendingAttachmentDelete(attachment)}
                onDownload={() => void handleDownloadAttachment(attachment)}
                onPreview={() => void handlePreviewAttachment(attachment)}
                onRetry={handleChooseAttachment}
              />
            ))}
          </div>
        ) : null}
      </section>

      <input
        type="file"
        accept={attachmentAccept}
        className="attachment-file-input"
        ref={fileInputRef}
        onChange={(event) => void handleAttachmentFileChange(event)}
      />

      <ConfirmDialog
        body={pendingAttachmentDelete ? `Delete ${pendingAttachmentDelete.display_name}? This removes the stored file.` : ''}
        confirmLabel="Delete document"
        isBusy={isDeletingAttachment}
        isOpen={pendingAttachmentDelete !== null}
        title="Delete document?"
        onCancel={() => setPendingAttachmentDelete(null)}
        onConfirm={() => void confirmDeleteAttachment()}
      />

      <AttachmentPreviewOverlay
        attachment={previewAttachment}
        error={previewError}
        isLoading={isPreviewLoading}
        url={previewUrl}
        onClose={clearPreviewState}
        onDownload={(attachment) => void handleDownloadAttachment(attachment)}
      />
    </>
  )
}

function DocumentCard({
  attachment,
  isPanelActive,
  onDelete,
  onDownload,
  onPreview,
  onRetry,
  thumbnailUrl,
}: {
  attachment: RecordAttachment
  isPanelActive: boolean
  onDelete: () => void
  onDownload: () => void
  onPreview: () => void
  onRetry: () => void
  thumbnailUrl: string | null
}) {
  const isAvailable = attachment.status === 'available'
  const isFailed = attachment.status === 'rejected' || attachment.status === 'scan_failed'
  const statusMeta = getAttachmentStatusMeta(attachment)
  const StatusIcon = statusMeta.icon
  const dateLabel = formatAttachmentDate(attachment.available_at ?? attachment.uploaded_at ?? attachment.created_at)

  return (
    <article className={`document-card ${isFailed ? 'document-card-warning' : ''}`.trim()}>
      <button
        type="button"
        className="document-card-open"
        disabled={!isAvailable}
        onClick={onPreview}
        aria-label={
          isAvailable
            ? `Open secure preview for ${attachment.display_name}`
            : `${attachment.display_name} is ${statusMeta.label.toLowerCase()} and cannot be previewed`
        }
      >
        <DocumentThumbnail attachment={attachment} isPanelActive={isPanelActive} thumbnailUrl={thumbnailUrl} />
        <span className="document-card-copy">
          <strong>{attachment.display_name}</strong>
          <span>{formatAttachmentSize(attachment.size_bytes)} - {dateLabel}</span>
          <small className={statusMeta.className}>
            <StatusIcon size={13} aria-hidden="true" />
            {statusMeta.label}
          </small>
        </span>
        {isAvailable ? (
          <span className="document-preview-cue" aria-hidden="true">
            <Maximize2 size={14} />
          </span>
        ) : null}
      </button>

      <div className="document-card-actions" aria-label={`Actions for ${attachment.display_name}`}>
        {isAvailable ? (
          <button type="button" className="icon-button document-action-button" onClick={onDownload} aria-label={`Download ${attachment.display_name}`}>
            <Download size={17} aria-hidden="true" />
          </button>
        ) : null}
        {isFailed ? (
          <button type="button" className="icon-button document-action-button" onClick={onRetry} aria-label="Retry with another file">
            <FileUp size={17} aria-hidden="true" />
          </button>
        ) : null}
        <button type="button" className="icon-button document-action-button document-delete-button" onClick={onDelete} aria-label={`Delete ${attachment.display_name}`}>
          <Trash2 size={16} aria-hidden="true" />
        </button>
      </div>
    </article>
  )
}

function DocumentThumbnail({
  attachment,
  isPanelActive,
  thumbnailUrl,
}: {
  attachment: RecordAttachment
  isPanelActive: boolean
  thumbnailUrl: string | null
}) {
  const isAvailable = attachment.status === 'available'
  const isImage = attachment.content_type.startsWith('image/')
  const isPdf = attachment.content_type === 'application/pdf'
  const isFailed = attachment.status === 'rejected' || attachment.status === 'scan_failed'

  if (isAvailable && thumbnailUrl && isImage) {
    return (
      <span className="document-thumbnail document-thumbnail-image">
        <img src={thumbnailUrl} alt="" referrerPolicy="no-referrer" />
      </span>
    )
  }

  if (isAvailable && thumbnailUrl && isPdf) {
    return (
      <span className="document-thumbnail document-thumbnail-pdf">
        <PdfThumbnailCanvas isActive={isPanelActive} url={thumbnailUrl} />
        <span className="document-file-type-pill">PDF</span>
      </span>
    )
  }

  if (isAvailable && !thumbnailUrl) {
    return <span className="document-thumbnail document-thumbnail-loading" aria-hidden="true" />
  }

  if (isFailed) {
    return (
      <span className="document-thumbnail document-thumbnail-failed" aria-hidden="true">
        <TriangleAlert size={22} />
      </span>
    )
  }

  return (
    <span className="document-thumbnail document-thumbnail-muted" aria-hidden="true">
      <FileText size={22} />
    </span>
  )
}

function PdfThumbnailCanvas({ isActive, url }: { isActive: boolean; url: string }) {
  const [containerRef, width] = useElementWidth<HTMLSpanElement>()
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [renderState, setRenderState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')

  useEffect(() => {
    if (!isActive || width <= 0) {
      return undefined
    }

    const canvas = canvasRef.current
    if (!canvas) {
      return undefined
    }
    const targetCanvas = canvas

    let isCancelled = false
    let renderTask: PdfRenderTask | null = null
    let pdfDocument: PdfDocument | null = null

    async function renderThumbnail() {
      setRenderState('loading')
      pdfDocument = await loadPdfDocument(url)
      if (isCancelled) {
        await pdfDocument.destroy()
        return
      }
      renderTask = await createPdfPageRenderTask({
        canvas: targetCanvas,
        document: pdfDocument,
        pageNumber: 1,
        targetWidth: width,
      })
      if (isCancelled) {
        renderTask.cancel()
        return
      }
      await renderTask.promise

      if (!isCancelled) {
        setRenderState('ready')
      }
    }

    void renderThumbnail().catch((renderError) => {
      if (!isCancelled && !isPdfRenderCancelled(renderError)) {
        setRenderState('error')
      }
    })

    return () => {
      isCancelled = true
      renderTask?.cancel()
      if (pdfDocument) {
        void pdfDocument.destroy().catch(() => undefined)
      }
    }
  }, [isActive, url, width])

  return (
    <span className={`document-pdf-thumbnail-canvas document-pdf-thumbnail-${renderState}`} ref={containerRef}>
      {renderState !== 'ready' ? <span className="document-thumbnail-skeleton" aria-hidden="true" /> : null}
      {renderState === 'error' ? <FileText size={22} aria-hidden="true" /> : null}
      <canvas ref={canvasRef} aria-hidden="true" />
    </span>
  )
}

function AttachmentPreviewOverlay({
  attachment,
  error,
  isLoading,
  onClose,
  onDownload,
  url,
}: {
  attachment: RecordAttachment | null
  error: string | null
  isLoading: boolean
  onClose: () => void
  onDownload: (attachment: RecordAttachment) => void
  url: string | null
}) {
  const [pageCount, setPageCount] = useState<number | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [zoom, setZoom] = useState(1)
  const handlePdfPageCount = useCallback((count: number) => {
    setPageCount(count)
    setPageNumber((current) => Math.min(current, count))
  }, [])

  useEffect(() => {
    setPageCount(null)
    setPageNumber(1)
    setZoom(1)
  }, [attachment?.attachment_id, url])

  if (!attachment) {
    return null
  }

  const isPdf = attachment.content_type === 'application/pdf'
  const canGoPrevious = isPdf && pageNumber > 1
  const canGoNext = isPdf && pageCount !== null && pageNumber < pageCount

  return (
    <div className="attachment-preview-backdrop" role="dialog" aria-modal="true" aria-label={`Preview ${attachment.display_name}`}>
      <div className="attachment-preview-shell">
        <header className="attachment-preview-header">
          <div>
            <h3>{attachment.display_name}</h3>
            <p>{isPdf && pageCount ? `Page ${pageNumber} of ${pageCount}` : formatAttachmentSize(attachment.size_bytes)}</p>
          </div>
          <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close document preview">
            <X size={20} aria-hidden="true" />
          </button>
        </header>

        <div className="attachment-preview-toolbar" aria-label="Document preview controls">
          {isPdf ? (
            <div className="attachment-page-controls" aria-label="PDF page controls">
              <button type="button" className="icon-button attachment-preview-tool-button" disabled={!canGoPrevious} onClick={() => setPageNumber((current) => Math.max(1, current - 1))} aria-label="Previous page">
                <ChevronLeft size={18} aria-hidden="true" />
              </button>
              <span>{pageNumber} of {pageCount ?? '-'}</span>
              <button type="button" className="icon-button attachment-preview-tool-button" disabled={!canGoNext} onClick={() => setPageNumber((current) => Math.min(pageCount ?? current, current + 1))} aria-label="Next page">
                <ChevronRight size={18} aria-hidden="true" />
              </button>
            </div>
          ) : null}
          <div className="attachment-zoom-controls" aria-label="Preview zoom controls">
            <button type="button" className="icon-button attachment-preview-tool-button" disabled={zoom <= minViewerZoom} onClick={() => setZoom((current) => Math.max(minViewerZoom, current - viewerZoomStep))} aria-label="Zoom out">
              <ZoomOut size={17} aria-hidden="true" />
            </button>
            <button type="button" className="icon-button attachment-preview-tool-button" onClick={() => setZoom(1)} aria-label="Fit width">
              <RotateCcw size={17} aria-hidden="true" />
            </button>
            <button type="button" className="icon-button attachment-preview-tool-button" disabled={zoom >= maxViewerZoom} onClick={() => setZoom((current) => Math.min(maxViewerZoom, current + viewerZoomStep))} aria-label="Zoom in">
              <ZoomIn size={17} aria-hidden="true" />
            </button>
            <button type="button" className="icon-button attachment-preview-tool-button" onClick={() => onDownload(attachment)} aria-label={`Download ${attachment.display_name}`}>
              <Download size={17} aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="attachment-preview-stage">
          {isLoading ? <p className="attachment-preview-state">Loading preview...</p> : null}
          {!isLoading && error ? <p className="field-error attachment-preview-state">{error}</p> : null}
          {!isLoading && !error && url && isPdf ? (
            <PdfPreviewCanvas
              pageNumber={pageNumber}
              url={url}
              zoom={zoom}
              onPageCount={handlePdfPageCount}
            />
          ) : null}
          {!isLoading && !error && url && !isPdf ? <ImagePreviewStage url={url} zoom={zoom} /> : null}
        </div>
      </div>
    </div>
  )
}

function PdfPreviewCanvas({
  onPageCount,
  pageNumber,
  url,
  zoom,
}: {
  onPageCount: (count: number) => void
  pageNumber: number
  url: string
  zoom: number
}) {
  const [stageRef, width] = useElementWidth<HTMLDivElement>()
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [pdfDocument, setPdfDocument] = useState<PdfDocument | null>(null)
  const [renderError, setRenderError] = useState<string | null>(null)
  const [isRendering, setIsRendering] = useState(true)

  useEffect(() => {
    let isCancelled = false
    let loadedDocument: PdfDocument | null = null

    setPdfDocument(null)
    setRenderError(null)
    setIsRendering(true)

    async function loadDocument() {
      loadedDocument = await loadPdfDocument(url)
      if (isCancelled) {
        await loadedDocument.destroy()
        return
      }
      setPdfDocument(loadedDocument)
      onPageCount(loadedDocument.numPages)
    }

    void loadDocument().catch((loadError) => {
      if (!isCancelled) {
        setRenderError(loadError instanceof Error ? loadError.message : 'Unable to load the PDF preview.')
        setIsRendering(false)
      }
    })

    return () => {
      isCancelled = true
      if (loadedDocument) {
        void loadedDocument.destroy().catch(() => undefined)
      }
    }
  }, [onPageCount, url])

  useEffect(() => {
    if (!pdfDocument || width <= 0) {
      return undefined
    }

    const canvas = canvasRef.current
    if (!canvas) {
      return undefined
    }
    const targetCanvas = canvas
    const targetDocument = pdfDocument

    let isCancelled = false
    let renderTask: PdfRenderTask | null = null

    async function renderPage() {
      setIsRendering(true)
      setRenderError(null)
      renderTask = await createPdfPageRenderTask({
        canvas: targetCanvas,
        document: targetDocument,
        pageNumber,
        targetWidth: width,
        zoom,
      })
      if (isCancelled) {
        renderTask.cancel()
        return
      }
      await renderTask.promise

      if (!isCancelled) {
        setIsRendering(false)
      }
    }

    void renderPage().catch((renderFailure) => {
      if (!isCancelled && !isPdfRenderCancelled(renderFailure)) {
        setRenderError(renderFailure instanceof Error ? renderFailure.message : 'Unable to render the PDF page.')
        setIsRendering(false)
      }
    })

    return () => {
      isCancelled = true
      renderTask?.cancel()
    }
  }, [pageNumber, pdfDocument, width, zoom])

  return (
    <div className="attachment-pdf-viewer" ref={stageRef}>
      {isRendering && !renderError ? <p className="attachment-preview-state attachment-render-state">Rendering page...</p> : null}
      {renderError ? <p className="field-error attachment-preview-state">{renderError}</p> : null}
      <canvas className="attachment-pdf-canvas" ref={canvasRef} aria-label={`PDF page ${pageNumber}`} />
    </div>
  )
}

function ImagePreviewStage({ url, zoom }: { url: string; zoom: number }) {
  return (
    <div className="attachment-image-viewer">
      <img
        className="attachment-preview-image"
        src={url}
        alt=""
        referrerPolicy="no-referrer"
        style={{ transform: `scale(${zoom})` }}
      />
    </div>
  )
}

function DocumentSkeletonGrid() {
  return (
    <div className="documents-grid" aria-label="Loading documents">
      <div className="document-card document-card-skeleton" />
      <div className="document-card document-card-skeleton" />
    </div>
  )
}

function useElementWidth<T extends HTMLElement>() {
  const elementRef = useRef<T | null>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const element = elementRef.current
    if (!element) {
      return undefined
    }
    const observedElement = element

    function updateWidth() {
      setWidth(Math.floor(observedElement.clientWidth))
    }

    updateWidth()
    const observer = new ResizeObserver(updateWidth)
    observer.observe(observedElement)
    return () => observer.disconnect()
  }, [])

  return [elementRef, width] as const
}

function activeAttachmentCount(attachments: RecordAttachment[]) {
  return attachments.filter((attachment) => ['pending_upload', 'uploaded', 'scanning', 'available'].includes(attachment.status)).length
}

function upsertAttachment(attachments: RecordAttachment[], nextAttachment: RecordAttachment) {
  const exists = attachments.some((attachment) => attachment.attachment_id === nextAttachment.attachment_id)
  if (exists) {
    return attachments.map((attachment) => (attachment.attachment_id === nextAttachment.attachment_id ? nextAttachment : attachment))
  }
  return [...attachments, nextAttachment]
}

function isAttachmentPendingScan(attachment: RecordAttachment) {
  return attachment.status === 'uploaded' || attachment.status === 'scanning'
}

function isPreviewableAttachment(attachment: RecordAttachment) {
  return attachment.content_type === 'application/pdf' || attachment.content_type.startsWith('image/')
}

function getAttachmentStatusMeta(attachment: RecordAttachment) {
  if (attachment.status === 'available') {
    return {
      className: 'document-status document-status-available',
      icon: CheckCircle2,
      label: 'Security scanned',
    }
  }
  if (attachment.status === 'rejected') {
    return {
      className: 'document-status document-status-failed',
      icon: TriangleAlert,
      label: attachment.scan_result === 'threats_found' ? 'Rejected' : 'Not accepted',
    }
  }
  if (attachment.status === 'scan_failed') {
    return {
      className: 'document-status document-status-failed',
      icon: TriangleAlert,
      label: 'Scan failed',
    }
  }
  if (attachment.status === 'pending_upload') {
    return {
      className: 'document-status document-status-scanning',
      icon: Clock3,
      label: 'Waiting for upload',
    }
  }
  if (attachment.status === 'deleting') {
    return {
      className: 'document-status document-status-scanning',
      icon: Clock3,
      label: 'Deleting',
    }
  }

  return {
    className: 'document-status document-status-scanning',
    icon: Clock3,
    label: 'Scanning',
  }
}

function formatAttachmentDate(value: string | null) {
  if (!value) {
    return 'Date unknown'
  }
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}

function isPdfRenderCancelled(error: unknown) {
  return error instanceof Error && (error.name === 'RenderingCancelledException' || error.message.toLowerCase().includes('cancelled'))
}




