import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearRecentSearches,
  isRememberRecentSearchesEnabled,
  loadRecentSearches,
  removeRecentSearch,
  saveRecentSearch,
  setRememberRecentSearches,
} from './recentSearches'

describe('recent searches privacy', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-17T12:00:00.000Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not persist searches and clears legacy entries until the device-local setting is enabled', () => {
    window.localStorage.setItem('lifeledger.recentSearches.v1', '["legacy query"]')
    expect(isRememberRecentSearchesEnabled()).toBe(false)
    expect(loadRecentSearches()).toEqual([])
    expect(saveRecentSearch('passport number')).toEqual([])
    expect(window.localStorage.length).toBe(0)
  })

  it('stores only bounded deduplicated query entries when enabled', () => {
    setRememberRecentSearches(true)
    for (let index = 0; index < 10; index += 1) {
      vi.setSystemTime(new Date(`2026-07-17T12:00:00.${String(index).padStart(3, '0')}Z`))
      saveRecentSearch(`query ${index}`)
    }
    saveRecentSearch(' QUERY 9 ')

    const stored = loadRecentSearches()
    expect(stored).toHaveLength(8)
    expect(stored[0].query).toBe('QUERY 9')
    expect(stored.filter((item) => item.query.toLowerCase() === 'query 9')).toHaveLength(1)
    expect(Object.keys(stored[0]).sort()).toEqual(['createdAt', 'query'])
  })

  it('expires old entries and supports individual and clear-all removal', () => {
    setRememberRecentSearches(true)
    const first = saveRecentSearch('first')[0]
    vi.advanceTimersByTime(1_000)
    saveRecentSearch('second')

    expect(removeRecentSearch(first.createdAt).map((item) => item.query)).toEqual(['second'])
    expect(clearRecentSearches()).toEqual([])
    expect(loadRecentSearches()).toEqual([])

    saveRecentSearch('expires')
    vi.advanceTimersByTime(8 * 24 * 60 * 60 * 1000)
    expect(loadRecentSearches()).toEqual([])
  })

  it('clears current and legacy entries immediately when disabled', () => {
    setRememberRecentSearches(true)
    saveRecentSearch('device-only')
    window.localStorage.setItem('lifeledger.recentSearches.v1', '["legacy"]')

    setRememberRecentSearches(false)

    expect(isRememberRecentSearchesEnabled()).toBe(false)
    expect(window.localStorage.getItem('lifeledger.recentSearches.v2')).toBeNull()
    expect(window.localStorage.getItem('lifeledger.recentSearches.v1')).toBeNull()
  })
})