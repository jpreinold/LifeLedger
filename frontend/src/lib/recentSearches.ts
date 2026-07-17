const storageKey = 'lifeledger.recentSearches.v1'
const maxRecentSearches = 8

export interface RecentSearch {
  query: string
  createdAt: string
}

export function loadRecentSearches(): RecentSearch[] {
  if (typeof window === 'undefined') {
    return []
  }

  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed
      .filter((item): item is RecentSearch => typeof item?.query === 'string' && typeof item?.createdAt === 'string')
      .slice(0, maxRecentSearches)
  } catch {
    return []
  }
}

export function saveRecentSearch(query: string): RecentSearch[] {
  const normalized = query.trim()
  if (!normalized || typeof window === 'undefined') {
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

export function clearRecentSearches(): RecentSearch[] {
  if (typeof window === 'undefined') {
    return []
  }

  try {
    window.localStorage.removeItem(storageKey)
  } catch {
    return []
  }

  return []
}
