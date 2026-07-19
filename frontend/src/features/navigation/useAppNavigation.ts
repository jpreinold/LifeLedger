import { useCallback, useEffect, useState } from 'react'


export type AppPage = 'home' | 'search' | 'reminders' | 'records' | 'settings' | 'calendar'

const pages = new Set<AppPage>(['home', 'search', 'reminders', 'records', 'settings', 'calendar'])

export function useAppNavigation() {
  const [activePage, setPageState] = useState<AppPage>(() => pageFromUrl())

  useEffect(() => {
    normalizePageUrl()
    const handlePopState = () => setPageState(pageFromUrl())
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const setActivePage = useCallback((page: AppPage) => {
    setPageState(page)
    const params = new URLSearchParams(window.location.search)
    if (page === 'home') params.delete('page')
    else params.set('page', page)
    const search = params.toString()
    const nextUrl = `${window.location.pathname}${search ? `?${search}` : ''}${window.location.hash}`
    window.history.pushState({ lifeledgerPage: page }, '', nextUrl || '/')
  }, [])

  return { activePage, setActivePage }
}

function pageFromUrl(): AppPage {
  const value = new URLSearchParams(window.location.search).get('page')
  return value && pages.has(value as AppPage) ? value as AppPage : 'home'
}

function normalizePageUrl() {
  const params = new URLSearchParams(window.location.search)
  const current = params.get('page')
  if (current === null || pages.has(current as AppPage)) return
  params.delete('page')
  const search = params.toString()
  window.history.replaceState(null, '', `${window.location.pathname}${search ? `?${search}` : ''}${window.location.hash}`)
}
