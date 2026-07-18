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
      closeLabel="Close item types"
      isOpen={isOpen && isDrawerOpen}
      labelledBy="record-type-heading"
      onClose={requestClose}
      subtitle="Each item type suggests useful details, responsibilities, and documents."
      title="What would you like to keep track of?"
    >
      {recordTypeOptions.map((option) => {
        const Icon = option.icon

        return (
          <button
            type="button"
            className="add-type-option add-type-option-blue record-type-option"
            key={option.type}
            onClick={() => closeWithAction(() => onChoose(option.type))}
            aria-label={option.createActionLabel}
          >
            <span className={`add-type-icon tone-${option.tone}`} aria-hidden="true">
              <Icon size={22} />
            </span>
            <span className="add-type-copy">
              <strong>{option.singularLabel}</strong>
              <span>{option.shortDescription}</span>
            </span>
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        )
      })}
    </SheetDrawer>
  )
}
