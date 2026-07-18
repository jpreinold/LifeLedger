import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { searchApi } from '../api/searchApi'
import type { LifeRecord } from '../types/record'
import type { SavedSearchView, SearchResponse } from '../types/search'
import { SearchView } from './SearchView'

vi.mock('../api/searchApi', () => ({
  searchApi: {
    search: vi.fn(),
    listSavedViews: vi.fn(),
    createSavedView: vi.fn(),
    deleteSavedView: vi.fn(),
  },
}))

const api = vi.mocked(searchApi)

const searchResponse: SearchResponse = {
  items: [
    {
      source_item_id: 'record-1',
      source_item_type: 'record',
      title: 'Passport',
      subtitle: 'Travel Documents',
      status: 'active',
      category: 'Documents',
      relevant_date: '2027-07-16',
      archived: false,
      match_context: ['Matched title'],
      linked_context: [],
      navigation_metadata: { record_id: 'record-1' },
      updated_at: '2026-07-16T12:00:00.000Z',
    },
  ],
  next_cursor: null,
  applied_filters: {},
  result_count: 1,
}

const savedView: SavedSearchView = {
  saved_view_id: 'view-1',
  name: 'Travel docs',
  query: 'passport',
  filters: { itemTypes: ['record'], statuses: [] },
  sort: 'relevance',
  icon: 'folder',
  is_pinned: false,
  created_at: '2026-07-16T12:00:00.000Z',
  updated_at: '2026-07-16T12:00:00.000Z',
}

function itemRecord(id: string, recordType: LifeRecord['record_type'], title: string): LifeRecord {
  return {
    id,
    record_type: recordType,
    title,
    subtitle: null,
    category: recordType === 'vehicle' ? 'Transportation' : 'Family',
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
    created_at: '2026-07-16T12:00:00.000Z',
    updated_at: '2026-07-18T12:00:00.000Z',
  }
}

describe('SearchView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    window.localStorage.clear()
    api.search.mockResolvedValue(searchResponse)
    api.listSavedViews.mockResolvedValue([savedView])
    api.createSavedView.mockResolvedValue({ ...savedView, saved_view_id: 'view-2', name: 'Passport files' })
    api.deleteSavedView.mockResolvedValue(undefined)
  })

  it('runs search, opens record results, and saves the current view', async () => {
    const user = userEvent.setup()
    const onViewRecord = vi.fn()

    render(
      <SearchView
        onViewRecord={onViewRecord}
        onViewReminder={vi.fn()}
        onViewDocument={vi.fn()}
      />,
    )

    expect(await screen.findByText('Travel docs')).toBeInTheDocument()

    await user.type(screen.getByPlaceholderText('Search items, documents, reminders...'), 'passport')

    await waitFor(() => expect(api.search).toHaveBeenCalledWith(expect.objectContaining({ q: 'passport' })))
    expect(await screen.findByText('Passport')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Passport/ }))
    expect(onViewRecord).toHaveBeenCalledWith('record-1')

    await user.click(screen.getByRole('button', { name: 'Open saved views' }))
    await user.type(screen.getByPlaceholderText('Travel documents'), 'Passport files')
    await user.click(screen.getByRole('button', { name: 'Save view' }))

    await waitFor(() => expect(api.createSavedView).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Passport files',
      query: 'passport',
      sort: 'relevance',
    })))
  })
  it('passes the exact document ID from a search result', async () => {
    const user = userEvent.setup()
    const onViewDocument = vi.fn()
    api.search.mockResolvedValue({
      ...searchResponse,
      items: [{
        ...searchResponse.items[0],
        source_item_id: 'record-9#document-b',
        source_item_type: 'document',
        title: 'duplicate-name.pdf',
        navigation_metadata: {
          record_id: 'record-9',
          attachment_id: 'document-b',
          document_id: 'record-9#document-b',
        },
      }],
    })

    render(
      <SearchView
        onViewRecord={vi.fn()}
        onViewReminder={vi.fn()}
        onViewDocument={onViewDocument}
      />,
    )

    await user.type(screen.getByPlaceholderText('Search items, documents, reminders...'), 'duplicate')
    const result = await screen.findByRole('button', { name: /duplicate-name.pdf/ })
    await user.click(result)
    expect(onViewDocument).toHaveBeenCalledWith('record-9', 'document-b')
  })

  it('presents specific item, document, and reminder result types', async () => {
    const baxter = itemRecord('pet-1', 'pet', 'Baxter')
    const mazda = itemRecord('vehicle-1', 'vehicle', 'Mazda3')
    api.search.mockResolvedValue({
      ...searchResponse,
      result_count: 4,
      items: [
        { ...searchResponse.items[0], source_item_id: baxter.id, title: baxter.title, navigation_metadata: { record_id: baxter.id } },
        { ...searchResponse.items[0], source_item_id: mazda.id, title: mazda.title, navigation_metadata: { record_id: mazda.id } },
        {
          ...searchResponse.items[0],
          source_item_id: 'vehicle-1#registration',
          source_item_type: 'document',
          title: 'Mazda registration',
          navigation_metadata: { record_id: mazda.id, attachment_id: 'registration' },
        },
        {
          ...searchResponse.items[0],
          source_item_id: 'reminder-1',
          source_item_type: 'reminder',
          title: 'Rabies vaccination',
          linked_context: ['Linked to Baxter'],
          navigation_metadata: { reminder_id: 'reminder-1' },
        },
      ],
    })

    render(
      <SearchView
        records={[baxter, mazda]}
        onViewRecord={vi.fn()}
        onViewReminder={vi.fn()}
        onViewDocument={vi.fn()}
      />,
    )

    await userEvent.type(screen.getByPlaceholderText('Search items, documents, reminders...'), 'life')
    const petResult = (await screen.findByText('Baxter', { selector: 'strong' })).closest('button')!
    const vehicleResult = screen.getByText('Mazda3', { selector: 'strong' }).closest('button')!
    const documentResult = screen.getByText('Mazda registration', { selector: 'strong' }).closest('button')!
    const reminderResult = screen.getByText('Rabies vaccination', { selector: 'strong' }).closest('button')!

    expect(within(petResult).getByText('Pet')).toBeInTheDocument()
    expect(within(vehicleResult).getByText('Vehicle')).toBeInTheDocument()
    expect(within(documentResult).getByText('Document')).toBeInTheDocument()
    expect(within(documentResult).getByText('Related to Mazda3')).toBeInTheDocument()
    expect(within(reminderResult).getByText('Reminder')).toBeInTheDocument()
    expect(within(reminderResult).getByText('Related to Baxter')).toBeInTheDocument()
  })
})
