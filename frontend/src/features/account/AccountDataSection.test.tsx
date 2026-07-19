import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { accountApi } from '../../api/accountApi'
import type { AccountOperation } from '../../types/account'
import { AccountDataSection } from './AccountDataSection'


vi.mock('../../api/accountApi', () => ({
  accountApi: {
    getStatus: vi.fn(),
    createExport: vi.fn(),
    getExport: vi.fn(),
    createDownload: vi.fn(),
    requestDeletion: vi.fn(),
    getDeletion: vi.fn(),
  },
}))

const operation = (overrides: Partial<AccountOperation> = {}): AccountOperation => ({
  operation_id: 'operation-1',
  operation_type: 'export',
  status: 'pending',
  include_protected_details: false,
  created_at: '2026-07-18T12:00:00Z',
  updated_at: '2026-07-18T12:00:00Z',
  expires_at: null,
  artifact_size_bytes: null,
  safe_error: null,
  steps: [],
  ...overrides,
})

describe('AccountDataSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(accountApi.getStatus).mockResolvedValue({ state: 'active', current_operation: null })
    vi.mocked(accountApi.createExport).mockResolvedValue(operation())
    vi.mocked(accountApi.getExport).mockResolvedValue(operation())
    vi.mocked(accountApi.requestDeletion).mockResolvedValue(operation({ operation_type: 'deletion' }))
    vi.mocked(accountApi.getDeletion).mockResolvedValue(operation({ operation_type: 'deletion' }))
  })

  it('shows Data and account and excludes protected plaintext by default', async () => {
    render(<AccountDataSection />)

    expect(await screen.findByRole('heading', { name: 'Data and account' })).toBeInTheDocument()
    expect(screen.getByLabelText(/include decrypted protected details/i)).not.toBeChecked()
    expect(screen.getByText(/protected plaintext is excluded/i)).toBeInTheDocument()
    expect(screen.getByText(/export your data first/i)).toBeInTheDocument()
  })

  it('shows the protected-detail warning and announces export progress', async () => {
    const user = userEvent.setup()
    render(<AccountDataSection />)
    await screen.findByRole('heading', { name: 'Data and account' })

    await user.click(screen.getByLabelText(/include decrypted protected details/i))
    expect(screen.getByText(/contains sensitive plaintext/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Export my data' }))

    expect(accountApi.createExport).toHaveBeenCalledWith(true)
    expect(screen.getAllByRole('status').some((element) => /preparing your export/i.test(element.textContent ?? ''))).toBe(true)
  })

  it('shows ready, expired, and retryable export states clearly', async () => {
    vi.mocked(accountApi.getStatus).mockResolvedValue({
      state: 'active',
      current_operation: operation({ status: 'complete', expires_at: '2030-01-01T00:00:00Z' }),
    })
    const { unmount } = render(<AccountDataSection />)
    expect(await screen.findByRole('button', { name: /download export/i })).toBeInTheDocument()
    unmount()

    vi.mocked(accountApi.getStatus).mockResolvedValue({
      state: 'active',
      current_operation: operation({ status: 'expired' }),
    })
    const expired = render(<AccountDataSection />)
    expect(await screen.findByText(/export expired and was removed/i)).toBeInTheDocument()
    expired.unmount()

    vi.mocked(accountApi.getStatus).mockResolvedValue({
      state: 'active',
      current_operation: operation({ status: 'failed', safe_error: 'The export can be retried safely.' }),
    })
    render(<AccountDataSection />)
    expect(await screen.findByRole('button', { name: 'Retry export' })).toBeInTheDocument()
    expect(screen.getByText('The export can be retried safely.')).toBeInTheDocument()
  })

  it('requires deliberate typed deletion confirmation and restores focus', async () => {
    const user = userEvent.setup()
    render(<AccountDataSection />)
    const openButton = await screen.findByRole('button', { name: 'Delete my account' })
    await user.click(openButton)

    const confirmation = screen.getByLabelText('Confirmation phrase')
    await waitFor(() => expect(confirmation).toHaveFocus())
    const destructive = screen.getByRole('button', { name: 'Delete my LifeLedger account' })
    expect(destructive).toBeDisabled()
    await user.type(confirmation, 'DELETE MY ACCOUNT')
    expect(destructive).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(openButton).toHaveFocus())
  })

  it('announces deleting and attention states and remains usable at 320px', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 320 })
    fireEvent(window, new Event('resize'))
    const stateEvents: string[] = []
    window.addEventListener('lifeledger:account-state', (event: Event) => {
      stateEvents.push((event as CustomEvent<{ state: string }>).detail.state)
    })
    vi.mocked(accountApi.getStatus).mockResolvedValue({
      state: 'deletion_requires_attention',
      current_operation: operation({ operation_type: 'deletion', status: 'failed', safe_error: 'Cleanup is incomplete.' }),
    })

    render(<AccountDataSection />)

    expect(await screen.findByText(/deletion requires additional cleanup/i)).toBeInTheDocument()
    expect(screen.getByText(/use the existing support contact/i)).toBeInTheDocument()
    expect(stateEvents).toContain('deletion_requires_attention')
    expect(screen.getByRole('button', { name: 'Delete my account' })).toBeDisabled()
  })
})
