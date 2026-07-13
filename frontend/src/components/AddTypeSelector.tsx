import { Bell, Cake, ChevronRight, FileText, RefreshCcw, Wrench } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useDrawerCloseTransition } from '../lib/useDrawerCloseTransition'
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

export function AddTypeSelector({
  isOpen,
  onClose,
  onChooseBirthday,
  onChooseReminder,
  onChooseRenewal,
  onChooseMaintenance,
  onChooseRecord,
}: AddTypeSelectorProps) {
  const { closeWithAction, isDrawerOpen, requestClose } = useDrawerCloseTransition({ isOpen, onClose })

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
      bodyClassName="sheet-body add-type-options"
      closeLabel="Close add options"
      isOpen={isOpen && isDrawerOpen}
      labelledBy="add-type-heading"
      onClose={requestClose}
      subtitle="Choose the kind of item to create."
      title="What would you like to add?"
    >
      {options.map((option) => (
        <AddTypeOption option={option} key={option.title} />
      ))}
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

