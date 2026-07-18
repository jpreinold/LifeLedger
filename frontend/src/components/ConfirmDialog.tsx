import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Trash2, X } from 'lucide-react'

interface ConfirmDialogProps {
  body: string
  confirmLabel: string
  busyLabel?: string
  isBusy?: boolean
  isOpen: boolean
  title: string
  onCancel: () => void
  onConfirm: () => void
}

export function ConfirmDialog({
  body,
  confirmLabel,
  busyLabel = 'Deleting',
  isBusy = false,
  isOpen,
  title,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null)
  const dialogRef = useRef<HTMLElement | null>(null)
  const previousActiveElementRef = useRef<HTMLElement | null>(null)
  const wasOpenRef = useRef(false)
  const titleId = useId()
  const bodyId = useId()

  useEffect(() => {
    if (isOpen && !wasOpenRef.current) {
      wasOpenRef.current = true
      previousActiveElementRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
      window.requestAnimationFrame(() => cancelButtonRef.current?.focus())
      return
    }
    if (!isOpen && wasOpenRef.current) {
      wasOpenRef.current = false
      previousActiveElementRef.current?.focus()
      previousActiveElementRef.current = null
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return undefined

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !isBusy) {
        event.preventDefault()
        onCancel()
        return
      }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'),
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isBusy, isOpen, onCancel])

  if (!isOpen) return null

  return createPortal(
    <div
      className="confirm-dialog-backdrop"
      role="presentation"
      onMouseDown={() => {
        if (!isBusy) onCancel()
      }}
    >
      <section
        className="confirm-dialog"
        ref={dialogRef}
        role="alertdialog"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        aria-modal="true"
        aria-busy={isBusy}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="confirm-dialog-header">
          <div className="confirm-dialog-icon" aria-hidden="true">
            <Trash2 size={20} />
          </div>
          <button type="button" className="icon-button ghost-icon-button" onClick={onCancel} aria-label="Close confirmation" disabled={isBusy}>
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <h2 id={titleId}>{title}</h2>
        <p id={bodyId}>{body}</p>
        <div className="confirm-dialog-actions">
          <button type="button" className="secondary-button" onClick={onCancel} ref={cancelButtonRef} disabled={isBusy}>
            Cancel
          </button>
          <button type="button" className="danger-button" onClick={onConfirm} disabled={isBusy}>
            {isBusy ? busyLabel : confirmLabel}
          </button>
        </div>
      </section>
    </div>,
    document.body,
  )
}