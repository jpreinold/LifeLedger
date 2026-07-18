import { describe, expect, it } from 'vitest'

import { relationshipTypes } from '../types/linkedItem'
import {
  getCategoryPresentation,
  getEntityTypeLabel,
  getRelationshipPresentation,
  getResponsibilityPresentation,
  getSearchResultTypeLabel,
  translateApiPresentationMessage,
} from './terminology'

describe('product terminology', () => {
  it('uses specific item labels and an Other item compatibility fallback', () => {
    expect(getEntityTypeLabel('pet')).toBe('Pet')
    expect(getSearchResultTypeLabel('record', 'vehicle')).toBe('Vehicle')
    expect(getSearchResultTypeLabel('document')).toBe('Document')
    expect(getSearchResultTypeLabel('reminder')).toBe('Reminder')
    expect(getEntityTypeLabel('unknown_type')).toBe('Other item')
  })

  it('hides duplicate categories while preserving distinct organization', () => {
    expect(getCategoryPresentation('vehicle', 'Vehicle')).toBeNull()
    expect(getCategoryPresentation('vehicle', 'vehicle')).toBeNull()
    expect(getCategoryPresentation('vehicle', 'Transportation')).toBe('Transportation')
    expect(getCategoryPresentation('vehicle', 'Commuting')).toBe('Commuting')
    expect(getCategoryPresentation('vehicle', null)).toBeNull()
  })

  it('presents every relationship enum without leaking raw enum formatting', () => {
    for (const relationship of relationshipTypes) {
      const label = getRelationshipPresentation(relationship)
      expect(label).toBeTruthy()
      expect(label).not.toContain('_')
      expect(label).not.toBe(relationship)
    }
    expect(getRelationshipPresentation('UNRECOGNIZED')).toBe('Related to')
  })

  it('keeps reminder language global and responsibility language contextual', () => {
    expect(getResponsibilityPresentation('global')).toEqual({ singular: 'Reminder', plural: 'Reminders', add: 'Add reminder' })
    expect(getResponsibilityPresentation('item')).toEqual({ singular: 'Responsibility', plural: 'Responsibilities', add: 'Add responsibility' })
  })

  it('translates safe backend model language at the presentation boundary', () => {
    expect(translateApiPresentationMessage('Record attachments and linked items could not be loaded.'))
      .toBe('Item documents and related items could not be loaded.')
  })
})
