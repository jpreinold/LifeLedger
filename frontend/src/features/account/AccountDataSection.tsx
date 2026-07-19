import { Download, FileArchive, ShieldAlert, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { accountApi } from '../../api/accountApi'
import { ApiError } from '../../api/apiClient'
import type { AccountOperation, AccountState } from '../../types/account'


interface AccountDataSectionProps {
  onAccountDeleted?: () => void
}

const deletingStates: AccountState[] = [
  'deletion_requested',
  'deleting',
  'deletion_requires_attention',
  'deleted',
]

export function AccountDataSection({ onAccountDeleted }: AccountDataSectionProps) {
  const [includeProtected, setIncludeProtected] = useState(false)
  const [exportOperation, setExportOperation] = useState<AccountOperation | null>(null)
  const [deletionOperation, setDeletionOperation] = useState<AccountOperation | null>(null)
  const [accountState, setAccountState] = useState<AccountState>('active')
  const [isLoading, setIsLoading] = useState(true)
  const [isExporting, setIsExporting] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false)
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const deleteButtonRef = useRef<HTMLButtonElement>(null)
  const confirmationRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    accountApi.getStatus(controller.signal)
      .then((status) => {
        setAccountState(status.state)
        if (status.current_operation?.operation_type === 'export') setExportOperation(status.current_operation)
        if (status.current_operation?.operation_type === 'deletion') setDeletionOperation(status.current_operation)
        announceState(status.state)
      })
      .catch((requestError) => {
        if (!(requestError instanceof DOMException && requestError.name === 'AbortError')) {
          setError(safeMessage(requestError))
        }
      })
      .finally(() => setIsLoading(false))
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!isDeleteConfirmOpen) return
    const timer = window.setTimeout(() => confirmationRef.current?.focus(), 0)
    return () => window.clearTimeout(timer)
  }, [isDeleteConfirmOpen])

  useEffect(() => {
    const operation = exportOperation
    if (!operation || !['pending', 'in_progress'].includes(operation.status)) return
    const controller = new AbortController()
    const timer = window.setInterval(() => {
      accountApi.getExport(operation.operation_id, controller.signal)
        .then(setExportOperation)
        .catch((requestError) => {
          if (!(requestError instanceof DOMException && requestError.name === 'AbortError')) setError(safeMessage(requestError))
        })
    }, 2_000)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [exportOperation])

  useEffect(() => {
    const operation = deletionOperation
    if (!operation) return
    if (operation.status === 'complete') {
      setAccountState('deleted')
      announceState('deleted')
      onAccountDeleted?.()
      return
    }
    if (!['pending', 'in_progress', 'failed'].includes(operation.status)) return
    const controller = new AbortController()
    const timer = window.setInterval(() => {
      accountApi.getDeletion(operation.operation_id, controller.signal)
        .then((updated) => {
          setDeletionOperation(updated)
          const nextState: AccountState = updated.status === 'failed' ? 'deletion_requires_attention' : 'deleting'
          setAccountState(nextState)
          announceState(nextState)
          if (updated.status === 'complete') onAccountDeleted?.()
        })
        .catch((requestError) => {
          if (requestError instanceof ApiError && ['unauthorized', 'not_found'].includes(requestError.category)) {
            setAccountState('deleted')
            announceState('deleted')
            onAccountDeleted?.()
          } else if (!(requestError instanceof DOMException && requestError.name === 'AbortError')) {
            setError(safeMessage(requestError))
          }
        })
    }, 2_000)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [deletionOperation, onAccountDeleted])

  async function requestExport() {
    setIsExporting(true)
    setError(null)
    try {
      setExportOperation(await accountApi.createExport(includeProtected))
    } catch (requestError) {
      setError(safeMessage(requestError))
    } finally {
      setIsExporting(false)
    }
  }

  async function downloadExport() {
    if (!exportOperation) return
    setError(null)
    try {
      const download = await accountApi.createDownload(exportOperation.operation_id)
      window.location.assign(download.download_url)
    } catch (requestError) {
      setError(safeMessage(requestError))
    }
  }

  async function deleteAccount() {
    if (confirmation !== 'DELETE MY ACCOUNT') return
    setIsDeleting(true)
    setError(null)
    try {
      const operation = await accountApi.requestDeletion(confirmation)
      setDeletionOperation(operation)
      setAccountState('deletion_requested')
      announceState('deletion_requested')
      closeConfirmation()
    } catch (requestError) {
      setError(safeMessage(requestError))
    } finally {
      setIsDeleting(false)
    }
  }

  function closeConfirmation() {
    setIsDeleteConfirmOpen(false)
    setConfirmation('')
    window.setTimeout(() => deleteButtonRef.current?.focus(), 0)
  }

  const deletionActive = deletingStates.includes(accountState)
  const exportReady = exportOperation?.status === 'complete'

  return (
    <section className="settings-digest-card account-data-card" aria-labelledby="settings-account-data-heading">
      <div className="settings-card-header settings-digest-header">
        <div>
          <h3 id="settings-account-data-heading">Data and account</h3>
          <p>Download a portable copy of your LifeLedger data or request permanent account deletion.</p>
        </div>
        <FileArchive size={22} aria-hidden="true" />
      </div>

      {error ? <div className="account-flow-error" role="alert"><strong>Account action could not be completed.</strong><span>{error}</span></div> : null}

      <div className="account-action-panel">
        <h4>Export my data</h4>
        <p>The ZIP includes a versioned JSON manifest, items, responsibilities, history, relationships, settings, document metadata, and available documents.</p>
        <label className="account-protected-option">
          <input
            checked={includeProtected}
            disabled={isExporting || deletionActive}
            type="checkbox"
            onChange={(event) => setIncludeProtected(event.currentTarget.checked)}
          />
          <span><strong>Include decrypted protected details</strong><small>Off by default. When enabled, the download contains sensitive plaintext and expires sooner.</small></span>
        </label>
        {includeProtected ? (
          <div className="account-sensitive-warning" role="note">
            <ShieldAlert size={18} aria-hidden="true" />
            <span>Store this export carefully. LifeLedger uses an expiring authenticated download and does not claim custom archive encryption.</span>
          </div>
        ) : null}
        <div className="account-action-row">
          <button className="primary-button" disabled={isExporting || deletionActive || isLoading} type="button" onClick={() => void requestExport()}>
            {isExporting ? 'Requesting export…' : exportOperation?.status === 'failed' ? 'Retry export' : 'Export my data'}
          </button>
          {exportReady ? (
            <button className="secondary-button" type="button" onClick={() => void downloadExport()}>
              <Download size={17} aria-hidden="true" /> Download export
            </button>
          ) : null}
        </div>
        <p className="account-flow-status" role="status" aria-live="polite">
          {exportStatusText(exportOperation)}
        </p>
      </div>

      <div className="account-action-panel account-delete-panel">
        <h4>Delete my LifeLedger account</h4>
        <p>Deletion may take a few minutes while LifeLedger removes your documents, reminders, history, related-item links, search data, preferences, and integration state.</p>
        <p><strong>This cannot be undone after verification completes.</strong> Export your data first if you may need a copy.</p>
        <button
          ref={deleteButtonRef}
          className="danger-secondary-button"
          disabled={isDeleting || deletionActive || isLoading}
          type="button"
          onClick={() => setIsDeleteConfirmOpen(true)}
        >
          <Trash2 size={17} aria-hidden="true" /> Delete my account
        </button>
        <p className="account-flow-status" role="status" aria-live="polite">
          {deletionStatusText(accountState, deletionOperation)}
        </p>
        {accountState === 'deletion_requires_attention' ? (
          <p className="account-support-note">Deletion is incomplete. LifeLedger will retry safe cleanup; use the existing support contact if this status persists.</p>
        ) : null}
      </div>

      {isDeleteConfirmOpen ? (
        <div className="account-confirm-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeConfirmation() }}>
          <section
            className="account-confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-account-heading"
            aria-describedby="delete-account-description"
            onKeyDown={(event) => { if (event.key === 'Escape') closeConfirmation() }}
          >
            <button className="message-dismiss-button account-confirm-close" type="button" aria-label="Close delete-account confirmation" onClick={closeConfirmation}><X size={19} /></button>
            <h3 id="delete-account-heading">Delete your LifeLedger account?</h3>
            <p id="delete-account-description">Export your data first if needed. Then type <strong>DELETE MY ACCOUNT</strong> to begin permanent deletion.</p>
            <label htmlFor="delete-account-confirmation">Confirmation phrase</label>
            <input
              ref={confirmationRef}
              id="delete-account-confirmation"
              autoComplete="off"
              value={confirmation}
              onChange={(event) => setConfirmation(event.currentTarget.value)}
            />
            <div className="account-confirm-actions">
              <button className="secondary-button" type="button" onClick={closeConfirmation}>Cancel</button>
              <button className="danger-button" disabled={confirmation !== 'DELETE MY ACCOUNT' || isDeleting} type="button" onClick={() => void deleteAccount()}>
                {isDeleting ? 'Starting deletion…' : 'Delete my LifeLedger account'}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  )
}

function announceState(state: AccountState) {
  window.dispatchEvent(new CustomEvent('lifeledger:account-state', { detail: { state } }))
}

function safeMessage(error: unknown) {
  if (error instanceof ApiError) return error.message
  return 'LifeLedger could not complete this account action. Try again.'
}

function exportStatusText(operation: AccountOperation | null) {
  if (!operation) return 'Protected plaintext is excluded unless you explicitly include it.'
  if (operation.status === 'pending' || operation.status === 'in_progress') return 'Preparing your export. This status updates automatically.'
  if (operation.status === 'complete') return `Your export is ready${operation.expires_at ? ` until ${new Date(operation.expires_at).toLocaleString()}` : ''}.`
  if (operation.status === 'expired') return 'This export expired and was removed. Request a new export when ready.'
  return operation.safe_error ?? 'The export could not be prepared. Retry when ready.'
}

function deletionStatusText(state: AccountState, operation: AccountOperation | null) {
  if (state === 'deleted') return 'Account deletion is complete.'
  if (state === 'deletion_requires_attention') return 'Deletion requires additional cleanup and has not been reported complete.'
  if (state === 'deleting' || state === 'deletion_requested') return 'Deletion is in progress. New changes are unavailable.'
  if (operation?.status === 'failed') return operation.safe_error ?? 'Deletion cleanup will be retried safely.'
  return 'No deletion request is active.'
}
