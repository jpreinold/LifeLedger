import { describe, expect, it } from 'vitest'

import { recordTypes } from '../types/record'
import {
  entityCapabilityRegistry,
  entityTypeOrder,
  getEntityDefinition,
} from './entityRegistry'
import { createRecordInput, normalizeRecordInput, recordToInput } from './recordTypes'

describe('entity capability registry', () => {
  it('defines every persisted record type and falls back safely for unknown types', () => {
    expect(Object.keys(entityCapabilityRegistry).sort()).toEqual([...recordTypes].sort())
    expect(entityTypeOrder).toHaveLength(recordTypes.length)
    expect(new Set(entityTypeOrder).size).toBe(entityTypeOrder.length)

    for (const type of recordTypes) {
      const definition = getEntityDefinition(type)
      expect(definition.id).toBe(type)
      expect(definition.internalRecordType).toBe(type)
      expect(definition.singularLabel).toBeTruthy()
      expect(definition.pluralLabel).toBeTruthy()
      expect(definition.icon).toBeTruthy()
      expect(definition.supportedSections).toContain('overview')
      expect(definition.supportedSections).toContain('documents')
      expect(definition.supportedSections).toContain('relatedItems')
    }

    expect(getEntityDefinition('future_legacy_type').singularLabel).toBe('Other item')
  })

  it('keeps suggested detail keys and ordering stable within each item type', () => {
    for (const definition of Object.values(entityCapabilityRegistry)) {
      const keys = definition.suggestedDetails.map((detail) => detail.key)
      const displayOrder = definition.suggestedDetails.map((detail) => detail.displayOrder)

      expect(new Set(keys).size, `${definition.type} detail keys`).toBe(keys.length)
      expect(new Set(displayOrder).size, `${definition.type} display order`).toBe(displayOrder.length)
      expect(displayOrder, `${definition.type} display order`).toEqual([...displayOrder].sort((a, b) => a - b))
    }
  })

  it('never makes a protected suggested detail searchable', () => {
    const protectedDetails = Object.values(entityCapabilityRegistry)
      .flatMap((definition) => definition.suggestedDetails)
      .filter((detail) => detail.protectedByDefault || detail.protectedField)

    expect(protectedDetails.length).toBeGreaterThan(0)
    expect(protectedDetails.every((detail) => !detail.searchable)).toBe(true)
  })

  it('preserves meaningful and legacy category values without rewriting stored items', () => {
    const input = createRecordInput('vehicle')
    expect(input.category).toBe('Transportation')

    const normalized = normalizeRecordInput({ ...input, title: '  Mazda3  ', category: 'Commuting' })
    expect(normalized.title).toBe('Mazda3')
    expect(normalized.category).toBe('Commuting')

    const legacy = recordToInput({ ...input, title: 'Mazda3', category: 'Vehicle' })
    expect(legacy.category).toBe('Vehicle')
  })

  it('keeps profile fields first-class and omits audited duplicate identity fields', () => {
    const person = getEntityDefinition('person')
    expect(person.fields).toContain('relationship_context')
    expect(person.defaultSuggestedFields).toContain('relationship_context')
    expect(person.dynamicFieldPresets.map((field) => field.key)).not.toContain('preferred_name')
    expect(person.dynamicFieldPresets.map((field) => field.key)).not.toContain('relationship_context')

    expect(getEntityDefinition('passport').fields).not.toContain('owner_name')
    expect(getEntityDefinition('driver_license').fields).not.toContain('owner_name')
  })
})
