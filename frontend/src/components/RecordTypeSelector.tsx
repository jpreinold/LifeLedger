import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronRight, X } from 'lucide-react'

import { recordTypeOptions } from '../lib/recordTypes'
import type { RecordType } from '../types/record'
import { SheetDrawer } from './SheetDrawer'

interface RecordTypeSelectorProps {
  isOpen: boolean
  onChoose: (type: RecordType) => void
  onClose: () => void
}

const drawerCloseMs = 220

export function RecordTypeSelector({ isOpen, onChoose, onClose }: RecordTypeSelectorProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const isClosingRef = useRef(false)
  const closeTimerRef = useRef<number | null>(null)

  const requestClose = useCallback(() => {
    if (isClosingRef.current) {
      return
    }

    isClosingRef.current = true
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onClose()
    }, drawerCloseMs)
  }, [onClose])

  const closeWithType = useCallback((type: RecordType) => {
    if (isClosingRef.current) {
      return
    }

    isClosingRef.current = true
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      onChoose(type)
    }, drawerCloseMs)
  }, [onChoose])

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

  return (
    <SheetDrawer
      className="record-type-dialog"
      isOpen={isOpen && isDrawerOpen}
      labelledBy="record-type-heading"
      onClose={requestClose}
    >
      <div className="sheet-header">
        <div>
          <h2 id="record-type-heading">Choose record type</h2>
          <p>Start with a safe structured template.</p>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={requestClose} aria-label="Close record types">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="add-type-options record-type-options">
        {recordTypeOptions.map((option) => {
          const Icon = option.icon

          return (
            <button
              type="button"
              className="add-type-option add-type-option-blue record-type-option"
              key={option.type}
              onClick={() => closeWithType(option.type)}
              aria-label={`Add ${option.label} record`}
            >
              <span className={`add-type-icon tone-${option.tone}`} aria-hidden="true">
                <Icon size={22} />
              </span>
              <span className="add-type-copy">
                <strong>{option.label}</strong>
                <span>{option.description}</span>
              </span>
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          )
        })}
      </div>
    </SheetDrawer>
  )
}
