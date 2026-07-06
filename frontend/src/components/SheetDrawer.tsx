import type { ReactNode } from 'react'
import Drawer from '@mui/material/Drawer'

interface SheetDrawerProps {
  children: ReactNode
  className: string
  isOpen: boolean
  labelledBy: string
  onClose: () => void
}

export function SheetDrawer({ children, className, isOpen, labelledBy, onClose }: SheetDrawerProps) {
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
          role: 'dialog',
        },
      }}
    >
      {children}
    </Drawer>
  )
}
