import { useMemo, useState, type ReactNode } from 'react'
import { LayoutTemplate, Plus, Search, X } from 'lucide-react'

import { lifeAdminTemplates } from '../templates/lifeAdminTemplates'
import {
  createBirthdayReminderInput,
  createMaintenanceReminderInput,
  createRenewalReminderInput,
} from '../lib/reminderInput'
import { getMaintenanceDefaults, getMaintenanceRepeat } from '../lib/maintenanceUx'
import { getBackendRenewalKind, withRenewalDisplayKind } from '../lib/renewalUx'
import { buildReminderInputWithDefaultTiming, formatReminderTiming } from '../lib/reminderSchedule'
import type { ReminderInput } from '../types/reminder'
import type { LifeAdminTemplate, TemplateFilterGroup } from '../types/template'
import { getCategoryVisual } from './categoryVisuals'
import { SheetDrawer } from './SheetDrawer'

type TemplateFilter = 'All' | TemplateFilterGroup

interface LifeAdminTemplatesProps {
  isOpen: boolean
  onClose: () => void
  onStartBlank: () => void
  onUseTemplate: (input: ReminderInput) => void
}

const filters: TemplateFilter[] = [
  'All',
  'Smart',
  'Dates & People',
  'Vehicle',
  'Home',
  'Health',
  'Finance',
  'Subscriptions',
  'Documents',
  'Maintenance',
  'Coming soon',
]

export function LifeAdminTemplates({ isOpen, onClose, onStartBlank, onUseTemplate }: LifeAdminTemplatesProps) {
  const [activeFilter, setActiveFilter] = useState<TemplateFilter>('All')
  const [query, setQuery] = useState('')

  const filteredTemplates = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()

    return lifeAdminTemplates.filter(
      (template) => matchesFilter(template, activeFilter) && matchesQuery(template, normalizedQuery),
    )
  }, [activeFilter, query])

  const featuredTemplates = filteredTemplates.filter((template) => template.featured)
  const regularTemplates = filteredTemplates.filter((template) => !template.featured)
  const hasResults = featuredTemplates.length > 0 || regularTemplates.length > 0

  function handleUseTemplate(template: LifeAdminTemplate) {
    if (template.targetType === 'comingSoon') {
      return
    }

    onUseTemplate(toInput(template))
    onClose()
  }

  function handleStartBlank() {
    onStartBlank()
    onClose()
  }

  return (
    <SheetDrawer
      className="template-dialog"
      isOpen={isOpen}
      labelledBy="life-admin-templates-heading"
      onClose={onClose}
    >
        <div className="sheet-header">
          <div>
            <h2 id="life-admin-templates-heading">Templates</h2>
            <p>Choose what you want to track, then confirm it in the right setup flow.</p>
          </div>
          <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close templates">
            <X size={19} aria-hidden="true" />
          </button>
        </div>

        <div className="template-search">
          <Search size={17} aria-hidden="true" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search birthdays, renewals, passport, trial..."
            aria-label="Search templates"
          />
        </div>

        <div className="template-filters" aria-label="Filter templates by purpose">
          {filters.map((filter) => (
            <button
              type="button"
              className={filter === activeFilter ? 'template-filter active' : 'template-filter'}
              key={filter}
              onClick={() => setActiveFilter(filter)}
            >
              {filter}
            </button>
          ))}
        </div>

        <div className="template-results">
          {featuredTemplates.length > 0 ? (
            <TemplateSection title="Recommended smart starters">
              {featuredTemplates.map((template) => (
                <TemplateCard template={template} key={template.id} onUseTemplate={handleUseTemplate} />
              ))}
            </TemplateSection>
          ) : null}

          {regularTemplates.length > 0 ? (
            <TemplateSection title={activeFilter === 'All' ? 'More templates' : `${activeFilter} templates`}>
              {regularTemplates.map((template) => (
                <TemplateCard template={template} key={template.id} onUseTemplate={handleUseTemplate} />
              ))}
            </TemplateSection>
          ) : null}

          {!hasResults ? <p className="empty-state">No templates match that search.</p> : null}
        </div>

        <div className="template-footer">
          <button type="button" className="secondary-button start-blank-button" onClick={handleStartBlank}>
            <LayoutTemplate size={17} aria-hidden="true" />
            Start blank reminder
          </button>
        </div>
    </SheetDrawer>
  )
}

function TemplateSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="template-section" aria-label={title}>
      <h3>{title}</h3>
      <div className="template-grid">{children}</div>
    </section>
  )
}

function TemplateCard({
  template,
  onUseTemplate,
}: {
  template: LifeAdminTemplate
  onUseTemplate: (template: LifeAdminTemplate) => void
}) {
  const { Icon, tone } = getCategoryVisual(template.category)
  const isComingSoon = template.targetType === 'comingSoon'
  const badge = getTemplateBadge(template)

  return (
    <article className={`template-card tone-${tone} ${isComingSoon ? 'template-card-coming-soon' : ''}`}>
      <div className={`category-icon tone-${tone}`} aria-hidden="true">
        <Icon size={24} />
      </div>

      <div className="template-card-content">
        <h3>{template.title}</h3>
        <div className="template-card-labels">
          <span className="category-chip">{template.category}</span>
          <span className={isComingSoon ? 'coming-soon-template-badge' : 'smart-template-badge'}>{badge}</span>
        </div>
        <p>{template.description}</p>
        <div className="template-meta">
          {isComingSoon ? <span>{template.comingSoonLabel ?? 'Future phase'}</span> : <span>{template.recommendedRepeat}</span>}
          {!isComingSoon && template.defaultReminderTiming ? <span>{formatTemplateReminderTiming(template)}</span> : null}
        </div>
      </div>

      <button
        type="button"
        className="template-use-button"
        disabled={isComingSoon}
        onClick={() => onUseTemplate(template)}
        aria-label={isComingSoon ? `${template.title} coming soon` : `Use ${template.title} template`}
      >
        {isComingSoon ? <span aria-hidden="true">Soon</span> : <Plus size={20} aria-hidden="true" />}
      </button>
    </article>
  )
}

function toInput(template: LifeAdminTemplate): ReminderInput {
  if (template.targetType === 'birthday') {
    return createBirthdayReminderInput({
      title: template.title,
      category: template.category,
      priority: template.recommendedPriority,
      notes: template.suggestedNotes,
      reminder_lead_value: template.defaultReminderTiming?.reminder_lead_value ?? 1,
      reminder_lead_unit: template.defaultReminderTiming?.reminder_lead_unit ?? 'weeks',
      reminder_time: template.defaultReminderTiming?.reminder_time ?? '09:00',
    })
  }

  if (template.targetType === 'renewal') {
    const displayKind = template.targetKind ?? 'renewal'
    const renewalDetails = withRenewalDisplayKind({
      item_name: template.renewalItemName ?? getTemplateRenewalItemName(template.title),
      renewal_kind: getBackendRenewalKind(displayKind),
      owner_name: null,
      provider: null,
      renewal_date: null,
      expiration_date: null,
      renewal_window_days: template.renewalWindowDays ?? null,
      review_lead_days: template.reviewLeadDays ?? null,
      frequency: null,
    }, displayKind)

    return createRenewalReminderInput({
      title: template.title,
      category: template.category,
      repeat: template.recommendedRepeat,
      priority: template.recommendedPriority,
      notes: template.suggestedNotes,
      reminder_lead_value: template.defaultReminderTiming?.reminder_lead_value ?? 1,
      reminder_lead_unit: template.defaultReminderTiming?.reminder_lead_unit ?? 'months',
      reminder_time: template.defaultReminderTiming?.reminder_time ?? '09:00',
      renewal_details: renewalDetails,
    })
  }
  if (template.targetType === 'maintenance') {
    const maintenanceArea = template.maintenanceArea ?? 'home'
    const defaults = getMaintenanceDefaults(maintenanceArea)
    const maintenanceDetails = {
      item_name: template.maintenanceItemName ?? template.title,
      maintenance_area: maintenanceArea,
      last_completed_date: null,
      interval_value: template.maintenanceIntervalValue ?? defaults.interval_value,
      interval_unit: template.maintenanceIntervalUnit ?? defaults.interval_unit,
      next_due_date: null,
      instructions: template.maintenanceInstructions ?? null,
    }

    return createMaintenanceReminderInput({
      title: template.title,
      category: template.category,
      repeat: getMaintenanceRepeat(maintenanceDetails),
      priority: template.recommendedPriority,
      notes: template.suggestedNotes,
      reminder_lead_value: template.defaultReminderTiming?.reminder_lead_value ?? defaults.reminder_lead_value,
      reminder_lead_unit: template.defaultReminderTiming?.reminder_lead_unit ?? defaults.reminder_lead_unit,
      reminder_time: template.defaultReminderTiming?.reminder_time ?? defaults.reminder_time,
      maintenance_details: maintenanceDetails,
    })
  }

  return buildReminderInputWithDefaultTiming({
    title: template.title,
    category: template.category,
    due_date: new Date().toISOString().slice(0, 10),
    repeat: template.recommendedRepeat,
    priority: template.recommendedPriority,
    notes: template.suggestedNotes,
    reminder_lead_value: template.defaultReminderTiming?.reminder_lead_value ?? null,
    reminder_lead_unit: template.defaultReminderTiming?.reminder_lead_unit ?? null,
    reminder_time: template.defaultReminderTiming?.reminder_time ?? null,
    reminder_type: 'generic',
    birthday_details: null,
    renewal_details: null,
    maintenance_details: null,
  })
}

function getTemplateRenewalItemName(title: string) {
  return title
    .replace(/^Renew\s+/i, '')
    .replace(/\s+reminder$/i, '')
    .replace(/\s+renewal$/i, '')
    .replace(/\s+expiration$/i, '')
    .trim() || title
}

function getTemplateBadge(template: LifeAdminTemplate) {
  if (template.smartBadge) {
    return template.smartBadge
  }

  if (template.targetType === 'comingSoon') {
    return 'Coming soon'
  }

  if (template.targetType === 'generic') {
    return 'Reminder'
  }

  return 'Smart'
}

function formatTemplateReminderTiming(template: LifeAdminTemplate) {
  if (!template.defaultReminderTiming) {
    return ''
  }

  return formatReminderTiming({
    reminder_lead_value: template.defaultReminderTiming.reminder_lead_value,
    reminder_lead_unit: template.defaultReminderTiming.reminder_lead_unit,
    reminder_time: template.defaultReminderTiming.reminder_time ?? null,
  })
}

function matchesFilter(template: LifeAdminTemplate, filter: TemplateFilter) {
  if (filter === 'All') {
    return true
  }

  if (filter === 'Smart') {
    return template.targetType === 'birthday' || template.targetType === 'renewal' || template.targetType === 'maintenance'
  }

  if (filter === 'Coming soon') {
    return template.targetType === 'comingSoon'
  }

  return template.filterGroups?.includes(filter) ?? false
}

function matchesQuery(template: LifeAdminTemplate, query: string) {
  if (!query) {
    return true
  }

  const searchable = [
    template.title,
    template.description,
    template.category,
    template.suggestedNotes,
    template.smartBadge,
    template.targetType,
    template.targetKind,
    template.comingSoonLabel,
    ...(template.filterGroups ?? []),
    ...(template.tags ?? []),
  ].join(' ')

  return searchable.toLowerCase().includes(query)
}
