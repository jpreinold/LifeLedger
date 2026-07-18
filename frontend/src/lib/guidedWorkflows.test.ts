import { describe, expect, it } from 'vitest'

import { relationshipTypes } from '../types/linkedItem'
import type { LifeRecord } from '../types/record'
import {
  buildGuidedExistingRecordInput,
  buildGuidedProtectedInput,
  buildGuidedReminderInput,
  getCompatibleActiveItems,
  guidedWorkflowOptions,
  repeatForBillingFrequency,
  validateGuidedWorkflowConfiguration,
} from './guidedWorkflows'

function record(overrides: Partial<LifeRecord> = {}): LifeRecord {
  return {
    id: 'record-1',
    record_type: 'subscription',
    title: 'Music service',
    subtitle: null,
    category: 'Finance',
    owner_name: null,
    provider_or_brand: 'Current provider',
    start_date: null,
    issue_date: null,
    expiration_date: null,
    purchase_date: null,
    renewal_date: '2030-01-15',
    location_hint: null,
    notes: 'Keep this note',
    tags: ['existing'],
    status: 'active',
    has_protected_data: false,
    protected_field_names: [],
    dynamic_fields: [],
    created_at: '2026-07-01T12:00:00.000Z',
    updated_at: '2026-07-18T12:00:00.000Z',
    ...overrides,
  }
}

describe('guided workflow registry', () => {
  it('declares four valid, uniquely mapped workflows with safe protected fields', () => {
    expect(guidedWorkflowOptions.map((workflow) => workflow.id)).toEqual([
      'passport_expiration',
      'vehicle_registration',
      'pet_vaccination',
      'subscription_renewal',
    ])
    expect(new Set(guidedWorkflowOptions.map((workflow) => workflow.id)).size).toBe(4)

    for (const workflow of guidedWorkflowOptions) {
      expect(validateGuidedWorkflowConfiguration(workflow)).toBe(true)
      expect(workflow.requiredSteps).toEqual(['item', 'details', 'responsibility', 'document', 'review'])
      expect(workflow.documentPrompt.optional).toBe(true)
      expect(relationshipTypes).toContain(workflow.relationshipDefaults.type)
      expect(workflow.fields.filter((field) => field.protected).every((field) => !field.searchable)).toBe(true)
      expect(workflow.reviewPresentation.saveLabel).not.toMatch(/passport_expiration|vehicle_registration|pet_vaccination|subscription_renewal/)
    }
  })

  it('filters compatible existing items by type and active status', () => {
    const workflow = guidedWorkflowOptions.find((item) => item.id === 'subscription_renewal')!
    const active = record()
    const archived = record({ id: 'archived', status: 'archived' })
    const vehicle = record({ id: 'vehicle', record_type: 'vehicle' })

    expect(getCompatibleActiveItems(workflow, [active, archived, vehicle])).toEqual([active])
  })
})

describe('guided workflow builders', () => {
  it('preserves existing safe item values until the user explicitly approves a replacement', () => {
    const workflow = guidedWorkflowOptions.find((item) => item.id === 'subscription_renewal')!
    const existing = record()
    const values = {
      item_title: existing.title,
      provider: 'Replacement provider',
      renewal_date: '2031-02-20',
      billing_frequency: 'Monthly',
    }

    const kept = buildGuidedExistingRecordInput(workflow, existing, values, new Set())
    const replaced = buildGuidedExistingRecordInput(workflow, existing, values, new Set(['provider', 'renewal_date']))

    expect(kept.provider_or_brand).toBe('Current provider')
    expect(kept.renewal_date).toBe('2030-01-15')
    expect(kept.notes).toBe('Keep this note')
    expect(kept.tags).toEqual(['existing'])
    expect(replaced.provider_or_brand).toBe('Replacement provider')
    expect(replaced.renewal_date).toBe('2031-02-20')
  })

  it('maps protected passport and vehicle values only into protected storage payloads', () => {
    const passport = guidedWorkflowOptions.find((item) => item.id === 'passport_expiration')!
    const vehicle = guidedWorkflowOptions.find((item) => item.id === 'vehicle_registration')!

    expect(buildGuidedProtectedInput(passport, { passport_number: 'P1234567' })).toEqual({ document_number: 'P1234567' })
    expect(buildGuidedProtectedInput(vehicle, { vin: '1HGCM82633A004352', license_plate: 'ABC123' })).toEqual({ vin: '1HGCM82633A004352' })
  })

  it('creates an advisory-neutral pet maintenance reminder and frequency-aware subscription recurrence', () => {
    const pet = guidedWorkflowOptions.find((item) => item.id === 'pet_vaccination')!
    const reminder = buildGuidedReminderInput(pet, {
      vaccination_name: 'Custom vaccine',
      next_due_date: '2030-06-01',
      administered_date: '2029-06-01',
      vaccination_provider: 'Neighborhood Vet',
      reminder_lead_value: '2',
      reminder_lead_unit: 'weeks',
      reminder_repeat: 'None',
    }, 'Baxter')

    expect(reminder).toMatchObject({
      title: 'Custom vaccine vaccination',
      reminder_type: 'maintenance',
      due_date: '2030-06-01',
      repeat: 'None',
      maintenance_details: {
        item_name: 'Baxter',
        maintenance_area: 'pet',
        last_completed_date: '2029-06-01',
        next_due_date: '2030-06-01',
      },
    })
    expect(repeatForBillingFrequency('Monthly')).toBe('Monthly')
    expect(repeatForBillingFrequency('Quarterly')).toBe('Quarterly')
    expect(repeatForBillingFrequency('Yearly')).toBe('Yearly')
    expect(repeatForBillingFrequency('Custom or non-recurring')).toBe('None')

    const subscription = guidedWorkflowOptions.find((item) => item.id === 'subscription_renewal')!
    const yearly = buildGuidedReminderInput(subscription, {
      renewal_date: '2030-12-01',
      billing_frequency: 'Yearly',
      reminder_lead_value: '2',
      reminder_lead_unit: 'weeks',
      reminder_repeat: 'Yearly',
    }, 'Annual membership')
    expect(yearly).toMatchObject({ due_date: '2030-12-01', repeat: 'Yearly', reminder_type: 'renewal' })
  })
})
