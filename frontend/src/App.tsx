import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import {
  AlertCircle,
  Bell,
  CalendarDays,
  CheckCircle,
  CheckCircle2,
  FileText,
  Home,
  Inbox,
  ListChecks,
  Plus,
  RefreshCcw,
  Search,
  ShieldCheck,
  Settings,
  X,
} from 'lucide-react'

import { calendarApi, type GoogleCalendarStatus } from './api/calendarApi'
import { linkedItemsApi } from './api/linkedItemsApi'
import { recordsApi } from './api/recordsApi'
import { remindersApi } from './api/remindersApi'
import { preferencesApi } from './api/preferencesApi'
import { isCognitoAuthEnabled } from './auth/config'
import { AddTypeSelector } from './components/AddTypeSelector'
import { AlertCenter } from './components/AlertCenter'
import { ConfirmDialog } from './components/ConfirmDialog'
import { DailyDigestDrawer } from './components/DailyDigestDrawer'
import { Dashboard } from './components/Dashboard'
import { EditReminderDrawer } from './components/EditReminderDrawer'
import { HomeDashboard } from './components/HomeDashboard'
import { LifeAdminTemplates } from './components/LifeAdminTemplates'
import type { RecordDetailTab } from './components/RecordDetailDrawer'
import type { RecordCreationResult } from './components/RecordForm'
import { RecordsView } from './components/RecordsView'
import { RecordTypeSelector } from './components/RecordTypeSelector'
import { ReminderForm } from './components/ReminderForm'
import type { TemplateDraft } from './components/ReminderForm'
import { ReminderList } from './components/ReminderList'
import { buildDailyDigest } from './lib/digest'
import type { ReminderStatusFilter, ReminderTypeFilter } from './lib/reminderDisplay'
import {
  createBirthdayReminderInput,
  createGenericReminderInput,
  createMaintenanceReminderInput,
  createRenewalReminderInput,
  emptyBirthdayDetails,
  emptyMaintenanceDetails,
  emptyRenewalDetails,
} from './lib/reminderInput'
import { runRecordSetupAttempt } from './lib/recordCreationWorkflow'
import type { GuidedWorkflowId } from './lib/guidedWorkflows'
import { hasProtectedRecordInput } from './lib/recordTypes'
import { useAppNavigation, type AppPage } from './features/navigation/useAppNavigation'
import type { SuggestedResponsibilityDefinition } from './lib/entityRegistry'
import { productTerms } from './lib/terminology'
import {
  defaultDigestPreferences,
  getBrowserTimeZone,
  type DigestPreferences,
  type DigestPreferencesUpdate,
} from './types/preferences'
import type { Reminder, ReminderAlert, ReminderInput } from './types/reminder'
import type { DynamicRecordFieldInput, LifeRecord, ProtectedRecordInput, ProtectedRecordStatus, RecordInput, RecordType } from './types/record'
import type { LinkCreateRequest } from './types/linkedItem'
import type { RecordFilter } from './lib/recordTypes'
import type { CaptureDetail } from './types/capture'

const AuthenticatedApp = lazy(() => import('./components/AuthenticatedApp'))
const CalendarView = lazy(() => import('./components/CalendarView').then((module) => ({ default: module.CalendarView })))
const CaptureInbox = lazy(() => import('./features/capture/CaptureInbox').then((module) => ({ default: module.CaptureInbox })))
const GuidedWorkflowDrawer = lazy(() => import('./components/GuidedWorkflowDrawer').then((module) => ({ default: module.GuidedWorkflowDrawer })))
const LifecycleActionDrawer = lazy(() => import('./components/LifecycleActionDrawer').then((module) => ({ default: module.LifecycleActionDrawer })))
const RecordDetailDrawer = lazy(() => import('./components/RecordDetailDrawer').then((module) => ({ default: module.RecordDetailDrawer })))
const RecordForm = lazy(() => import('./components/RecordForm').then((module) => ({ default: module.RecordForm })))
const ReminderDetailDrawer = lazy(() => import('./components/ReminderDetailDrawer').then((module) => ({ default: module.ReminderDetailDrawer })))
const SearchView = lazy(() => import('./components/SearchView').then((module) => ({ default: module.SearchView })))
const SettingsView = lazy(() => import('./features/settings/SettingsView').then((module) => ({ default: module.SettingsView })))

function App() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW()

  const updateToast = needRefresh ? (
    <PwaUpdateToast
      onDismiss={() => setNeedRefresh(false)}
      onUpdate={() => {
        void updateServiceWorker(true)
      }}
    />
  ) : null

  if (!isCognitoAuthEnabled) {
    return (
      <>
        <ReminderApp />
        {updateToast}
      </>
    )
  }

  return <Suspense fallback={<main className="app-loading" role="status">Loading secure workspace…</main>}><AuthenticatedApp updateToast={updateToast} /></Suspense>
}

interface PwaUpdateToastProps {
  onDismiss: () => void
  onUpdate: () => void
}

function PwaUpdateToast({ onDismiss, onUpdate }: PwaUpdateToastProps) {
  return (
    <aside className="update-toast" role="status" aria-live="polite">
      <div className="update-toast-icon" aria-hidden="true">
        <RefreshCcw size={18} />
      </div>
      <div className="update-toast-copy">
        <strong>Update available</strong>
        <span>Refresh to install the latest LifeLedger.</span>
      </div>
      <div className="update-toast-actions">
        <button type="button" className="update-toast-primary" onClick={onUpdate}>
          Update
        </button>
        <button type="button" className="update-toast-dismiss" onClick={onDismiss} aria-label="Dismiss update notice">
          Later
        </button>
      </div>
    </aside>
  )
}

interface ReminderAppProps {
  onSignOut?: () => void
  userLabel?: string | null
}

type ViewingRecordState = { initialTab: RecordDetailTab; record: LifeRecord; documentId?: string }
type RecordCreationProgress = {
  record: LifeRecord
  protectedSaved: boolean
  successfulFiles: Set<string>
  successfulLinks: Set<string>
  successfulDetails: Set<string>
}

export function ReminderApp({ onSignOut, userLabel }: ReminderAppProps) {
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [records, setRecords] = useState<LifeRecord[]>([])
  const [alerts, setAlerts] = useState<ReminderAlert[]>([])
  const [digestPreferences, setDigestPreferences] = useState<DigestPreferences>(() => defaultDigestPreferences())
  const [calendarStatus, setCalendarStatus] = useState<GoogleCalendarStatus | null>(null)
  const [isCalendarStatusLoading, setIsCalendarStatusLoading] = useState(true)
  const [calendarStatusError, setCalendarStatusError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRecordsLoading, setIsRecordsLoading] = useState(true)
  const [isDigestPreferencesLoading, setIsDigestPreferencesLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isSavingDigestPreferences, setIsSavingDigestPreferences] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editingReminder, setEditingReminder] = useState<Reminder | null>(null)
  const [viewingReminder, setViewingReminder] = useState<{ reminder: Reminder; fromAlert: boolean } | null>(null)
  const [editingRecord, setEditingRecord] = useState<LifeRecord | null>(null)
  const [viewingRecord, setViewingRecord] = useState<ViewingRecordState | null>(null)
  const [recordBackStack, setRecordBackStack] = useState<ViewingRecordState[]>([])
  const recordCreationProgressRef = useRef(new Map<string, RecordCreationProgress>())
  const reminderDeleteInFlightRef = useRef(false)
  const [pendingDelete, setPendingDelete] = useState<Reminder | null>(null)
  const [pendingReminderActionId, setPendingReminderActionId] = useState<string | null>(null)
  const [lifecycleAction, setLifecycleAction] = useState<{ action: 'complete' | 'renew'; reminder: Reminder } | null>(null)
  const [pendingRecordDelete, setPendingRecordDelete] = useState<LifeRecord | null>(null)
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft | null>(null)
  const { activePage, setActivePage } = useAppNavigation()
  const [calendarVisibleMonth, setCalendarVisibleMonth] = useState(() => getMonthStartDateKey(new Date()))
  const [calendarSelectedDate, setCalendarSelectedDate] = useState<string | null>(() => getDateKey(new Date()))
  const [reminderStatusFilter, setReminderStatusFilter] = useState<ReminderStatusFilter>('active')
  const [reminderTypeFilter, setReminderTypeFilter] = useState<ReminderTypeFilter>('all')
  const [recordFilter, setRecordFilter] = useState<RecordFilter>('all')
  const [showArchivedRecords, setShowArchivedRecords] = useState(false)
  const [isReminderFormOpen, setIsReminderFormOpen] = useState(false)
  const [isRecordFormOpen, setIsRecordFormOpen] = useState(false)
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false)
  const [isAddTypeSelectorOpen, setIsAddTypeSelectorOpen] = useState(false)
  const [isRecordTypeSelectorOpen, setIsRecordTypeSelectorOpen] = useState(false)
  const [guidedWorkflow, setGuidedWorkflow] = useState<{ id: GuidedWorkflowId; item: LifeRecord | null } | null>(null)
  const [selectedRecordType, setSelectedRecordType] = useState<RecordType>('general')
  const [responsibilityRecordId, setResponsibilityRecordId] = useState<string | null>(null)
  const [addDateContext, setAddDateContext] = useState<string | null>(null)
  const [isAlertCenterOpen, setIsAlertCenterOpen] = useState(false)
  const [isDigestOpen, setIsDigestOpen] = useState(false)
  const [isAccountDeleting, setIsAccountDeleting] = useState(false)
  const [initialCaptureDetail, setInitialCaptureDetail] = useState<CaptureDetail | null>(null)
  const didHandleDigestUrl = useRef(false)
  const openDailyDigestRef = useRef<() => void>(() => undefined)

  useEffect(() => {
    const handleAccountState = (event: Event) => {
      const state = (event as CustomEvent<{ state?: string }>).detail?.state
      const deleting = ['deletion_requested', 'deleting', 'deletion_requires_attention', 'deleted'].includes(state ?? '')
      setIsAccountDeleting(deleting)
      if (deleting) {
        setIsAddTypeSelectorOpen(false)
        setIsRecordTypeSelectorOpen(false)
        setIsRecordFormOpen(false)
        setIsReminderFormOpen(false)
        setGuidedWorkflow(null)
      }
    }
    window.addEventListener('lifeledger:account-state', handleAccountState)
    return () => window.removeEventListener('lifeledger:account-state', handleAccountState)
  }, [])

  async function loadReminderData() {
    setIsLoading(true)
    setError(null)

    try {
      const [reminderData, alertData] = await Promise.all([remindersApi.list(), remindersApi.alerts()])
      setReminders(reminderData)
      setAlerts(alertData)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load reminders.')
    } finally {
      setIsLoading(false)
    }
  }

  async function loadRecordData() {
    setIsRecordsLoading(true)

    try {
      const recordData = await recordsApi.list(true)
      setRecords(recordData)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load items.')
    } finally {
      setIsRecordsLoading(false)
    }
  }

  async function loadCalendarStatus() {
    setIsCalendarStatusLoading(true)
    setCalendarStatusError(null)

    try {
      const status = await calendarApi.getStatus()
      setCalendarStatus(status)
    } catch (requestError) {
      setCalendarStatus(null)
      setCalendarStatusError(requestError instanceof Error ? requestError.message : 'Unable to load Google Calendar settings.')
    } finally {
      setIsCalendarStatusLoading(false)
    }
  }

  async function initializeCalendarStatus() {
    const handledCallback = await handleGoogleCalendarCallbackFromUrl()
    if (!handledCallback) {
      await loadCalendarStatus()
    }
  }

  async function handleGoogleCalendarCallbackFromUrl() {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const state = params.get('state')
    const oauthError = params.get('error')

    if (!code && !state && !oauthError) {
      return false
    }

    clearGoogleOAuthUrlParams(params)
    setIsCalendarStatusLoading(true)
    setCalendarStatusError(null)
    setError(null)
    setNotice(null)

    try {
      if (oauthError) {
        throw new Error('Google Calendar connection was cancelled.')
      }
      if (!code || !state) {
        throw new Error('Google Calendar connection expired. Try again.')
      }
      if (hasProcessedGoogleOAuthCallbackState(state)) {
        await loadCalendarStatus()
        setNotice('Google Calendar connection status refreshed.')
        return true
      }

      markGoogleOAuthCallbackStateProcessed(state)
      const status = await calendarApi.callback({ code, state })
      setCalendarStatus(status)
      setNotice(status.connected ? 'Google Calendar connected.' : 'Google Calendar connection status refreshed.')
    } catch (requestError) {
      setCalendarStatus(null)
      setCalendarStatusError(requestError instanceof Error ? requestError.message : 'Unable to connect Google Calendar.')
      setError(requestError instanceof Error ? requestError.message : 'Unable to connect Google Calendar.')
    } finally {
      setIsCalendarStatusLoading(false)
    }

    return true
  }

  async function loadDigestPreferences() {
    setIsDigestPreferencesLoading(true)

    try {
      const preferences = await preferencesApi.getDigest()
      const browserTimeZone = getBrowserTimeZone()
      setDigestPreferences({
        ...preferences,
        timezone: preferences.timezone ?? browserTimeZone,
      })
    } catch (requestError) {
      setDigestPreferences(defaultDigestPreferences())
      setError(requestError instanceof Error ? requestError.message : 'Unable to load Daily Digest settings.')
    } finally {
      setIsDigestPreferencesLoading(false)
    }
  }

  useEffect(() => {
    void loadReminderData()
    void loadRecordData()
    void loadDigestPreferences()
    void initializeCalendarStatus()
  }, [])

  async function updateDigestPreferences(
    input: DigestPreferencesUpdate,
    options: { showNotice?: boolean } = {},
  ) {
    setIsSavingDigestPreferences(true)
    setError(null)
    if (options.showNotice) {
      setNotice(null)
    }

    try {
      const updated = await preferencesApi.updateDigest({
        timezone: digestPreferences.timezone ?? getBrowserTimeZone(),
        ...input,
      })
      setDigestPreferences({
        ...updated,
        timezone: updated.timezone ?? getBrowserTimeZone(),
      })
      if (options.showNotice) {
        setNotice('Daily Digest settings saved.')
      }
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to save Daily Digest settings.')
      return false
    } finally {
      setIsSavingDigestPreferences(false)
    }
  }

  async function handleCreate(input: ReminderInput) {
    setIsSaving(true)
    setError(null)
    setNotice(null)

    try {
      const created = await remindersApi.create(input, undefined, responsibilityRecordId ?? undefined)
      if (responsibilityRecordId) {
        try {
          await linkedItemsApi.createRecordLink(responsibilityRecordId, {
            target_type: 'reminder',
            target_id: created.id,
            relationship_type: 'reminder_for',
          })
          setNotice('Responsibility added to this item.')
        } catch {
          setError('The reminder was added, but LifeLedger could not connect it to this item. You can add it from Related items.')
        }
      }
      await loadReminderData()
      setResponsibilityRecordId(null)
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to create reminder.')
      return false
    } finally {
      setIsSaving(false)
    }
  }

  async function handleComplete(id: string) {
    setError(null)
    setNotice(null)
    const reminder = reminders.find((item) => item.id === id)
    if (!reminder) {
      setError('Unable to find this responsibility.')
      return
    }
    setLifecycleAction({ action: 'complete', reminder })
  }

  async function handleSnoozeReminder(id: string, snoozedUntil: string) {
    if (pendingReminderActionId === id) {
      return false
    }

    setPendingReminderActionId(id)
    setError(null)
    setNotice(null)

    try {
      const updated = await remindersApi.snooze(id, snoozedUntil)
      replaceReminder(updated)
      await loadReminderData()
      setNotice('Reminder snoozed.')
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to snooze reminder.')
      return false
    } finally {
      setPendingReminderActionId(null)
    }
  }

  async function handleClearReminderSnooze(id: string) {
    if (pendingReminderActionId === id) {
      return false
    }

    setPendingReminderActionId(id)
    setError(null)
    setNotice(null)

    try {
      const updated = await remindersApi.clearSnooze(id)
      replaceReminder(updated)
      await loadReminderData()
      setNotice('Snooze cleared.')
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to clear snooze.')
      return false
    } finally {
      setPendingReminderActionId(null)
    }
  }

  async function handleRenewReminder(id: string, _newDueDate: string) {
    setError(null)
    setNotice(null)
    const reminder = reminders.find((item) => item.id === id)
    if (!reminder) {
      setError('Unable to find this responsibility.')
      return false
    }
    setLifecycleAction({ action: 'renew', reminder })
    return true
  }

  async function handleReopenReminder(id: string, occurrenceId: string | null) {
    if (pendingReminderActionId === id) return false
    setPendingReminderActionId(id)
    setError(null)
    setNotice(null)
    try {
      const updated = await remindersApi.reopen(id, occurrenceId, crypto.randomUUID())
      replaceReminder(updated)
      await loadReminderData()
      setNotice('Responsibility reopened. Earlier completion history is unchanged.')
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to reopen responsibility.')
      return false
    } finally {
      setPendingReminderActionId(null)
    }
  }

  async function handleLifecycleSaved(updated: Reminder, message: string) {
    replaceReminder(updated)
    setLifecycleAction(null)
    setNotice(message)
    setError(null)
    await Promise.all([loadReminderData(), loadRecordData()])
  }

  async function handleUpdate(id: string, input: ReminderInput) {
    setIsSaving(true)
    setError(null)
    setNotice(null)

    try {
      await remindersApi.update(id, input)
      await loadReminderData()
      setNotice('Reminder updated.')
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to update reminder.')
      return false
    } finally {
      setIsSaving(false)
    }
  }

  async function handleCreateRecord(
    input: RecordInput,
    protectedInput: ProtectedRecordInput,
    files: File[] = [],
    links: LinkCreateRequest[] = [],
    workflowId: string,
    details: DynamicRecordFieldInput[] = [],
  ): Promise<RecordCreationResult> {
    setIsSaving(true)
    setError(null)
    setNotice(null)

    try {
      let progress = recordCreationProgressRef.current.get(workflowId)
      if (!progress) {
        const created = await recordsApi.create(input, workflowId)
        progress = {
          record: created,
          protectedSaved: false,
          successfulFiles: new Set(),
          successfulLinks: new Set(),
          successfulDetails: new Set(),
        }
        recordCreationProgressRef.current.set(workflowId, progress)
      } else {
        progress.record = await recordsApi.update(progress.record.id, input)
      }

      let nextRecord = progress.record
      const setupAttempt = await runRecordSetupAttempt(
        nextRecord.id,
        protectedInput,
        files,
        links,
        progress,
        {
          saveProtected: recordsApi.setProtected,
          uploadFile: recordsApi.uploadRecordAttachment,
          createLink: linkedItemsApi.createRecordLink,
          addDetail: recordsApi.addField,
        },
        details,
      )
      const { detailFailures, failedFiles, latestRecord, linkFailures, protectedFailed, protectedStatus } = setupAttempt
      if (latestRecord) {
        nextRecord = latestRecord
        progress.record = latestRecord
      }
      if (protectedStatus) {
        nextRecord = withProtectedStatus(nextRecord, protectedStatus)
        progress.record = nextRecord
      }

      recordCreationProgressRef.current.set(workflowId, progress)
      await Promise.all([loadRecordData(), loadReminderData()])
      const incomplete = protectedFailed || detailFailures > 0 || failedFiles.length > 0 || linkFailures > 0
      if (incomplete) {
        const failures = [
          protectedFailed ? 'protected details were not saved' : null,
          detailFailures ? `${detailFailures} detail${detailFailures === 1 ? '' : 's'} could not be saved` : null,
          failedFiles.length ? `${failedFiles.length} document${failedFiles.length === 1 ? '' : 's'} could not be uploaded` : null,
          linkFailures ? `${linkFailures} related item${linkFailures === 1 ? '' : 's'} could not be saved` : null,
        ].filter(Boolean).join('; ')
        return {
          complete: false,
          recordId: nextRecord.id,
          message: `${nextRecord.title} was created, but ${failures}. Retry the unfinished setup now or finish it later.`,
          stages: [
            { label: 'Item', status: 'saved' },
            { label: 'Protected details', status: !hasProtectedRecordInput(protectedInput) ? 'not_included' : progress.protectedSaved ? 'saved' : 'needs_retry' },
            { label: 'Details', status: details.length === 0 ? 'not_included' : detailFailures === 0 ? 'saved' : 'needs_retry' },
            { label: 'Documents', status: files.length === 0 ? 'not_included' : failedFiles.length === 0 ? 'saved' : 'needs_retry' },
            { label: 'Related items', status: links.length === 0 ? 'not_included' : linkFailures === 0 ? 'saved' : 'needs_retry' },
          ],
        }
      }

      recordCreationProgressRef.current.delete(workflowId)
      setActivePage('records')
      setRecordBackStack([])
      setViewingRecord({ record: nextRecord, initialTab: links.length > 0 ? 'linkedItems' : 'details' })
      setNotice(files.length || links.length || details.length || hasProtectedRecordInput(protectedInput) ? 'Item and setup details saved.' : 'Item added. Add a document when ready.')
      return { complete: true, recordId: nextRecord.id, message: null }
    } catch (requestError) {
      const createdRecordId = recordCreationProgressRef.current.get(workflowId)?.record.id ?? null
      return {
        complete: false,
        recordId: createdRecordId,
        message: createdRecordId
          ? 'The item was created, but LifeLedger could not continue setup. Retry now or finish it later.'
          : requestError instanceof Error ? requestError.message : 'LifeLedger could not create the item. Try again.',
        stages: [{ label: 'Item', status: createdRecordId ? 'saved' : 'needs_retry' }],
      }
    } finally {
      setIsSaving(false)
    }
  }
  async function handleUpdateRecord(id: string, input: RecordInput, protectedInput: ProtectedRecordInput) {
    setIsSaving(true)
    setError(null)
    setNotice(null)

    try {
      const updated = await recordsApi.update(id, input)
      let nextRecord = updated
      let protectedSaved = true
      if (Object.keys(protectedInput).length > 0) {
        try {
          const protectedStatus = await recordsApi.updateProtected(id, protectedInput)
          nextRecord = withProtectedStatus(updated, protectedStatus)
        } catch {
          protectedSaved = false
        }
      }
      await Promise.all([loadRecordData(), loadReminderData()])
      setViewingRecord((current) => (current?.record.id === id ? { ...current, record: nextRecord } : current))
      if (!protectedSaved) {
        setError('Item updated, but protected details were not saved. Protected storage may not be configured.')
      } else {
        setNotice('Item updated.')
      }
      return protectedSaved
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to update item.')
      return false
    } finally {
      setIsSaving(false)
    }
  }
  function requestDelete(reminder: Reminder) {
    setPendingDelete(reminder)
  }

  function requestRecordDelete(record: LifeRecord) {
    setPendingRecordDelete(record)
  }

  async function confirmDelete() {
    if (!pendingDelete || reminderDeleteInFlightRef.current) {
      return
    }

    const target = pendingDelete
    reminderDeleteInFlightRef.current = true
    setIsDeleting(true)
    setError(null)
    setNotice(null)

    try {
      await remindersApi.remove(target.id)
      await loadReminderData()
      setNotice('Reminder deleted.')
      setEditingReminder((current) => (current?.id === target.id ? null : current))
      setViewingReminder((current) => (current?.reminder.id === target.id ? null : current))
      setPendingDelete(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to delete reminder.')
    } finally {
      reminderDeleteInFlightRef.current = false
      setIsDeleting(false)
    }
  }

  async function handleDismissAlert(id: string) {
    setError(null)
    setNotice(null)

    try {
      await remindersApi.dismissAlert(id)
      await loadReminderData()
      setNotice('Alert dismissed for now.')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to dismiss alert.')
    }
  }

  async function handleSnoozeAlert(id: string) {
    const snoozed = await handleSnoozeReminder(id, getTomorrowMorningIso())
    if (snoozed) {
      setNotice('Reminder snoozed until tomorrow morning.')
    }
  }

  function replaceReminder(updated: Reminder) {
    setReminders((current) => current.map((item) => (item.id === updated.id ? updated : item)))
    setViewingReminder((current) => (current?.reminder.id === updated.id ? { ...current, reminder: updated } : current))
    setEditingReminder((current) => (current?.id === updated.id ? updated : current))
  }

  function replaceRecord(updated: LifeRecord) {
    setRecords((current) => current.map((item) => (item.id === updated.id ? updated : item)))
    setViewingRecord((current) => (current?.record.id === updated.id ? { ...current, record: updated } : current))
    setEditingRecord((current) => (current?.id === updated.id ? updated : current))
    setRecordBackStack((current) => current.map((item) => (item.record.id === updated.id ? { ...item, record: updated } : item)))
  }

  function handleRecordChange(updated: LifeRecord) {
    replaceRecord(updated)
    if (updated.record_type === 'person') {
      void loadReminderData()
    }
  }

  async function handleEnableCalendarSync(id: string) {
    setError(null)
    setNotice(null)

    try {
      const updated = await remindersApi.enableCalendarSync(id)
      replaceReminder(updated)
      await loadReminderData()
      setViewingReminder((current) => (current?.reminder.id === id ? { ...current, reminder: updated } : current))
      setNotice('Reminder synced to Google Calendar.')
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to sync reminder to Google Calendar.')
      return false
    }
  }

  async function handleDisableCalendarSync(id: string) {
    setError(null)
    setNotice(null)

    try {
      const updated = await remindersApi.disableCalendarSync(id)
      replaceReminder(updated)
      await loadReminderData()
      setViewingReminder((current) => (current?.reminder.id === id ? { ...current, reminder: updated } : current))
      setNotice('Google Calendar sync disabled for this reminder.')
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to disable Google Calendar sync.')
      return false
    }
  }

  function openAlertDetail(reminder: Reminder) {
    setIsAlertCenterOpen(false)
    setEditingReminder(null)
    setViewingReminder({ reminder, fromAlert: true })
  }

  function openDailyDigest() {
    const seenAt = new Date().toISOString()
    const timezone = getBrowserTimeZone()
    setIsDigestOpen(true)
    setDigestPreferences((current) => ({
      ...current,
      timezone: current.timezone ?? timezone,
      digest_last_seen_at: seenAt,
    }))
    void updateDigestPreferences({ digest_last_seen_at: seenAt, timezone })
  }

  openDailyDigestRef.current = openDailyDigest

  function openDigestReminderDetail(reminder: Reminder) {
    setIsDigestOpen(false)
    openReminderDetail(reminder)
  }

  function openDetailEdit(reminder: Reminder) {
    setViewingReminder(null)
    setEditingReminder(reminder)
  }

  function openReminderDetail(reminder: Reminder) {
    setEditingReminder(null)
    setViewingReminder({ reminder, fromAlert: false })
  }

  function openRecordDetail(record: LifeRecord) {
    setEditingRecord(null)
    setRecordBackStack([])
    setViewingRecord({ record, initialTab: 'details' })
  }

  function openLinkedRecord(recordId: string) {
    const record = records.find((item) => item.id === recordId)
    if (!record) {
      setError('Unable to open the related item. Refresh and try again.')
      return
    }

    setEditingRecord(null)
    setViewingReminder(null)
    if (viewingRecord) {
      setRecordBackStack((current) => [...current, viewingRecord])
    } else {
      setRecordBackStack([])
    }
    setViewingRecord({ record, initialTab: 'details' })
  }

  function openLinkedReminder(reminderId: string) {
    const reminder = reminders.find((item) => item.id === reminderId)
    if (!reminder) {
      setError('Unable to open linked reminder. Refresh and try again.')
      return
    }

    setViewingRecord(null)
    setRecordBackStack([])
    setEditingReminder(null)
    setViewingReminder({ reminder, fromAlert: false })
  }

  function openLinkedDocument(recordId: string, documentId: string) {
    const record = records.find((item) => item.id === recordId)
    if (!record) {
      setError('Unable to open linked document. Refresh and try again.')
      return
    }

    setEditingRecord(null)
    setViewingReminder(null)
    if (viewingRecord) {
      setRecordBackStack((current) => [...current, viewingRecord])
    } else {
      setRecordBackStack([])
    }
    setViewingRecord({ record, initialTab: 'documents', documentId: normalizeDocumentAttachmentId(recordId, documentId) })
  }

  async function openSearchRecord(recordId: string) {
    setError(null)
    try {
      const record = records.find((item) => item.id === recordId) ?? await recordsApi.get(recordId)
      setRecords((current) => (current.some((item) => item.id === record.id) ? current.map((item) => (item.id === record.id ? record : item)) : [...current, record]))
      setEditingRecord(null)
      setViewingReminder(null)
      setRecordBackStack([])
      setViewingRecord({ record, initialTab: 'details' })
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to open search result.')
    }
  }

  async function openSearchReminder(reminderId: string) {
    setError(null)
    try {
      const reminder = reminders.find((item) => item.id === reminderId) ?? await remindersApi.get(reminderId)
      setReminders((current) => (current.some((item) => item.id === reminder.id) ? current.map((item) => (item.id === reminder.id ? reminder : item)) : [...current, reminder]))
      setViewingRecord(null)
      setRecordBackStack([])
      setEditingReminder(null)
      setViewingReminder({ reminder, fromAlert: false })
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to open search result.')
    }
  }

  async function openSearchDocument(recordId: string, documentId: string) {
    setError(null)
    try {
      const record = records.find((item) => item.id === recordId) ?? await recordsApi.get(recordId)
      setRecords((current) => (current.some((item) => item.id === record.id) ? current.map((item) => (item.id === record.id ? record : item)) : [...current, record]))
      setEditingRecord(null)
      setViewingReminder(null)
      setRecordBackStack([])
      setViewingRecord({ record, initialTab: 'documents', documentId: normalizeDocumentAttachmentId(recordId, documentId) })
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to open search result.')
    }
  }

  function goBackRecordDetail() {
    const previous = recordBackStack[recordBackStack.length - 1]
    if (!previous) {
      return
    }

    setRecordBackStack((current) => current.slice(0, -1))
    setViewingRecord(previous)
  }

  async function confirmRecordDelete() {
    if (!pendingRecordDelete) {
      return
    }

    setIsDeleting(true)
    setError(null)
    setNotice(null)

    try {
      await recordsApi.remove(pendingRecordDelete.id)
      await Promise.all([loadRecordData(), loadReminderData()])
      setNotice('Item deleted.')
      setEditingRecord((current) => (current?.id === pendingRecordDelete.id ? null : current))
      setViewingRecord((current) => (current?.record.id === pendingRecordDelete.id ? null : current))
      setPendingRecordDelete(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to delete item.')
    } finally {
      setIsDeleting(false)
    }
  }

  async function handleArchiveRecord(record: LifeRecord) {
    setError(null)
    setNotice(null)

    try {
      const archived = await recordsApi.archive(record.id)
      await Promise.all([loadRecordData(), loadReminderData()])
      setViewingRecord({ record: archived, initialTab: 'details' })
      setNotice('Item archived.')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to archive item.')
    }
  }

  async function handleRestoreRecord(record: LifeRecord) {
    setError(null)
    setNotice(null)

    try {
      const restored = await recordsApi.restore(record.id)
      await Promise.all([loadRecordData(), loadReminderData()])
      setViewingRecord({ record: restored, initialTab: 'details' })
      setNotice('Item restored.')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to restore item.')
    }
  }

  function handleProtectedRecordStatusChange(id: string, protectedStatus: ProtectedRecordStatus) {
    setRecords((current) => current.map((record) => (record.id === id ? withProtectedStatus(record, protectedStatus) : record)))
    setViewingRecord((current) => (current?.record.id === id ? { ...current, record: withProtectedStatus(current.record, protectedStatus) } : current))
    setEditingRecord((current) => (current?.id === id ? withProtectedStatus(current, protectedStatus) : current))
  }

  function openAddReminder() {
    if (isAccountDeleting) return
    setResponsibilityRecordId(null)
    setAddDateContext(null)
    setEditingRecord(null)
    setIsRecordFormOpen(false)
    setIsRecordTypeSelectorOpen(false)
    setIsTemplateModalOpen(false)
    setIsReminderFormOpen(false)
    setIsAddTypeSelectorOpen(true)
  }

  function openAddReminderForDate(date: string) {
    setAddDateContext(date)
    setCalendarSelectedDate(date)
    setCalendarVisibleMonth(getMonthStartDateKey(date))
    setEditingRecord(null)
    setIsRecordFormOpen(false)
    setIsRecordTypeSelectorOpen(false)
    setIsTemplateModalOpen(false)
    setIsReminderFormOpen(false)
    setIsAddTypeSelectorOpen(true)
  }

  function closeAddTypeSelector() {
    setAddDateContext(null)
    setIsAddTypeSelectorOpen(false)
  }

  function openGuidedWorkflow(workflowId: GuidedWorkflowId, item: LifeRecord | null = null) {
    if (isAccountDeleting) return
    setResponsibilityRecordId(null)
    setAddDateContext(null)
    setEditingRecord(null)
    setViewingRecord(null)
    setRecordBackStack([])
    setIsRecordFormOpen(false)
    setIsRecordTypeSelectorOpen(false)
    setIsTemplateModalOpen(false)
    setIsReminderFormOpen(false)
    setIsAddTypeSelectorOpen(false)
    setGuidedWorkflow({ id: workflowId, item })
  }

  async function refreshGuidedWorkflowData() {
    await Promise.all([loadRecordData(), loadReminderData()])
  }

  async function openGuidedWorkflowItem(record: LifeRecord) {
    let currentRecord = record
    try {
      currentRecord = await recordsApi.get(record.id)
      setRecords((current) => current.some((item) => item.id === currentRecord.id)
        ? current.map((item) => item.id === currentRecord.id ? currentRecord : item)
        : [...current, currentRecord])
    } catch {
      setRecords((current) => current.some((item) => item.id === record.id) ? current : [...current, record])
    }
    setGuidedWorkflow(null)
    setActivePage('records')
    setRecordBackStack([])
    setViewingRecord({ record: currentRecord, initialTab: 'details' })
  }

  function openRecordTypeSelector() {
    if (isAccountDeleting) return
    setResponsibilityRecordId(null)
    setAddDateContext(null)
    setEditingRecord(null)
    setIsReminderFormOpen(false)
    setIsTemplateModalOpen(false)
    setIsAddTypeSelectorOpen(false)
    setIsRecordFormOpen(false)
    setIsRecordTypeSelectorOpen(true)
  }

  function closeRecordTypeSelector() {
    setIsRecordTypeSelectorOpen(false)
  }

  function openRecordForm(recordType: RecordType) {
    setSelectedRecordType(recordType)
    setEditingRecord(null)
    setIsRecordTypeSelectorOpen(false)
    setIsAddTypeSelectorOpen(false)
    setIsRecordFormOpen(true)
  }

  function openRecordDetailEdit(record: LifeRecord) {
    setViewingRecord(null)
    setRecordBackStack([])
    setSelectedRecordType(record.record_type)
    setEditingRecord(record)
    setIsRecordFormOpen(true)
  }

  function closeRecordForm() {
    setIsRecordFormOpen(false)
    setEditingRecord(null)
  }

  function continueRecordSetupLater(recordId: string) {
    const progress = [...recordCreationProgressRef.current.values()].find((item) => item.record.id === recordId)
    setActivePage('records')
    setRecordBackStack([])
    if (progress) {
      setViewingRecord({ record: progress.record, initialTab: 'details' })
    }
  }

  function closeAddReminder() {
    setResponsibilityRecordId(null)
    setAddDateContext(null)
    setIsReminderFormOpen(false)
    setTemplateDraft(null)
  }

  function openGenericReminderForm(
    input = createGenericReminderInput(getDateOverride(addDateContext)),
    preserveResponsibilityContext = false,
  ) {
    if (!preserveResponsibilityContext) setResponsibilityRecordId(null)
    setTemplateDraft({ id: `${input.title || input.reminder_type}-${input.due_date}-${Date.now()}`, input })
    setAddDateContext(null)
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }

  function openBirthdayReminderForm(
    input = createBirthdayReminderInput(getBirthdayDateOverride(addDateContext)),
    preserveResponsibilityContext = false,
  ) {
    if (!preserveResponsibilityContext) setResponsibilityRecordId(null)
    setTemplateDraft({ id: `${input.title}-${Date.now()}`, input })
    setAddDateContext(null)
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }

  function openRenewalReminderForm(
    input = createRenewalReminderInput(getRenewalDateOverride(addDateContext)),
    preserveResponsibilityContext = false,
  ) {
    if (!preserveResponsibilityContext) setResponsibilityRecordId(null)
    setTemplateDraft({ id: `${input.title}-${Date.now()}`, input })
    setAddDateContext(null)
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }

  function openMaintenanceReminderForm(
    input = createMaintenanceReminderInput(getMaintenanceDateOverride(addDateContext)),
    preserveResponsibilityContext = false,
  ) {
    if (!preserveResponsibilityContext) setResponsibilityRecordId(null)
    setTemplateDraft({ id: `${input.title}-${Date.now()}`, input })
    setAddDateContext(null)
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }

  function openResponsibilityForRecord(record: LifeRecord, suggestion?: SuggestedResponsibilityDefinition) {
    const reminderOffset = suggestion?.defaultReminderOffsets[0]
    const commonOverrides: Partial<ReminderInput> = {
      title: suggestion?.label ?? '',
      ...(reminderOffset ? {
        reminder_lead_value: reminderOffset.value,
        reminder_lead_unit: reminderOffset.unit,
      } : {}),
    }
    let input: ReminderInput

    if (suggestion?.type === 'renewal') {
      const relevantDate = record.renewal_date ?? record.expiration_date ?? getDateKey(new Date())
      input = createRenewalReminderInput({
        ...commonOverrides,
        due_date: relevantDate,
        renewal_details: {
          ...emptyRenewalDetails(),
          item_name: record.title,
          provider: record.provider_or_brand,
          renewal_date: record.renewal_date ?? relevantDate,
          expiration_date: record.expiration_date,
        },
      })
    } else if (suggestion?.type === 'maintenance') {
      const relevantDate = getDateKey(new Date())
      input = createMaintenanceReminderInput({
        ...commonOverrides,
        due_date: relevantDate,
        maintenance_details: {
          ...emptyMaintenanceDetails(),
          item_name: record.title,
          maintenance_area: getMaintenanceAreaForRecord(record.record_type),
          next_due_date: relevantDate,
        },
      })
    } else {
      input = createGenericReminderInput(commonOverrides)
    }

    setResponsibilityRecordId(record.id)
    setTemplateDraft({ id: `responsibility-${record.id}-${Date.now()}`, input })
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }

  function openTemplates() {
    setAddDateContext(null)
    setIsReminderFormOpen(false)
    setIsTemplateModalOpen(true)
  }

  function handleStartBlank() {
    setTemplateDraft(null)
    setIsReminderFormOpen(true)
  }

  function handleUseTemplate(input: ReminderInput) {
    const preserveResponsibilityContext = responsibilityRecordId !== null

    if (input.reminder_type === 'birthday') {
      openBirthdayReminderForm(input, preserveResponsibilityContext)
      return
    }

    if (input.reminder_type === 'renewal') {
      openRenewalReminderForm(input, preserveResponsibilityContext)
      return
    }

    if (input.reminder_type === 'maintenance') {
      openMaintenanceReminderForm(input, preserveResponsibilityContext)
      return
    }

    openGenericReminderForm(input, preserveResponsibilityContext)
  }

  function showPage(page: AppPage) {
    if (page !== 'records') {
      setViewingRecord(null)
    }
    setActivePage(page)
    document.getElementById('app-top')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function showCalendar(targetDate?: string | null) {
    if (targetDate) {
      setCalendarSelectedDate(targetDate)
      setCalendarVisibleMonth(getMonthStartDateKey(targetDate))
    }

    showPage('calendar')
  }

  function getNavClass(page: AppPage) {
    return activePage === page ? 'active' : undefined
  }


  useEffect(() => {
    if (didHandleDigestUrl.current || window.location.search.length === 0) {
      return
    }

    const params = new URLSearchParams(window.location.search)
    if (params.get('openDigest') !== '1') {
      return
    }

    didHandleDigestUrl.current = true
    setActivePage('home')
    openDailyDigestRef.current()
    params.delete('openDigest')
    const nextSearch = params.toString()
    const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ''}${window.location.hash}`
    window.history.replaceState(null, '', nextUrl || '/')
  }, [setActivePage])
  const attentionCount = alerts.length
  const dailyDigest = buildDailyDigest(reminders, alerts, { lookaheadDays: digestPreferences.digest_lookahead_days })
  const activeRecordsCount = records.filter((record) => record.status !== 'archived').length
  const displayName = getUserDisplayName(userLabel)
  const pageTitle = getPageTitle(activePage)
  const useBrandHeader = activePage === 'home' || activePage === 'calendar'

  return (
    <Suspense fallback={<main className="app-loading" role="status">Loading feature…</main>}>
      <>
      <main className="app-shell" id="app-top">
        <header className="app-header app-header-main">
          <button
            type="button"
            className={`icon-button header-calendar-button ${activePage === 'calendar' ? 'active' : ''}`.trim()}
            onClick={() => showCalendar()}
            aria-current={activePage === 'calendar' ? 'page' : undefined}
            aria-label={activePage === 'calendar' ? 'Calendar open' : 'Open calendar'}
          >
            <CalendarDays size={20} aria-hidden="true" />
          </button>

          <h1 className={useBrandHeader ? 'app-title app-title-brand' : 'app-title'}>
            {useBrandHeader ? (
              <span className="app-title-logo" aria-hidden="true">
                <CheckCircle size={14} />
              </span>
            ) : null}
            <span>{useBrandHeader ? 'LifeLedger' : pageTitle}</span>
          </h1>

          <div className="header-actions header-main-actions">
            <button
              type="button"
              className={`icon-button header-inbox-button ${activePage === 'inbox' ? 'active' : ''}`.trim()}
              onClick={() => showPage('inbox')}
              aria-current={activePage === 'inbox' ? 'page' : undefined}
              aria-label={activePage === 'inbox' ? 'Capture Inbox open' : 'Open Capture Inbox'}
            >
              <Inbox size={19} aria-hidden="true" />
            </button>
            <button
              type="button"
              className={`icon-button header-search-button ${activePage === 'search' ? 'active' : ''}`.trim()}
              onClick={() => showPage('search')}
              aria-current={activePage === 'search' ? 'page' : undefined}
              aria-label={activePage === 'search' ? 'Search open' : 'Open search'}
            >
              <Search size={19} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="icon-button header-notification-button"
              onClick={() => setIsAlertCenterOpen(true)}
              aria-label="Open alerts"
            >
              <Bell size={19} aria-hidden="true" />
              {attentionCount > 0 ? (
                <span className="notification-badge" aria-label={`${attentionCount} reminders need attention`}>
                  {attentionCount > 9 ? '9+' : attentionCount}
                </span>
              ) : null}
            </button>
          </div>
        </header>

      {error ? (
        <div className="alert" role="alert">
          <AlertCircle size={18} aria-hidden="true" />
          <span>{error}</span>
          <button type="button" className="message-dismiss-button" onClick={() => setError(null)} aria-label="Dismiss message">
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      ) : null}

      {notice ? (
        <div className="notice" role="status">
          <CheckCircle2 size={18} aria-hidden="true" />
          <span>{notice}</span>
          <button type="button" className="message-dismiss-button" onClick={() => setNotice(null)} aria-label="Dismiss message">
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      ) : null}

      {activePage === 'home' ? (
        <HomeDashboard
          reminders={reminders}
          alerts={alerts}
          digest={dailyDigest}
          digestPreferences={digestPreferences}
          isLoading={isLoading}
          recordsCount={activeRecordsCount}
          userName={displayName}
          onAddRecord={openRecordTypeSelector}
          onAddReminder={openAddReminder}
          onBrowseTemplates={openTemplates}
          onViewReminders={() => showPage('reminders')}
          onViewCalendar={showCalendar}
          onViewAlerts={() => setIsAlertCenterOpen(true)}
          onOpenDigest={openDailyDigest}
          onViewRecords={() => showPage('records')}
          onViewReminder={openReminderDetail}
          onStartWorkflow={(workflowId) => openGuidedWorkflow(workflowId)}
          onCapture={(detail) => { setInitialCaptureDetail(detail); showPage('inbox') }}
        />
      ) : null}

      {activePage === 'calendar' ? (
        <CalendarView
          reminders={reminders}
          isLoading={isLoading}
          selectedDate={calendarSelectedDate}
          visibleMonth={calendarVisibleMonth}
          onAddForDate={openAddReminderForDate}
          onSelectedDateChange={setCalendarSelectedDate}
          onViewReminder={openReminderDetail}
          onVisibleMonthChange={setCalendarVisibleMonth}
        />
      ) : null}

      {activePage === 'search' ? (
        <SearchView
          records={records}
          onViewRecord={(recordId) => void openSearchRecord(recordId)}
          onViewReminder={(reminderId) => void openSearchReminder(reminderId)}
          onViewDocument={(recordId, documentId) => void openSearchDocument(recordId, documentId)}
        />
      ) : null}

      {activePage === 'inbox' ? (
        <CaptureInbox
          initialDetail={initialCaptureDetail}
          onDataChanged={() => { void loadReminderData(); void loadRecordData() }}
          onManualOrganize={openAddReminder}
          onOpenResult={(actionType, entityId) => {
            if (['create_item', 'update_item_detail', 'add_safe_note'].includes(actionType)) void openSearchRecord(entityId)
            if (['create_responsibility', 'complete_responsibility', 'renew_responsibility', 'snooze_responsibility'].includes(actionType)) void openSearchReminder(entityId)
          }}
        />
      ) : null}

      {activePage === 'reminders' ? (
        <>
          <Dashboard
            reminders={reminders}
            activeStatusFilter={reminderStatusFilter}
            activeTypeFilter={reminderTypeFilter}
            onStatusFilterChange={setReminderStatusFilter}
          />

          <section className="workspace" id="reminders-section">
            <ReminderList
              reminders={reminders}
              isLoading={isLoading}
              activeStatusFilter={reminderStatusFilter}
              activeTypeFilter={reminderTypeFilter}
              onStatusFilterChange={setReminderStatusFilter}
              onTypeFilterChange={setReminderTypeFilter}
              onComplete={handleComplete}
              onDelete={requestDelete}
              onEdit={openDetailEdit}
              onView={openReminderDetail}
              onBrowseTemplates={openTemplates}
              onAddReminder={openAddReminder}
              pendingActionId={pendingReminderActionId}
            />
          </section>

          <div className="privacy-note">
            <ShieldCheck size={24} aria-hidden="true" />
            <div>
              <strong>Signed-in access protects your LifeLedger account.</strong>
              <span>Standard details are available to the authenticated application backend; protected details add encryption before storage.</span>
            </div>
          </div>
        </>
      ) : null}

      {activePage === 'records' ? (
        <RecordsView
          activeFilter={recordFilter}
          isLoading={isRecordsLoading}
          records={records}
          showArchived={showArchivedRecords}
          onAddRecord={openRecordTypeSelector}
          onFilterChange={setRecordFilter}
          onShowArchivedChange={setShowArchivedRecords}
          onViewRecord={openRecordDetail}
        />
      ) : null}

        {activePage === 'settings' ? (
          <SettingsView
            calendarStatus={calendarStatus}
            calendarStatusError={calendarStatusError}
            digestPreferences={digestPreferences}
            isDigestPreferencesLoading={isDigestPreferencesLoading}
            isCalendarStatusLoading={isCalendarStatusLoading}
            isSavingDigestPreferences={isSavingDigestPreferences}
            userLabel={userLabel}
            onSignOut={onSignOut}
            onCalendarStatusRefresh={loadCalendarStatus}
            onCalendarStatusUpdate={setCalendarStatus}
            onUpdateDigestPreferences={(input) => updateDigestPreferences(input, { showNotice: true })}
          />
        ) : null}
      </main>

      <nav className="bottom-nav" aria-label="Primary actions">
        <button type="button" className={getNavClass('home')} onClick={() => showPage('home')} aria-current={activePage === 'home' ? 'page' : undefined}>
          <Home size={19} aria-hidden="true" />
          Home
        </button>
        <button type="button" className={getNavClass('reminders')} onClick={() => showPage('reminders')} aria-current={activePage === 'reminders' ? 'page' : undefined}>
          <ListChecks size={19} aria-hidden="true" />
          Reminders
        </button>
        <button type="button" className="bottom-nav-add" disabled={isAccountDeleting} onClick={openAddReminder} aria-label={isAccountDeleting ? 'Adding is unavailable while account deletion is in progress' : 'Add item'}>
          <Plus size={28} aria-hidden="true" />
        </button>
        <button type="button" className={getNavClass('records')} onClick={() => showPage('records')} aria-current={activePage === 'records' ? 'page' : undefined}>
          <FileText size={19} aria-hidden="true" />
          {productTerms.items}
        </button>
        <button type="button" className={getNavClass('settings')} onClick={() => showPage('settings')} aria-current={activePage === 'settings' ? 'page' : undefined}>
          <Settings size={19} aria-hidden="true" />
          Settings
        </button>
      </nav>

      <ReminderForm
        isOpen={isReminderFormOpen}
        onClose={closeAddReminder}
        onCreate={handleCreate}
        isSaving={isSaving}
        onBrowseTemplates={openTemplates}
        templateDraft={templateDraft}
      />

      <AddTypeSelector
        isOpen={isAddTypeSelectorOpen}
        onChooseCapture={() => showPage('inbox')}
        onClose={closeAddTypeSelector}
        onChooseReminder={openGenericReminderForm}
        onChooseBirthday={() => openBirthdayReminderForm()}
        onChooseRenewal={() => openRenewalReminderForm()}
        onChooseMaintenance={() => openMaintenanceReminderForm()}
        onChooseItem={openRecordForm}
        onBrowseItemTypes={openRecordTypeSelector}
        onChooseWorkflow={(workflowId) => openGuidedWorkflow(workflowId)}
      />

      <GuidedWorkflowDrawer
        initialItem={guidedWorkflow?.item}
        isOpen={guidedWorkflow !== null}
        records={records}
        workflowId={guidedWorkflow?.id ?? null}
        onClose={() => setGuidedWorkflow(null)}
        onDataChanged={refreshGuidedWorkflowData}
        onOpenItem={(record) => void openGuidedWorkflowItem(record)}
      />

      <RecordTypeSelector
        isOpen={isRecordTypeSelectorOpen}
        onClose={closeRecordTypeSelector}
        onChoose={openRecordForm}
      />

      <RecordForm
        isOpen={isRecordFormOpen}
        isSaving={isSaving}
        record={editingRecord}
        records={records}
        recordType={selectedRecordType}
        reminders={reminders}
        onClose={closeRecordForm}
        onCreate={handleCreateRecord}
        onContinueLater={continueRecordSetupLater}
        onOpenRecord={openLinkedRecord}
        onOpenReminder={openLinkedReminder}
        onUpdate={handleUpdateRecord}
      />

      <LifeAdminTemplates
        isOpen={isTemplateModalOpen}
        onClose={() => setIsTemplateModalOpen(false)}
        onStartBlank={handleStartBlank}
        onUseTemplate={handleUseTemplate}
      />

      <AlertCenter
        alerts={alerts}
        isLoading={isLoading}
        isOpen={isAlertCenterOpen}
        onClose={() => setIsAlertCenterOpen(false)}
        onComplete={handleComplete}
        onDismiss={handleDismissAlert}
        onSnooze={handleSnoozeAlert}
        onView={openAlertDetail}
      />
      <DailyDigestDrawer
        digest={dailyDigest}
        isLoading={isLoading}
        isOpen={isDigestOpen}
        onClose={() => setIsDigestOpen(false)}
        onComplete={handleComplete}
        onDismiss={handleDismissAlert}
        onViewReminder={openDigestReminderDetail}
      />
      {viewingReminder ? (
        <ReminderDetailDrawer
          reminder={viewingReminder.reminder}
          records={records}
          calendarStatus={calendarStatus}
          isCalendarStatusLoading={isCalendarStatusLoading}
          isAlertEligible={viewingReminder.fromAlert || alerts.some((alert) => alert.id === viewingReminder.reminder.id)}
          onClose={() => setViewingReminder(null)}
          onClearSnooze={handleClearReminderSnooze}
          onComplete={handleComplete}
          onDisableCalendarSync={handleDisableCalendarSync}
          onEnableCalendarSync={handleEnableCalendarSync}
          onDismiss={handleDismissAlert}
          onEdit={openDetailEdit}
          onOpenLinkedDocument={openLinkedDocument}
          onOpenLinkedRecord={openLinkedRecord}
          onRenew={handleRenewReminder}
          onReopen={handleReopenReminder}
          onRequestDelete={requestDelete}
          onSnooze={handleSnoozeReminder}
          isActionPending={pendingReminderActionId === viewingReminder.reminder.id}
        />
      ) : null}
      {viewingRecord ? (
        <RecordDetailDrawer
          record={viewingRecord.record}
          records={records}
          reminders={reminders}
          canGoBack={recordBackStack.length > 0}
          initialDocumentId={viewingRecord.documentId}
          initialTab={viewingRecord.initialTab}
          onArchive={handleArchiveRecord}
          onAddResponsibility={openResponsibilityForRecord}
          onStartGuidedWorkflow={(record, workflowId) => openGuidedWorkflow(workflowId, record)}
          onBack={goBackRecordDetail}
          onClose={() => {
            setViewingRecord(null)
            setRecordBackStack([])
          }}
          onEdit={openRecordDetailEdit}
          onOpenLinkedDocument={openLinkedDocument}
          onOpenLinkedRecord={openLinkedRecord}
          onOpenLinkedReminder={openLinkedReminder}
          onProtectedStatusChange={handleProtectedRecordStatusChange}
          onRecordChange={handleRecordChange}
          onRequestDelete={requestRecordDelete}
          onRestore={handleRestoreRecord}
        />
      ) : null}
      {lifecycleAction ? (
        <LifecycleActionDrawer
          action={lifecycleAction.action}
          reminder={lifecycleAction.reminder}
          records={records}
          onClose={() => setLifecycleAction(null)}
          onSaved={(updated, message) => void handleLifecycleSaved(updated, message)}
        />
      ) : null}
      {editingReminder ? (
        <EditReminderDrawer
          reminder={editingReminder}
          isSaving={isSaving}
          onCancel={() => setEditingReminder(null)}
          onDelete={requestDelete}
          onSave={handleUpdate}
        />
      ) : null}
      <ConfirmDialog
        body={getDeleteConfirmationBody(pendingDelete)}
        confirmLabel="Delete reminder"
        isBusy={isDeleting}
        isOpen={pendingDelete !== null}
        title="Delete reminder?"
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => void confirmDelete()}
      />
      <ConfirmDialog
        body={getRecordDeleteConfirmationBody(pendingRecordDelete)}
        confirmLabel="Delete item"
        isBusy={isDeleting}
        isOpen={pendingRecordDelete !== null}
        title="Delete item?"
        onCancel={() => setPendingRecordDelete(null)}
        onConfirm={() => void confirmRecordDelete()}
      />
      </>
    </Suspense>
  )
}

function getUserDisplayName(value?: string | null) {
  const trimmedValue = value?.trim()

  if (!trimmedValue) {
    return null
  }

  const localPart = trimmedValue.includes('@') ? trimmedValue.split('@')[0] : trimmedValue
  const [firstToken] = localPart.split(/[._\s-]+/).filter(Boolean)

  if (!firstToken) {
    return null
  }

  if (firstToken.length <= 3) {
    return firstToken.toUpperCase()
  }

  return `${firstToken.charAt(0).toUpperCase()}${firstToken.slice(1)}`
}

const GOOGLE_CALENDAR_OAUTH_CALLBACK_KEY_PREFIX = 'google-calendar-oauth-callback:'

function normalizeDocumentAttachmentId(recordId: string, documentId: string): string {
  const prefix = `${recordId}#`
  return documentId.startsWith(prefix) ? documentId.slice(prefix.length) : documentId
}
function clearGoogleOAuthUrlParams(params: URLSearchParams) {
  for (const key of ['code', 'state', 'scope', 'authuser', 'prompt', 'error', 'error_description']) {
    params.delete(key)
  }

  const nextSearch = params.toString()
  const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ''}${window.location.hash}`
  window.history.replaceState(null, '', nextUrl || '/')
}

function hasProcessedGoogleOAuthCallbackState(state: string) {
  try {
    return window.sessionStorage.getItem(getGoogleOAuthCallbackStorageKey(state)) !== null
  } catch {
    return false
  }
}

function markGoogleOAuthCallbackStateProcessed(state: string) {
  try {
    window.sessionStorage.setItem(getGoogleOAuthCallbackStorageKey(state), String(Date.now()))
  } catch {
    // URL clearing still prevents ordinary remount duplication when sessionStorage is unavailable.
  }
}

function getGoogleOAuthCallbackStorageKey(state: string) {
  return `${GOOGLE_CALENDAR_OAUTH_CALLBACK_KEY_PREFIX}${state}`
}

function getTomorrowMorningIso() {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  tomorrow.setHours(9, 0, 0, 0)
  return tomorrow.toISOString()
}
function getDeleteConfirmationBody(reminder: Reminder | null) {
  const name = reminder?.title.trim()

  if (name) {
    return `${name} will be permanently deleted. Related items and documents will remain, but their relationships to this reminder will be removed. This cannot be undone.`
  }

  return 'This reminder will be permanently deleted. Related items will remain, but their relationships to it will be removed. This cannot be undone.'
}

function getRecordDeleteConfirmationBody(record: LifeRecord | null) {
  const name = record?.title.trim()

  if (name) {
    return `${name}, its protected details, and its stored documents will be permanently deleted. Related reminders and items will remain, but their relationships to this item will be removed. This cannot be undone.`
  }

  return 'This item, its protected details, and its stored documents will be permanently deleted. Related items will remain, but their relationships to it will be removed. This cannot be undone.'
}

function withProtectedStatus(record: LifeRecord, protectedStatus: ProtectedRecordStatus): LifeRecord {
  return {
    ...record,
    has_protected_data: protectedStatus.has_protected_data,
    protected_field_names: protectedStatus.protected_field_names,
  }
}

function getDateOverride(date: string | null): Partial<ReminderInput> {
  return date ? { due_date: date } : {}
}

function getMaintenanceAreaForRecord(type: RecordType) {
  if (type === 'vehicle') return 'vehicle' as const
  if (type === 'pet') return 'pet' as const
  if (type === 'home' || type === 'appliance') return 'home' as const
  return 'other' as const
}

function getBirthdayDateOverride(date: string | null): Partial<ReminderInput> {
  const parsedDate = parseDateKey(date)

  if (!date || !parsedDate) {
    return {}
  }

  return {
    due_date: date,
    birthday_details: {
      ...emptyBirthdayDetails(),
      birth_month: parsedDate.getMonth() + 1,
      birth_day: parsedDate.getDate(),
    },
  }
}

function getRenewalDateOverride(date: string | null): Partial<ReminderInput> {
  if (!date) {
    return {}
  }

  return {
    due_date: date,
    renewal_details: {
      ...emptyRenewalDetails(),
      renewal_date: date,
    },
  }
}

function getMaintenanceDateOverride(date: string | null): Partial<ReminderInput> {
  if (!date) {
    return {}
  }

  return {
    due_date: date,
    maintenance_details: {
      ...emptyMaintenanceDetails(),
      next_due_date: date,
    },
  }
}

function getDateKey(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getMonthStartDateKey(value: Date | string) {
  const date = typeof value === 'string' ? parseDateKey(value) : value
  const fallbackDate = date ?? new Date()
  return getDateKey(new Date(fallbackDate.getFullYear(), fallbackDate.getMonth(), 1))
}

function parseDateKey(value: string | null | undefined) {
  if (!value || !/^\d{4}-\d{2}-\d{2}/.test(value)) {
    return null
  }

  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  const date = new Date(year, month - 1, day)

  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return null
  }

  return date
}

function getPageTitle(page: AppPage) {
  const titles: Record<AppPage, string> = {
    home: 'LifeLedger',
    search: 'Search',
    reminders: 'Reminders',
    records: productTerms.items,
    settings: 'Settings',
    calendar: 'Calendar',
    inbox: 'Capture Inbox',
  }

  return titles[page]
}

export default App
