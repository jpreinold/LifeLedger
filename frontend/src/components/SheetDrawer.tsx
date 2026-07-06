import { useEffect, useRef, type ReactNode } from 'react'
import Drawer from '@mui/material/Drawer'

interface SheetDrawerProps {
  children: ReactNode
  className: string
  isOpen: boolean
  labelledBy: string
  onClose: () => void
}

export function SheetDrawer({ children, className, isOpen, labelledBy, onClose }: SheetDrawerProps) {
  const paperRef = useRef<HTMLDivElement | null>(null)

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
      paper.querySelectorAll<HTMLElement>('*').forEach((element) => {
        element.scrollTop = 0
      })
    })

    return () => window.cancelAnimationFrame(frame)
  }, [isOpen])

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
          className: `sheet-dialog ${className}`,
          ref: paperRef,
          role: 'dialog',
        },
      }}
    >
      {children}
    </Drawer>
  )
}
