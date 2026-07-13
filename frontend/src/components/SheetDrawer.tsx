import { useEffect, useRef, type MutableRefObject, type ReactNode, type Ref } from 'react'
import Drawer from '@mui/material/Drawer'
import { ArrowLeft, X } from 'lucide-react'

interface SheetDrawerProps {
  children: ReactNode
  backLabel?: string
  bodyClassName?: string
  bodyRef?: Ref<HTMLDivElement>
  className?: string
  closeLabel?: string
  footer?: ReactNode
  headerClassName?: string
  isOpen: boolean
  labelledBy: string
  onBack?: () => void
  onClose: () => void
  subtitle?: ReactNode
  title?: ReactNode
}

export function SheetDrawer({
  backLabel = 'Back',
  bodyClassName = 'sheet-body',
  bodyRef,
  children,
  className = '',
  closeLabel = 'Close',
  footer,
  headerClassName = '',
  isOpen,
  labelledBy,
  onBack,
  onClose,
  subtitle,
  title,
}: SheetDrawerProps) {
  const paperRef = useRef<HTMLDivElement | null>(null)
  const hasStructuredLayout = title !== undefined || footer !== undefined || bodyRef !== undefined || onBack !== undefined

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const frame = window.requestAnimationFrame(() => {
      const paper = paperRef.current
      if (!paper) {
        return
      }

      paper.scrollTop = 0
      paper.querySelectorAll<HTMLElement>('[data-drawer-scroll]').forEach((element) => {
        element.scrollTop = 0
      })
    })

    return () => window.cancelAnimationFrame(frame)
  }, [isOpen])

  function setBodyRef(node: HTMLDivElement | null) {
    if (!bodyRef) {
      return
    }

    if (typeof bodyRef === 'function') {
      bodyRef(node)
      return
    }

    ;(bodyRef as MutableRefObject<HTMLDivElement | null>).current = node
  }

  return (
    <Drawer
      anchor="bottom"
      open={isOpen}
      onClose={onClose}
      aria-labelledby={labelledBy}
      ModalProps={{
        keepMounted: true,
      }}
      slotProps={{
        backdrop: {
          className: 'sheet-backdrop',
        },
        paper: {
          'aria-labelledby': labelledBy,
          'aria-modal': 'true',
          className: `sheet-dialog ${className}`.trim(),
          ref: paperRef,
          role: 'dialog',
        },
      }}
    >
      {hasStructuredLayout ? (
        <>
          {title !== undefined ? (
            <div className={`sheet-header ${headerClassName}`.trim()}>
              <div className="sheet-header-title-row">
                {onBack ? (
                  <button type="button" className="icon-button ghost-icon-button" onClick={onBack} aria-label={backLabel}>
                    <ArrowLeft size={18} aria-hidden="true" />
                  </button>
                ) : null}
                <div className="sheet-title-copy">
                  <h2 id={labelledBy}>{title}</h2>
                  {subtitle ? <p>{subtitle}</p> : null}
                </div>
              </div>
              <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label={closeLabel}>
                <X size={19} aria-hidden="true" />
              </button>
            </div>
          ) : null}
          <div className={bodyClassName} data-drawer-scroll ref={setBodyRef}>
            {children}
          </div>
          {footer ? <div className="sheet-footer">{footer}</div> : null}
        </>
      ) : (
        children
      )}
    </Drawer>
  )
}
