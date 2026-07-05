import type { ReactNode } from 'react'
import SwipeableDrawer from '@mui/material/SwipeableDrawer'

interface SheetDrawerProps {
  children: ReactNode
  className: string
  isOpen: boolean
  labelledBy: string
  onClose: () => void
}

export function SheetDrawer({ children, className, isOpen, labelledBy, onClose }: SheetDrawerProps) {
  return (
    <SwipeableDrawer
      anchor="bottom"
      open={isOpen}
      onClose={onClose}
      onOpen={() => undefined}
      aria-labelledby={labelledBy}
      disableDiscovery
      disableSwipeToOpen
      keepMounted
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
    </SwipeableDrawer>
  )
}
