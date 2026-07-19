import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAppNavigation } from './useAppNavigation'


describe('useAppNavigation', () => {
  beforeEach(() => window.history.replaceState(null, '', '/'))

  it('preserves a safe main page across refresh without placing private state in the URL', () => {
    const { result, unmount } = renderHook(() => useAppNavigation())
    act(() => result.current.setActivePage('settings'))
    expect(window.location.search).toBe('?page=settings')
    expect(window.location.href).not.toContain('protected')
    unmount()

    const refreshed = renderHook(() => useAppNavigation())
    expect(refreshed.result.current.activePage).toBe('settings')
  })

  it('handles browser back and unknown page values safely', () => {
    window.history.replaceState(null, '', '/?page=unknown&openDigest=1')
    const { result } = renderHook(() => useAppNavigation())
    expect(result.current.activePage).toBe('home')
    expect(window.location.search).toContain('openDigest=1')

    act(() => result.current.setActivePage('records'))
    act(() => {
      window.history.replaceState(null, '', '/?page=home')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    expect(result.current.activePage).toBe('home')
  })
})
