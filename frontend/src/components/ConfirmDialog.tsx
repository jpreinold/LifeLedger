import { useEffect, useRef } from 'react'
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

  useEffect(() => {
    if (!isOpen) {
      return undefined
    }

    cancelButtonRef.current?.focus()

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        if (!isBusy) {
          onCancel()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isBusy, isOpen, onCancel])

  if (!isOpen) {
    return null
  }

  return (
    <div
      className="confirm-dialog-backdrop"
      role="presentation"
      onMouseDown={() => {
        if (!isBusy) {
          onCancel()
        }
      }}
    >
      <section
        className="confirm-dialog"
        role="dialog"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-body"
        aria-modal="true"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="confirm-dialog-header">
          <div className="confirm-dialog-icon" aria-hidden="true">
            <Trash2 size={20} />
          </div>
          <button
            type="button"
            className="icon-button ghost-icon-button"
            onClick={onCancel}
            aria-label="Close confirmation"
            disabled={isBusy}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <h2 id="confirm-dialog-title">{title}</h2>
        <p id="confirm-dialog-body">{body}</p>
        <div className="confirm-dialog-actions">
          <button type="button" className="secondary-button" onClick={onCancel} ref={cancelButtonRef} disabled={isBusy}>
            Cancel
          </button>
          <button type="button" className="danger-button" onClick={onConfirm} disabled={isBusy}>
            {isBusy ? busyLabel : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  )
}
