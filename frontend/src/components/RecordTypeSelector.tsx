import { ChevronRight } from 'lucide-react'

import { recordTypeOptions } from '../lib/recordTypes'
import { useDrawerCloseTransition } from '../lib/useDrawerCloseTransition'
import type { RecordType } from '../types/record'
import { SheetDrawer } from './SheetDrawer'

interface RecordTypeSelectorProps {
  isOpen: boolean
  onChoose: (type: RecordType) => void
  onClose: () => void
}

export function RecordTypeSelector({ isOpen, onChoose, onClose }: RecordTypeSelectorProps) {
  const { closeWithAction, isDrawerOpen, requestClose } = useDrawerCloseTransition({ isOpen, onClose })

  return (
    <SheetDrawer
      className="record-type-dialog"
      bodyClassName="sheet-body add-type-options record-type-options"
      closeLabel="Close record types"
      isOpen={isOpen && isDrawerOpen}
      labelledBy="record-type-heading"
      onClose={requestClose}
      subtitle="Start with a safe structured template."
      title="Choose record type"
    >
      {recordTypeOptions.map((option) => {
        const Icon = option.icon

        return (
          <button
            type="button"
            className="add-type-option add-type-option-blue record-type-option"
            key={option.type}
            onClick={() => closeWithAction(() => onChoose(option.type))}
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
    </SheetDrawer>
  )
}
