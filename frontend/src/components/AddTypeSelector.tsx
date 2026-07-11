import { useCallback, useEffect, useRef, useState } from 'react'
import { Bell, Cake, ChevronRight, FileText, RefreshCcw, Wrench, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { SheetDrawer } from './SheetDrawer'

interface AddTypeSelectorProps {
  isOpen: boolean
  onClose: () => void
  onChooseBirthday: () => void
  onChooseReminder: () => void
  onChooseRenewal: () => void
  onChooseMaintenance: () => void
  onChooseRecord: () => void
}

interface AddOption {
  title: string
  description: string
  icon: LucideIcon
  tone: 'blue' | 'pink' | 'green' | 'orange'
  disabled?: boolean
  onClick?: () => void
}

const drawerCloseMs = 220

export function AddTypeSelector({
  isOpen,
  onClose,
  onChooseBirthday,
  onChooseReminder,
  onChooseRenewal,
  onChooseMaintenance,
  onChooseRecord,
}: AddTypeSelectorProps) {
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

  const closeWithAction = useCallback((action: () => void) => {
    if (isClosingRef.current) {
      return
    }

    isClosingRef.current = true
    setIsDrawerOpen(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      action()
    }, drawerCloseMs)
  }, [])

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

  const options: AddOption[] = [
    {
      title: 'Reminder',
      description: 'For one-time or recurring tasks.',
      icon: Bell,
      tone: 'blue',
      onClick: () => closeWithAction(onChooseReminder),
    },
    {
      title: 'Birthday',
      description: 'Track birthdays and calculate age.',
      icon: Cake,
      tone: 'pink',
      onClick: () => closeWithAction(onChooseBirthday),
    },
    {
      title: 'Renewal',
      description: 'Track renewals, expirations, subscriptions, warranties, and review dates.',
      icon: RefreshCcw,
      tone: 'orange',
      onClick: () => closeWithAction(onChooseRenewal),
    },
    {
      title: 'Maintenance',
      description: 'Track recurring home, vehicle, pet, and personal maintenance.',
      icon: Wrench,
      tone: 'green',
      onClick: () => closeWithAction(onChooseMaintenance),
    },
    {
      title: 'Record',
      description: 'Save structured personal details.',
      icon: FileText,
      tone: 'green',
      onClick: () => closeWithAction(onChooseRecord),
    },
  ]

  return (
    <SheetDrawer
      className="add-type-dialog"
      isOpen={isOpen && isDrawerOpen}
      labelledBy="add-type-heading"
      onClose={requestClose}
    >
        <div className="sheet-header">
          <div>
            <h2 id="add-type-heading">What would you like to add?</h2>
            <p>Choose the kind of item to create.</p>
          </div>
          <button type="button" className="icon-button ghost-icon-button" onClick={requestClose} aria-label="Close add options">
            <X size={19} aria-hidden="true" />
          </button>
        </div>

        <div className="add-type-options">
          {options.map((option) => (
            <AddTypeOption option={option} key={option.title} />
          ))}
        </div>
    </SheetDrawer>
  )
}

function AddTypeOption({ option }: { option: AddOption }) {
  const Icon = option.icon

  return (
    <button
      type="button"
      className={`add-type-option add-type-option-${option.tone}`}
      disabled={option.disabled}
      onClick={option.onClick}
      aria-label={option.disabled ? `${option.title} coming soon` : `Add ${option.title}`}
    >
      <span className="add-type-icon" aria-hidden="true">
        <Icon size={22} />
      </span>
      <span className="add-type-copy">
        <strong>{option.title}</strong>
        <span>{option.description}</span>
      </span>
      {option.disabled ? <small>Coming soon</small> : <ChevronRight size={18} aria-hidden="true" />}
    </button>
  )
}

