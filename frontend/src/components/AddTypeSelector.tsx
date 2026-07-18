import { Bell, Cake, ChevronRight, Grid2X2Plus, RefreshCcw, Wrench } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { getEntityDefinitions, primaryEntityTypes } from '../lib/entityRegistry'
import { guidedWorkflowOptions, type GuidedWorkflowId } from '../lib/guidedWorkflows'
import { useDrawerCloseTransition } from '../lib/useDrawerCloseTransition'
import type { RecordType } from '../types/record'
import { SheetDrawer } from './SheetDrawer'

interface AddTypeSelectorProps {
  isOpen: boolean
  onClose: () => void
  onChooseBirthday: () => void
  onChooseReminder: () => void
  onChooseRenewal: () => void
  onChooseMaintenance: () => void
  onChooseItem: (type: RecordType) => void
  onBrowseItemTypes: () => void
  onChooseWorkflow?: (workflowId: GuidedWorkflowId) => void
}

interface AddOption {
  title: string
  description: string
  icon: LucideIcon
  tone: 'blue' | 'pink' | 'green' | 'orange'
  ariaLabel: string
  onClick: () => void
}

export function AddTypeSelector({
  isOpen,
  onClose,
  onChooseBirthday,
  onChooseReminder,
  onChooseRenewal,
  onChooseMaintenance,
  onChooseItem,
  onBrowseItemTypes,
  onChooseWorkflow,
}: AddTypeSelectorProps) {
  const { closeWithAction, isDrawerOpen, requestClose } = useDrawerCloseTransition({ isOpen, onClose })
  const itemOptions: AddOption[] = getEntityDefinitions(primaryEntityTypes).map((definition) => ({
    title: getChoiceLabel(definition.type, definition.singularLabel),
    description: definition.shortDescription,
    icon: definition.icon,
    tone: definition.type === 'pet' ? 'pink' : definition.type === 'vehicle' || definition.type === 'home' ? 'green' : 'blue',
    ariaLabel: definition.createActionLabel,
    onClick: () => closeWithAction(() => onChooseItem(definition.type)),
  }))
  const responsibilityOptions: AddOption[] = [
    {
      title: 'A reminder',
      description: 'Remember a one-time or recurring task.',
      icon: Bell,
      tone: 'blue',
      ariaLabel: 'Add reminder',
      onClick: () => closeWithAction(onChooseReminder),
    },
    {
      title: 'A birthday',
      description: 'Keep a birthday and age calculation on your radar.',
      icon: Cake,
      tone: 'pink',
      ariaLabel: 'Add birthday reminder',
      onClick: () => closeWithAction(onChooseBirthday),
    },
    {
      title: 'A renewal',
      description: 'Track an expiration, renewal, or review date.',
      icon: RefreshCcw,
      tone: 'orange',
      ariaLabel: 'Add renewal reminder',
      onClick: () => closeWithAction(onChooseRenewal),
    },
    {
      title: 'Maintenance',
      description: 'Plan recurring home, vehicle, pet, or personal care.',
      icon: Wrench,
      tone: 'green',
      ariaLabel: 'Add maintenance reminder',
      onClick: () => closeWithAction(onChooseMaintenance),
    },
  ]
  const guidedOptions: AddOption[] = guidedWorkflowOptions.map((workflow) => ({
    title: workflow.intentLabel,
    description: workflow.shortDescription,
    icon: workflow.icon,
    tone: workflow.associatedItemType === 'pet' ? 'pink' : workflow.associatedItemType === 'vehicle' ? 'green' : 'blue',
    ariaLabel: workflow.intentLabel,
    onClick: () => closeWithAction(() => onChooseWorkflow?.(workflow.id)),
  }))

  return (
    <SheetDrawer
      className="add-type-dialog"
      bodyClassName="sheet-body add-type-options"
      closeLabel="Close add options"
      isOpen={isOpen && isDrawerOpen}
      labelledBy="add-type-heading"
      onClose={requestClose}
      subtitle="Choose a real-world item, or add something that needs your attention."
      title="What would you like to keep track of?"
    >
      {onChooseWorkflow ? (
        <div className="add-option-group guided-add-options" aria-labelledby="common-tracking-heading">
          <h3 id="common-tracking-heading">Common things to track</h3>
          {guidedOptions.map((option) => <AddTypeOption option={option} key={option.ariaLabel} />)}
        </div>
      ) : null}

      <div className="add-option-group" aria-labelledby="important-items-heading">
        <h3 id="important-items-heading">Important items</h3>
        {itemOptions.map((option) => <AddTypeOption option={option} key={option.ariaLabel} />)}
        <button type="button" className="add-type-option add-type-option-blue" onClick={() => closeWithAction(onBrowseItemTypes)} aria-label="Browse all item types">
          <span className="add-type-icon" aria-hidden="true"><Grid2X2Plus size={22} /></span>
          <span className="add-type-copy"><strong>More item types</strong><span>See every item LifeLedger currently supports.</span></span>
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </div>

      <div className="add-option-group add-option-group-secondary" aria-labelledby="responsibilities-and-dates-heading">
        <h3 id="responsibilities-and-dates-heading">Responsibilities and dates</h3>
        {responsibilityOptions.map((option) => <AddTypeOption option={option} key={option.ariaLabel} />)}
      </div>
    </SheetDrawer>
  )
}

function AddTypeOption({ option }: { option: AddOption }) {
  const Icon = option.icon
  return (
    <button type="button" className={`add-type-option add-type-option-${option.tone}`} onClick={option.onClick} aria-label={option.ariaLabel}>
      <span className="add-type-icon" aria-hidden="true"><Icon size={22} /></span>
      <span className="add-type-copy"><strong>{option.title}</strong><span>{option.description}</span></span>
      <ChevronRight size={18} aria-hidden="true" />
    </button>
  )
}

function getChoiceLabel(type: RecordType, singularLabel: string) {
  if (type === 'insurance') return 'Insurance'
  if (type === 'general') return 'Something else'
  if (type === 'appliance') return 'An appliance'
  return `A ${singularLabel.toLocaleLowerCase()}`
}
