import { useEffect, useMemo, useState } from 'react'
import { ClipboardList, PlusCircle, Search, X } from 'lucide-react'

import { lifeAdminTemplates } from '../templates/lifeAdminTemplates'
import { reminderCategories, type ReminderCategory, type ReminderInput } from '../types/reminder'
import type { LifeAdminTemplate } from '../types/template'

type TemplateFilter = 'All' | ReminderCategory

interface LifeAdminTemplatesProps {
  isOpen: boolean
  onClose: () => void
  onUseTemplate: (input: ReminderInput) => void
}

const filters: TemplateFilter[] = ['All', ...reminderCategories]

export function LifeAdminTemplates({ isOpen, onClose, onUseTemplate }: LifeAdminTemplatesProps) {
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

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="template-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="life-admin-templates-heading"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="template-dialog-header">
          <div>
            <h2 id="life-admin-templates-heading">Life Admin Templates</h2>
            <p>Search common renewals, maintenance reminders, and recurring responsibilities.</p>
          </div>
          <button type="button" className="secondary-button dialog-close-button" onClick={onClose}>
            <X size={18} aria-hidden="true" />
            Close
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
          <div className="template-count">{visibleTemplates.length} templates</div>
          <div className="template-grid">
            {visibleTemplates.map((template) => (
              <TemplateCard template={template} key={template.id} onUseTemplate={handleUseTemplate} />
            ))}
          </div>
          {visibleTemplates.length === 0 ? <p className="empty-state">No templates match that search.</p> : null}
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
  return (
    <article className="template-card">
      <div className="card-topline">
        <span className="category-chip">{template.category}</span>
        <ClipboardList size={18} aria-hidden="true" />
      </div>

      <div>
        <h3>{template.title}</h3>
        <p>{template.description}</p>
      </div>

      <dl className="template-meta">
        <div>
          <dt>Repeat</dt>
          <dd>{template.recommendedRepeat}</dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>{template.recommendedPriority}</dd>
        </div>
      </dl>

      <button
        type="button"
        className="secondary-button template-use-button"
        onClick={() => onUseTemplate(toInput(template))}
      >
        <PlusCircle size={17} aria-hidden="true" />
        Use template
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
