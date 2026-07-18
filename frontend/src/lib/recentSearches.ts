const storageKey = 'lifeledger.recentSearches.v2'
const legacyStorageKey = 'lifeledger.recentSearches.v1'
const settingKey = 'lifeledger.rememberRecentSearches.v1'
const maxRecentSearches = 8
const recentSearchTtlMs = 7 * 24 * 60 * 60 * 1000

export interface RecentSearch {
  query: string
  createdAt: string
}

export function isRememberRecentSearchesEnabled(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return window.localStorage.getItem(settingKey) === 'true'
  } catch {
    return false
  }
}

export function setRememberRecentSearches(enabled: boolean): boolean {
  if (typeof window === 'undefined') return false
  try {
    if (enabled) {
      window.localStorage.setItem(settingKey, 'true')
    } else {
      window.localStorage.removeItem(settingKey)
      removeStoredSearchEntries()
    }
    return enabled
  } catch {
    return false
  }
}

export function loadRecentSearches(now = new Date()): RecentSearch[] {
  if (typeof window === 'undefined') return []
  if (!isRememberRecentSearchesEnabled()) {
    removeStoredSearchEntries()
    return []
  }

  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    const cutoff = now.getTime() - recentSearchTtlMs
    const valid = parsed
      .filter((item): item is RecentSearch => typeof item?.query === 'string' && typeof item?.createdAt === 'string')
      .filter((item) => item.query.trim().length > 0 && item.query.length <= 120)
      .filter((item) => {
        const createdAt = Date.parse(item.createdAt)
        return Number.isFinite(createdAt) && createdAt >= cutoff && createdAt <= now.getTime()
      })
      .slice(0, maxRecentSearches)
    window.localStorage.setItem(storageKey, JSON.stringify(valid))
    return valid
  } catch {
    return []
  }
}

export function saveRecentSearch(query: string): RecentSearch[] {
  const normalized = query.trim().slice(0, 120)
  if (!normalized || typeof window === 'undefined' || !isRememberRecentSearchesEnabled()) {
    return loadRecentSearches()
  }

  const next = [
    { query: normalized, createdAt: new Date().toISOString() },
    ...loadRecentSearches().filter((item) => item.query.toLocaleLowerCase() !== normalized.toLocaleLowerCase()),
  ].slice(0, maxRecentSearches)

  try {
    window.localStorage.setItem(storageKey, JSON.stringify(next))
  } catch {
    return next
  }
  return next
}

export function removeRecentSearch(createdAt: string): RecentSearch[] {
  const next = loadRecentSearches().filter((item) => item.createdAt !== createdAt)
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(next))
    } catch {
      return next
    }
  }
  return next
}

export function clearRecentSearches(): RecentSearch[] {
  if (typeof window === 'undefined') return []
  removeStoredSearchEntries()
  return []
}

function removeStoredSearchEntries(): void {
  try {
    window.localStorage.removeItem(storageKey)
    window.localStorage.removeItem(legacyStorageKey)
  } catch {
    // Device storage can be unavailable; remembering remains disabled.
  }
}
