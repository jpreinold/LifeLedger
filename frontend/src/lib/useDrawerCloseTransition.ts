import { useCallback, useEffect, useRef, useState } from 'react'

const defaultDrawerCloseMs = 220

export function useDrawerCloseTransition({
  delayMs = defaultDrawerCloseMs,
  isOpen,
  onClose,
}: {
  delayMs?: number
  isOpen: boolean
  onClose: () => void
}) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const isClosingRef = useRef(false)
  const closeTimerRef = useRef<number | null>(null)

  const closeWithAction = useCallback((action: () => void) => {
    if (isClosingRef.current) {
      return
    }

    isClosingRef.current = true
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      action()
    }, delayMs)
  }, [delayMs])

  const requestClose = useCallback(() => {
    closeWithAction(onClose)
  }, [closeWithAction, onClose])

  useEffect(() => {
    if (isOpen) {
      isClosingRef.current = false
      setIsDrawerOpen(true)
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        requestClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, requestClose])

  useEffect(() => {
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current)
      }
    }
  }, [])

  return {
    closeWithAction,
    isDrawerOpen,
    requestClose,
  }
}
