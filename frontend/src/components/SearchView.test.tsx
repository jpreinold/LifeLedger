import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { searchApi } from '../api/searchApi'
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

    await user.type(screen.getByPlaceholderText('Search records, docs, reminders...'), 'passport')

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
})
