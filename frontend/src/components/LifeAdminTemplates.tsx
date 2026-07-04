import { useEffect, useMemo, useState } from 'react'
import { LayoutTemplate, Plus, Search, X } from 'lucide-react'

import { lifeAdminTemplates } from '../templates/lifeAdminTemplates'
import { reminderCategories, type ReminderCategory, type ReminderInput } from '../types/reminder'
import type { LifeAdminTemplate } from '../types/template'
import { getCategoryVisual } from './categoryVisuals'

type TemplateFilter = 'All' | ReminderCategory

interface LifeAdminTemplatesProps {
  isOpen: boolean
  onClose: () => void
  onStartBlank: () => void
  onUseTemplate: (input: ReminderInput) => void
}

const filters: TemplateFilter[] = ['All', ...reminderCategories]

export function LifeAdminTemplates({ isOpen, onClose, onStartBlank, onUseTemplate }: LifeAdminTemplatesProps) {
  const [activeFilter, setActiveFilter] = useState<TemplateFilter>('All')
  const [query, setQuery] = useState('')

  const visibleTemplates = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()

    if (activeFilter === 'All') {
      return lifeAdminTemplates.filter((template) => matchesQuery(template, normalizedQuery))
    }

    return lifeAdminTemplates.filter(
      (template) => template.category === activeFilter && matchesQuery(template, normalizedQuery),
    )
  }, [activeFilter, query])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) {
    return null
  }

  function handleUseTemplate(input: ReminderInput) {
    onUseTemplate(input)
    onClose()
  }

  function handleStartBlank() {
    onStartBlank()
    onClose()
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="sheet-dialog template-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="life-admin-templates-heading"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sheet-header">
          <div>
            <h2 id="life-admin-templates-heading">Templates</h2>
            <p>Start from a common reminder, then confirm the due date.</p>
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
            placeholder="Search templates"
            aria-label="Search templates"
          />
        </div>

        <div className="template-filters" aria-label="Filter templates by category">
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
          <div className="template-grid">
            {visibleTemplates.map((template) => (
              <TemplateCard template={template} key={template.id} onUseTemplate={handleUseTemplate} />
            ))}
          </div>
          {visibleTemplates.length === 0 ? <p className="empty-state">No templates match that search.</p> : null}
        </div>

        <div className="template-footer">
          <button type="button" className="secondary-button start-blank-button" onClick={handleStartBlank}>
            <LayoutTemplate size={17} aria-hidden="true" />
            Start blank reminder
          </button>
        </div>
      </section>
    </div>
  )
}

function TemplateCard({
  template,
  onUseTemplate,
}: {
  template: LifeAdminTemplate
  onUseTemplate: (input: ReminderInput) => void
}) {
  const { Icon, tone } = getCategoryVisual(template.category)

  return (
    <article className={`template-card tone-${tone}`}>
      <div className={`category-icon tone-${tone}`} aria-hidden="true">
        <Icon size={24} />
      </div>

      <div className="template-card-content">
        <h3>{template.title}</h3>
        <span className="category-chip">{template.category}</span>
        <p>{template.description}</p>
        <div className="template-meta">
          <span>{template.recommendedRepeat}</span>
          <span>{template.recommendedPriority}</span>
        </div>
      </div>

      <button type="button" className="template-use-button" onClick={() => onUseTemplate(toInput(template))}>
        <Plus size={20} aria-hidden="true" />
        <span className="sr-only">Use {template.title} template</span>
      </button>
    </article>
  )
}

function toInput(template: LifeAdminTemplate): ReminderInput {
  return {
    title: template.title,
    category: template.category,
    due_date: new Date().toISOString().slice(0, 10),
    repeat: template.recommendedRepeat,
    priority: template.recommendedPriority,
    notes: template.suggestedNotes,
  }
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
    ...(template.tags ?? []),
  ].join(' ')

  return searchable.toLowerCase().includes(query)
}
