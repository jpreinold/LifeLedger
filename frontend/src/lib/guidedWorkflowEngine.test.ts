import { describe, expect, it, vi } from 'vitest'

import type { LifeRecord, ProtectedRecordStatus, RecordAttachment } from '../types/record'
import type { Reminder } from '../types/reminder'
import { createGuidedWorkflowProgress, runGuidedWorkflowAttempt } from './guidedWorkflowEngine'
import { guidedWorkflowRegistry } from './guidedWorkflows'

const protectedStatus: ProtectedRecordStatus = {
  has_protected_data: true,
  protected_field_names: ['vin'],
  protected_encryption_version: 1,
  protected_updated_at: '2026-07-18T12:00:00.000Z',
}

function record(overrides: Partial<LifeRecord> = {}): LifeRecord {
  return {
    id: 'vehicle-1',
    record_type: 'vehicle',
    title: 'Family car',
    subtitle: null,
    category: 'Transportation',
    owner_name: null,
    provider_or_brand: null,
    start_date: null,
    issue_date: null,
    expiration_date: null,
    purchase_date: null,
    renewal_date: null,
    location_hint: null,
    notes: null,
    tags: [],
    status: 'active',
    has_protected_data: false,
    protected_field_names: [],
    dynamic_fields: [],
    created_at: '2026-07-18T12:00:00.000Z',
    updated_at: '2026-07-18T12:00:00.000Z',
    ...overrides,
  }
}

const reminder = {
  id: 'reminder-1',
  title: 'Registration renewal',
  due_date: '2030-04-15',
  reminder_lead_value: 1,
  reminder_lead_unit: 'months',
} as unknown as Reminder

const attachment: RecordAttachment = {
  attachment_id: 'attachment-1',
  record_id: 'vehicle-1',
  display_name: 'registration.pdf',
  content_type: 'application/pdf',
  size_bytes: 3,
  status: 'scanning',
  scan_result: 'pending',
  created_at: '2026-07-18T12:00:00.000Z',
  uploaded_at: '2026-07-18T12:00:00.000Z',
  scan_completed_at: null,
  available_at: null,
  deleted_at: null,
}

describe('guided workflow recovery', () => {
  it('creates a passport, stores its number through protected storage, and links one renewal', async () => {
    const passport = record({
      id: 'passport-1',
      record_type: 'passport',
      title: 'Jamie',
      category: 'Identity',
      owner_name: 'Jamie',
      expiration_date: '2032-10-01',
    })
    const passportReminder = { ...reminder, id: 'passport-reminder', title: 'Passport renewal', due_date: '2032-10-01' } as Reminder
    const createItem = vi.fn().mockResolvedValue(passport)
    const saveProtected = vi.fn().mockResolvedValue({ ...protectedStatus, protected_field_names: ['document_number'] })
    const createReminder = vi.fn().mockResolvedValue(passportReminder)
    const createRelationship = vi.fn().mockResolvedValue(undefined)

    const result = await runGuidedWorkflowAttempt({
      workflow: guidedWorkflowRegistry.passport_expiration,
      values: {
        item_title: 'Jamie',
        expiration_date: '2032-10-01',
        issuing_country: 'United States',
        passport_number: 'P1234567',
        reminder_lead_value: '6',
        reminder_lead_unit: 'months',
        reminder_repeat: 'None',
      },
      existingItem: null,
      approvedUpdates: new Set(),
      document: null,
      progress: createGuidedWorkflowProgress('passport-attempt'),
    }, {
      createItem,
      updateItem: vi.fn(),
      createDetail: vi.fn(),
      updateDetail: vi.fn(),
      saveProtected,
      createReminder,
      createRelationship,
      uploadDocument: vi.fn(),
    })

    expect(result.complete).toBe(true)
    expect(createItem).toHaveBeenCalledWith(expect.objectContaining({
      record_type: 'passport',
      title: 'Jamie',
      owner_name: null,
      expiration_date: '2032-10-01',
    }), 'passport-attempt:item')
    expect(saveProtected).toHaveBeenCalledWith('passport-1', { document_number: 'P1234567' }, false)
    expect(createReminder).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Passport renewal',
      due_date: '2032-10-01',
      repeat: 'None',
    }), 'passport-attempt:responsibility', 'passport-1')
    expect(createRelationship).toHaveBeenCalledWith('passport-1', 'passport-reminder', 'reminder_for')
  })

  it('retries only unfinished child operations and never duplicates the item or reminder', async () => {
    const item = record()
    const document = new File(['pdf'], 'registration.pdf', { type: 'application/pdf', lastModified: 1 })
    const progress = createGuidedWorkflowProgress('guided-attempt')
    const createItem = vi.fn().mockResolvedValue(item)
    const createDetail = vi.fn()
      .mockRejectedValueOnce(new TypeError('network interrupted'))
      .mockResolvedValueOnce(record({
        dynamic_fields: [{
          field_id: 'field-1', key: 'registration_expiration', label: 'Registration expiration', field_type: 'date',
          value: '2030-04-15', is_sensitive: false, has_value: true, display_order: 185, select_options: [],
          created_at: item.created_at, updated_at: item.updated_at,
        }],
      }))
    const saveProtected = vi.fn()
      .mockRejectedValueOnce(new TypeError('network interrupted'))
      .mockResolvedValueOnce(protectedStatus)
    const createReminder = vi.fn().mockResolvedValue(reminder)
    const createRelationship = vi.fn()
      .mockRejectedValueOnce(new TypeError('network interrupted'))
      .mockResolvedValueOnce(undefined)
    const uploadDocument = vi.fn()
      .mockRejectedValueOnce(new TypeError('network interrupted'))
      .mockResolvedValueOnce(attachment)
    const dependencies = {
      createItem,
      updateItem: vi.fn(),
      createDetail,
      updateDetail: vi.fn(),
      saveProtected,
      createReminder,
      createRelationship,
      uploadDocument,
    }
    const attempt = {
      workflow: guidedWorkflowRegistry.vehicle_registration,
      values: {
        item_title: 'Family car',
        vin: '1HGCM82633A004352',
        registration_expiration: '2030-04-15',
        reminder_lead_value: '1',
        reminder_lead_unit: 'months',
        reminder_repeat: 'Yearly',
      },
      existingItem: null,
      approvedUpdates: new Set<string>(),
      document,
      progress,
    }

    const first = await runGuidedWorkflowAttempt(attempt, dependencies)
    const second = await runGuidedWorkflowAttempt(attempt, dependencies)

    expect(first.complete).toBe(false)
    expect(first.message).toBe('Family car is available, but some guided setup still needs attention.')
    expect(first.failedOperations).toEqual(expect.arrayContaining(['details', 'protected', 'relationship', 'document']))
    expect(second.complete).toBe(true)
    expect(second.failedOperations).toEqual([])
    expect(second.message).toContain('1 month before 2030-04-15')
    expect(createItem).toHaveBeenCalledTimes(1)
    expect(createReminder).toHaveBeenCalledTimes(1)
    expect(createDetail).toHaveBeenCalledTimes(2)
    expect(saveProtected).toHaveBeenCalledTimes(2)
    expect(createRelationship).toHaveBeenCalledTimes(2)
    expect(uploadDocument).toHaveBeenCalledTimes(2)
    expect(createItem).toHaveBeenCalledWith(expect.objectContaining({ title: 'Family car' }), 'guided-attempt:item')
    expect(createReminder).toHaveBeenCalledWith(expect.objectContaining({ due_date: '2030-04-15' }), 'guided-attempt:responsibility', 'vehicle-1')
    expect(uploadDocument).toHaveBeenCalledWith('vehicle-1', document, 'guided-attempt:document')
  })

  it('keeps existing item values when changes were not approved', async () => {
    const existing = record({ provider_or_brand: 'Current make' })
    const progress = createGuidedWorkflowProgress('existing-attempt')
    const updateItem = vi.fn()
    const dependencies = {
      createItem: vi.fn(),
      updateItem,
      createDetail: vi.fn().mockResolvedValue(existing),
      updateDetail: vi.fn(),
      saveProtected: vi.fn(),
      createReminder: vi.fn().mockResolvedValue(reminder),
      createRelationship: vi.fn().mockResolvedValue(undefined),
      uploadDocument: vi.fn(),
    }

    const result = await runGuidedWorkflowAttempt({
      workflow: guidedWorkflowRegistry.vehicle_registration,
      values: {
        item_title: existing.title,
        make: 'Replacement make',
        registration_expiration: '2030-04-15',
        reminder_lead_value: '1',
        reminder_lead_unit: 'months',
        reminder_repeat: 'Yearly',
      },
      existingItem: existing,
      approvedUpdates: new Set(),
      document: null,
      progress,
    }, dependencies)

    expect(result.complete).toBe(true)
    expect(updateItem).not.toHaveBeenCalled()
    expect(progress.item?.provider_or_brand).toBe('Current make')
  })
})
