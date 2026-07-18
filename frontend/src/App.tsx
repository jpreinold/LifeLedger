import { useEffect, useRef, useState } from 'react'
import { Authenticator } from '@aws-amplify/ui-react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import {
  AlertCircle,
  Bell,
  CalendarDays,
  CalendarPlus,
  CalendarX,
  CheckCircle,
  CheckCircle2,
  FileText,
  Home,
  LogOut,
  ListChecks,
  Plus,
  RefreshCcw,
  Search,
  ShieldCheck,
  Settings,
  X,
} from 'lucide-react'

import { calendarApi, type GoogleCalendarOption, type GoogleCalendarStatus } from './api/calendarApi'
import { linkedItemsApi } from './api/linkedItemsApi'
import { recordsApi } from './api/recordsApi'
import { remindersApi } from './api/remindersApi'
import { preferencesApi } from './api/preferencesApi'
import { pushApi, type PushStatus, type PushSubscriptionSummary } from './api/pushApi'
import { isCognitoAuthEnabled } from './auth/config'
import { AddTypeSelector } from './components/AddTypeSelector'
import { AlertCenter } from './components/AlertCenter'
import { CalendarView } from './components/CalendarView'
import { ConfirmDialog } from './components/ConfirmDialog'
import { DailyDigestDrawer } from './components/DailyDigestDrawer'
import { Dashboard } from './components/Dashboard'
import { EditReminderDrawer } from './components/EditReminderDrawer'
import { HomeDashboard } from './components/HomeDashboard'
import { GuidedWorkflowDrawer } from './components/GuidedWorkflowDrawer'
import { LifeAdminTemplates } from './components/LifeAdminTemplates'
import { RecordDetailDrawer, type RecordDetailTab } from './components/RecordDetailDrawer'
import { RecordForm, type RecordCreationResult } from './components/RecordForm'
import { RecordsView } from './components/RecordsView'
import { RecordTypeSelector } from './components/RecordTypeSelector'
import { ReminderDetailDrawer } from './components/ReminderDetailDrawer'
import { ReminderForm } from './components/ReminderForm'
import type { TemplateDraft } from './components/ReminderForm'
import { ReminderList } from './components/ReminderList'
import { SearchView } from './components/SearchView'
import { buildDailyDigest } from './lib/digest'
import { formatCompletionNotice, type ReminderStatusFilter, type ReminderTypeFilter } from './lib/reminderDisplay'
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
import type { SuggestedResponsibilityDefinition } from './lib/entityRegistry'
import { productTerms } from './lib/terminology'
import {
  defaultDigestPreferences,
  digestLookaheadOptions,
  getBrowserTimeZone,
  type DigestLookaheadDays,
  type DigestPreferences,
  type DigestPreferencesUpdate,
} from './types/preferences'
import type { Reminder, ReminderAlert, ReminderInput } from './types/reminder'
import type { DynamicRecordFieldInput, LifeRecord, ProtectedRecordInput, ProtectedRecordStatus, RecordInput, RecordType } from './types/record'
import type { LinkCreateRequest } from './types/linkedItem'
import type { RecordFilter } from './lib/recordTypes'

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

  return (
    <>
      <Authenticator hideSignUp>
        {({ signOut, user }) => (
          <ReminderApp onSignOut={signOut} userLabel={user?.signInDetails?.loginId ?? user?.username} />
        )}
      </Authenticator>
      {updateToast}
    </>
  )
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

type AppPage = 'home' | 'search' | 'reminders' | 'records' | 'settings' | 'calendar'
type ViewingRecordState = { initialTab: RecordDetailTab; record: LifeRecord; documentId?: string }
type RecordCreationProgress = {
  record: LifeRecord
  protectedSaved: boolean
  successfulFiles: Set<string>
  successfulLinks: Set<string>
  successfulDetails: Set<string>
}

function ReminderApp({ onSignOut, userLabel }: ReminderAppProps) {
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
  const [pendingDelete, setPendingDelete] = useState<Reminder | null>(null)
  const [pendingReminderActionId, setPendingReminderActionId] = useState<string | null>(null)
  const [pendingRecordDelete, setPendingRecordDelete] = useState<LifeRecord | null>(null)
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft | null>(null)
  const [activePage, setActivePage] = useState<AppPage>('home')
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
  const didHandleDigestUrl = useRef(false)
  const openDailyDigestRef = useRef<() => void>(() => undefined)

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
      const created = await remindersApi.create(input)
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
    if (pendingReminderActionId === id) {
      return
    }

    setPendingReminderActionId(id)
    setError(null)
    setNotice(null)
    const reminder = reminders.find((item) => item.id === id)

    try {
      const completedReminder = await remindersApi.complete(id)
      replaceReminder(completedReminder)
      await loadReminderData()
      setNotice(formatCompletionNotice(reminder, completedReminder))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to complete reminder.')
    } finally {
      setPendingReminderActionId(null)
    }
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

  async function handleRenewReminder(id: string, newDueDate: string) {
    if (pendingReminderActionId === id) {
      return false
    }

    setPendingReminderActionId(id)
    setError(null)
    setNotice(null)

    try {
      const updated = await remindersApi.renew(id, newDueDate)
      replaceReminder(updated)
      await loadReminderData()
      setNotice('Reminder renewed.')
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to renew reminder.')
      return false
    } finally {
      setPendingReminderActionId(null)
    }
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
      await loadRecordData()
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
      await loadRecordData()
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
    if (!pendingDelete) {
      return
    }

    setIsDeleting(true)
    setError(null)
    setNotice(null)

    try {
      await remindersApi.remove(pendingDelete.id)
      await loadReminderData()
      setNotice('Reminder deleted.')
      setEditingReminder((current) => (current?.id === pendingDelete.id ? null : current))
      setViewingReminder((current) => (current?.reminder.id === pendingDelete.id ? null : current))
      setPendingDelete(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to delete reminder.')
    } finally {
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
      await loadRecordData()
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
      await loadRecordData()
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
      await loadRecordData()
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
  }, [])
  const attentionCount = alerts.length
  const dailyDigest = buildDailyDigest(reminders, alerts, { lookaheadDays: digestPreferences.digest_lookahead_days })
  const activeRecordsCount = records.filter((record) => record.status !== 'archived').length
  const displayName = getUserDisplayName(userLabel)
  const pageTitle = getPageTitle(activePage)
  const useBrandHeader = activePage === 'home' || activePage === 'calendar'

  return (
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
        <button type="button" className="bottom-nav-add" onClick={openAddReminder} aria-label="Add item">
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
          onRecordChange={replaceRecord}
          onRequestDelete={requestRecordDelete}
          onRestore={handleRestoreRecord}
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
  )
}

function SettingsView({
  calendarStatus,
  calendarStatusError,
  digestPreferences,
  isDigestPreferencesLoading,
  isCalendarStatusLoading,
  isSavingDigestPreferences,
  userLabel,
  onSignOut,
  onCalendarStatusRefresh,
  onCalendarStatusUpdate,
  onUpdateDigestPreferences,
}: {
  calendarStatus: GoogleCalendarStatus | null
  calendarStatusError: string | null
  digestPreferences: DigestPreferences
  isDigestPreferencesLoading: boolean
  isCalendarStatusLoading: boolean
  isSavingDigestPreferences: boolean
  userLabel?: string | null
  onSignOut?: () => void
  onCalendarStatusRefresh: () => Promise<void>
  onCalendarStatusUpdate: (status: GoogleCalendarStatus) => void
  onUpdateDigestPreferences: (input: DigestPreferencesUpdate) => Promise<boolean>
}) {
  const accountLabel = userLabel?.trim() || (isCognitoAuthEnabled ? 'Signed in' : 'Local development mode')
  const controlsDisabled = isDigestPreferencesLoading || isSavingDigestPreferences

  const savedDigestEnabled = digestPreferences.digest_enabled
  const savedDigestTime = digestPreferences.digest_time
  const savedDigestLookahead = digestPreferences.digest_lookahead_days
  const [digestDraft, setDigestDraft] = useState<DigestDraft>(() => toDigestDraft(digestPreferences))

  useEffect(() => {
    setDigestDraft({
      digest_enabled: savedDigestEnabled,
      digest_time: savedDigestTime,
      digest_lookahead_days: savedDigestLookahead,
    })
  }, [savedDigestEnabled, savedDigestTime, savedDigestLookahead])

  const pendingDigestChanges = buildDigestChanges(digestPreferences, digestDraft)
  const hasUnsavedChanges = Object.keys(pendingDigestChanges).length > 0

  async function handleSaveDigestSettings() {
    if (!hasUnsavedChanges) {
      return
    }

    await onUpdateDigestPreferences(pendingDigestChanges)
  }

  function handleDiscardDigestSettings() {
    setDigestDraft(toDigestDraft(digestPreferences))
  }

  return (
    <section className="settings-view" aria-labelledby="settings-heading">
      <div className="settings-card">
        <div className="settings-card-header">
          <div className="coming-soon-icon settings-icon" aria-hidden="true">
            <Settings size={26} />
          </div>
          <div>
            <h2 id="settings-heading">Settings</h2>
            <p>Account, privacy, and app status.</p>
          </div>
        </div>

        <div className="settings-list">
          <div className="settings-row">
            <span>Account</span>
            <strong>{accountLabel}</strong>
          </div>
          <div className="settings-row">
            <span>Privacy</span>
            <strong>Reminders are scoped to your signed-in LifeLedger account and processed by the application backend.</strong>
          </div>
          <div className="settings-row">
            <span>Updates</span>
            <strong>App updates appear through the refresh prompt when available.</strong>
          </div>
        </div>

        <section className="settings-digest-card" aria-labelledby="settings-digest-heading">
          <div className="settings-card-header settings-digest-header">
            <div>
              <h3 id="settings-digest-heading">Daily Digest</h3>
              <p>Configure your in-app briefing and push schedule.</p>
            </div>
            <span className="settings-save-state">
              {isDigestPreferencesLoading
                ? 'Loading'
                : isSavingDigestPreferences
                  ? 'Saving'
                  : hasUnsavedChanges
                    ? 'Unsaved changes'
                    : 'Saved'}
            </span>
          </div>

          <label className="settings-control-row">
            <span>
              <strong>Daily Digest enabled</strong>
              <small>Controls the in-app digest and Daily Digest push eligibility.</small>
            </span>
            <input
              checked={digestDraft.digest_enabled}
              disabled={controlsDisabled}
              type="checkbox"
              onChange={(event) => {
                const digest_enabled = event.currentTarget.checked
                setDigestDraft((current) => ({ ...current, digest_enabled }))
              }}
            />
          </label>

          <label className="settings-control-row">
            <span>
              <strong>Digest time</strong>
              <small>Daily Digest push notifications use this local time.</small>
            </span>
            <input
              disabled={controlsDisabled}
              type="time"
              value={digestDraft.digest_time}
              onChange={(event) => {
                const digest_time = event.currentTarget.value
                setDigestDraft((current) => ({ ...current, digest_time }))
              }}
            />
          </label>

          <label className="settings-control-row">
            <span>
              <strong>Lookahead window</strong>
              <small>How far the digest looks for upcoming reminders.</small>
            </span>
            <select
              disabled={controlsDisabled}
              value={digestDraft.digest_lookahead_days}
              onChange={(event) => {
                const digest_lookahead_days = Number(event.currentTarget.value) as DigestLookaheadDays
                setDigestDraft((current) => ({ ...current, digest_lookahead_days }))
              }}
            >
              {digestLookaheadOptions.map((days) => (
                <option key={days} value={days}>
                  {days} days
                </option>
              ))}
            </select>
          </label>

          <div className="settings-row settings-digest-timezone-row">
            <span>Timezone</span>
            <strong>{digestPreferences.timezone ?? getBrowserTimeZone() ?? 'Detected by browser'}</strong>
          </div>
        </section>

        <GoogleCalendarSection
          calendarStatus={calendarStatus}
          calendarStatusError={calendarStatusError}
          isCalendarStatusLoading={isCalendarStatusLoading}
          onCalendarStatusRefresh={onCalendarStatusRefresh}
          onCalendarStatusUpdate={onCalendarStatusUpdate}
        />

        <PushNotificationsSection
          digestPreferences={digestPreferences}
          isDigestPreferencesLoading={isDigestPreferencesLoading}
        />

        {onSignOut ? (
          <button type="button" className="secondary-button settings-sign-out-button" onClick={onSignOut}>
            <LogOut size={17} aria-hidden="true" />
            Sign out
          </button>
        ) : null}
      </div>

      {hasUnsavedChanges ? (
        <div className="settings-save-bar" role="region" aria-label="Unsaved settings changes">
          <span className="settings-save-bar-text">You have unsaved changes</span>
          <div className="settings-save-bar-actions">
            <button
              type="button"
              className="secondary-button settings-save-bar-button"
              disabled={isSavingDigestPreferences}
              onClick={handleDiscardDigestSettings}
            >
              Discard
            </button>
            <button
              type="button"
              className="primary-button settings-save-bar-button"
              disabled={isSavingDigestPreferences}
              onClick={() => void handleSaveDigestSettings()}
            >
              {isSavingDigestPreferences ? 'Saving...' : 'Save changes'}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  )
}

interface DigestDraft {
  digest_enabled: boolean
  digest_time: string
  digest_lookahead_days: DigestLookaheadDays
}

function toDigestDraft(preferences: DigestPreferences): DigestDraft {
  return {
    digest_enabled: preferences.digest_enabled,
    digest_time: preferences.digest_time,
    digest_lookahead_days: preferences.digest_lookahead_days,
  }
}

function buildDigestChanges(saved: DigestPreferences, draft: DigestDraft): DigestPreferencesUpdate {
  const changes: DigestPreferencesUpdate = {}

  if (draft.digest_enabled !== saved.digest_enabled) {
    changes.digest_enabled = draft.digest_enabled
  }
  if (draft.digest_time !== saved.digest_time) {
    changes.digest_time = draft.digest_time
  }
  if (draft.digest_lookahead_days !== saved.digest_lookahead_days) {
    changes.digest_lookahead_days = draft.digest_lookahead_days
  }

  return changes
}


function GoogleCalendarSection({
  calendarStatus,
  calendarStatusError,
  isCalendarStatusLoading,
  onCalendarStatusRefresh,
  onCalendarStatusUpdate,
}: {
  calendarStatus: GoogleCalendarStatus | null
  calendarStatusError: string | null
  isCalendarStatusLoading: boolean
  onCalendarStatusRefresh: () => Promise<void>
  onCalendarStatusUpdate: (status: GoogleCalendarStatus) => void
}) {
  const [isWorking, setIsWorking] = useState(false)
  const [isDisconnectConfirmOpen, setIsDisconnectConfirmOpen] = useState(false)
  const [calendarOptions, setCalendarOptions] = useState<GoogleCalendarOption[]>([])
  const [selectedCalendarId, setSelectedCalendarId] = useState('')
  const [isLoadingCalendars, setIsLoadingCalendars] = useState(false)
  const [isSavingCalendar, setIsSavingCalendar] = useState(false)
  const [calendarMessage, setCalendarMessage] = useState<string | null>(null)
  const [calendarError, setCalendarError] = useState<string | null>(null)
  const onCalendarStatusRefreshRef = useRef(onCalendarStatusRefresh)
  const calendarState = getCalendarUiState(calendarStatus, isCalendarStatusLoading, calendarStatusError)
  const isCalendarPickerBusy = isLoadingCalendars || isSavingCalendar
  const canConnect = Boolean(calendarStatus?.configured) && !isCalendarStatusLoading && !isWorking && !isCalendarPickerBusy
  const canDisconnect = calendarStatus?.connected === true && !isCalendarStatusLoading && !isWorking && !isCalendarPickerBusy
  const shouldShowConnect = calendarStatus?.configured === true && calendarStatus.connected !== true
  const shouldShowDisconnect = calendarStatus?.connected === true
  const hasCalendarSelectionChanged = Boolean(selectedCalendarId && selectedCalendarId !== calendarStatus?.calendar_id)
  const canSaveCalendarSelection =
    calendarStatus?.connected === true && hasCalendarSelectionChanged && !isCalendarStatusLoading && !isWorking && !isCalendarPickerBusy

  useEffect(() => {
    onCalendarStatusRefreshRef.current = onCalendarStatusRefresh
  }, [onCalendarStatusRefresh])

  async function connectGoogleCalendar() {
    setIsWorking(true)
    setCalendarError(null)
    setCalendarMessage(null)

    try {
      const result = await calendarApi.connect()
      window.location.assign(result.authorization_url)
    } catch (requestError) {
      setCalendarError(requestError instanceof Error ? requestError.message : 'Unable to start Google Calendar connection.')
      setIsWorking(false)
    }
  }

  useEffect(() => {
    let isCancelled = false

    async function loadGoogleCalendars() {
      if (calendarStatus?.connected !== true) {
        setCalendarOptions([])
        setSelectedCalendarId('')
        setIsLoadingCalendars(false)
        return
      }

      setIsLoadingCalendars(true)
      setCalendarError(null)

      try {
        const options = await calendarApi.listCalendars()
        if (!isCancelled) {
          setCalendarOptions(options)
          setSelectedCalendarId(options.find((option) => option.selected)?.id ?? calendarStatus.calendar_id ?? options[0]?.id ?? '')
        }
      } catch (requestError) {
        if (!isCancelled) {
          setCalendarOptions([])
          setSelectedCalendarId(calendarStatus.calendar_id ?? '')
          setCalendarError(requestError instanceof Error ? requestError.message : 'Unable to load Google Calendar options.')
          await onCalendarStatusRefreshRef.current()
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingCalendars(false)
        }
      }
    }

    void loadGoogleCalendars()

    return () => {
      isCancelled = true
    }
  }, [calendarStatus?.connected, calendarStatus?.calendar_id])

  async function saveSelectedCalendar() {
    if (!canSaveCalendarSelection) {
      return
    }

    setIsSavingCalendar(true)
    setCalendarError(null)
    setCalendarMessage(null)

    try {
      const status = await calendarApi.selectCalendar({ calendar_id: selectedCalendarId })
      onCalendarStatusUpdate(status)
      setCalendarOptions((current) =>
        current.map((option) => ({
          ...option,
          selected: option.id === selectedCalendarId,
        })),
      )
      setCalendarMessage('Default Google Calendar updated.')
    } catch (requestError) {
      setCalendarError(requestError instanceof Error ? requestError.message : 'Unable to update the default Google Calendar.')
      await onCalendarStatusRefresh()
    } finally {
      setIsSavingCalendar(false)
    }
  }

  async function disconnectGoogleCalendar() {
    setIsWorking(true)
    setCalendarError(null)
    setCalendarMessage(null)

    try {
      await calendarApi.disconnect()
      const status = await calendarApi.getStatus()
      onCalendarStatusUpdate(status)
      setCalendarMessage('Google Calendar disconnected.')
      setIsDisconnectConfirmOpen(false)
    } catch (requestError) {
      setCalendarError(requestError instanceof Error ? requestError.message : 'Unable to disconnect Google Calendar.')
      await onCalendarStatusRefresh()
    } finally {
      setIsWorking(false)
    }
  }

  return (
    <section className="settings-digest-card settings-calendar-card" aria-labelledby="settings-calendar-heading">
      <div className="settings-card-header settings-digest-header">
        <div>
          <h3 id="settings-calendar-heading">Google Calendar</h3>
          <p>Sync selected LifeLedger reminders to your Google Calendar.</p>
        </div>
        <span className={`settings-push-status-pill settings-push-status-pill-${calendarState.tone}`}>
          {calendarState.label}
        </span>
      </div>

      <div className="settings-push-summary settings-calendar-summary">
        <strong>{calendarState.summary}</strong>
        <span>{calendarState.detail}</span>
      </div>

      {calendarStatus?.connected ? (
        <div className="settings-push-advanced-list settings-calendar-details" aria-label="Google Calendar connection details">
          <div className="settings-push-advanced-row">
            <span>Account</span>
            <strong>{calendarStatus.google_account_email ?? 'Google account connected'}</strong>
          </div>
          <div className="settings-push-advanced-row">
            <span>Calendar</span>
            <strong>{calendarStatus.calendar_label ?? 'Primary calendar'}</strong>
          </div>
        </div>
      ) : null}

      {calendarStatus?.connected ? (
        <div className="settings-calendar-picker">
          <label htmlFor="settings-google-calendar-select">
            <span>Default calendar</span>
            <div className="settings-calendar-select-row">
              <select
                id="settings-google-calendar-select"
                className="settings-calendar-select"
                disabled={isCalendarStatusLoading || isWorking || isCalendarPickerBusy || calendarOptions.length === 0}
                value={selectedCalendarId}
                onChange={(event) => setSelectedCalendarId(event.currentTarget.value)}
              >
                {calendarOptions.length === 0 ? (
                  <option value="">
                    {isLoadingCalendars ? 'Loading calendars...' : 'Reconnect Google Calendar to choose calendars'}
                  </option>
                ) : (
                  calendarOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.primary && option.label !== 'Primary calendar' ? `${option.label} (Primary)` : option.label}
                    </option>
                  ))
                )}
              </select>
              <button
                type="button"
                className="secondary-button settings-calendar-save-button"
                disabled={!canSaveCalendarSelection}
                onClick={() => void saveSelectedCalendar()}
              >
                {isSavingCalendar ? 'Saving...' : 'Save'}
              </button>
            </div>
          </label>
          <small>New reminder syncs use this calendar. Existing synced reminders stay where they are.</small>
        </div>
      ) : null}

      {calendarStatusError || calendarError ? (
        <div className="settings-push-error settings-push-inline-message" role="alert">
          <span>{calendarError ?? calendarStatusError}</span>
          <button type="button" className="message-dismiss-button" onClick={() => setCalendarError(null)} aria-label="Dismiss Google Calendar error">
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      ) : null}
      {calendarMessage ? (
        <div className="settings-push-message settings-push-inline-message" role="status">
          <span>{calendarMessage}</span>
          <button type="button" className="message-dismiss-button" onClick={() => setCalendarMessage(null)} aria-label="Dismiss Google Calendar message">
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      ) : null}

      <div className="settings-push-actions">
        {shouldShowConnect ? (
          <button type="button" className="primary-button settings-push-button" disabled={!canConnect} onClick={() => void connectGoogleCalendar()}>
            <CalendarPlus size={17} aria-hidden="true" />
            {isWorking ? 'Connecting...' : calendarStatus?.status === 'needs_reconnect' ? 'Reconnect Google Calendar' : 'Connect Google Calendar'}
          </button>
        ) : null}
        {shouldShowDisconnect ? (
          <button type="button" className="secondary-button settings-push-button" disabled={!canDisconnect} onClick={() => setIsDisconnectConfirmOpen(true)}>
            <CalendarX size={17} aria-hidden="true" />
            {isWorking ? 'Disconnecting...' : 'Disconnect Google Calendar'}
          </button>
        ) : null}
      </div>
      <ConfirmDialog
        body="LifeLedger will remove the saved Google authorization and stop future calendar syncs. Existing calendar events will remain, and synced reminders will be marked for attention."
        busyLabel="Disconnecting"
        confirmLabel="Disconnect Google Calendar"
        isBusy={isWorking}
        isOpen={isDisconnectConfirmOpen}
        title="Disconnect Google Calendar?"
        onCancel={() => setIsDisconnectConfirmOpen(false)}
        onConfirm={() => void disconnectGoogleCalendar()}
      />
    </section>
  )
}

function getCalendarUiState(
  calendarStatus: GoogleCalendarStatus | null,
  isLoading: boolean,
  calendarStatusError: string | null,
) {
  if (isLoading) {
    return {
      label: 'Checking',
      summary: 'Checking Google Calendar setup.',
      detail: 'Checking Calendar sync.',
      tone: 'disabled',
    }
  }

  if (calendarStatusError && !calendarStatus) {
    return {
      label: 'Error',
      summary: 'Google Calendar status is unavailable.',
      detail: 'Try again from Settings.',
      tone: 'blocked',
    }
  }

  if (!calendarStatus?.configured) {
    return {
      label: 'Not configured',
      summary: 'Calendar sync is not configured for this environment.',
      detail: 'A Google OAuth client must be configured on the backend.',
      tone: 'disabled',
    }
  }

  if (calendarStatus.connected) {
    return {
      label: 'Connected',
      summary: 'Connected',
      detail: calendarStatus.calendar_label ?? 'Selected calendar',
      tone: 'enabled',
    }
  }

  if (calendarStatus.status === 'needs_reconnect') {
    return {
      label: 'Needs reconnect',
      summary: 'Calendar sync needs attention.',
      detail: 'Reconnect Google Calendar to resume reminder sync.',
      tone: 'blocked',
    }
  }

  return {
    label: 'Not connected',
    summary: 'Connect Google Calendar',
    detail: 'Sync selected LifeLedger reminders to your Google Calendar.',
    tone: 'disabled',
  }
}


function PushNotificationsSection({
  digestPreferences,
  isDigestPreferencesLoading,
}: {
  digestPreferences: DigestPreferences
  isDigestPreferencesLoading: boolean
}) {
  const [pushStatus, setPushStatus] = useState<PushStatus | null>(null)
  const [subscriptions, setSubscriptions] = useState<PushSubscriptionSummary[]>([])
  const [permission, setPermission] = useState<NotificationPermission>(() => getNotificationPermission())
  const [isLoadingPush, setIsLoadingPush] = useState(true)
  const [isSavingPush, setIsSavingPush] = useState(false)
  const [isDisablePushConfirmOpen, setIsDisablePushConfirmOpen] = useState(false)
  const [isSendingTestPush, setIsSendingTestPush] = useState(false)
  const [pushMessage, setPushMessage] = useState<string | null>(null)
  const [pushError, setPushError] = useState<string | null>(null)
  const supportState = getPushSupportState()
  const frontendPublicKey = getVapidPublicKey()
  const activeSubscriptionCount = pushStatus?.active_subscription_count ?? subscriptions.length
  const backendConfigured = pushStatus?.configured === true
  const isCheckingConfig = isLoadingPush
  const isConfigMissing = supportState === 'supported' && !isLoadingPush && (!frontendPublicKey || pushStatus?.configured === false)
  const isEnabled = activeSubscriptionCount > 0
  const isBusy = isLoadingPush || isSavingPush || isSendingTestPush || isDigestPreferencesLoading
  const shouldShowTestPushButton =
    supportState === 'supported' && Boolean(frontendPublicKey) && backendConfigured && permission === 'granted' && isEnabled
  const canSendTestPush = shouldShowTestPushButton && !isBusy
  const pushState = getPushUiState(supportState, permission, isConfigMissing, isEnabled, isCheckingConfig)
  const advancedDetails = [
    { label: 'Browser permission', value: formatNotificationPermission(permission) },
    { label: 'Active subscriptions', value: String(activeSubscriptionCount) },
    { label: 'Last test or success', value: formatPushTimestamp(pushStatus?.last_success_at) },
    ...(pushStatus?.last_failure_at ? [{ label: 'Last failure', value: formatPushTimestamp(pushStatus.last_failure_at) }] : []),
  ]

  useEffect(() => {
    let isCancelled = false

    async function loadPushState() {
      setIsLoadingPush(true)
      setPushError(null)

      try {
        const [status, savedSubscriptions] = await Promise.all([
          pushApi.getStatus(),
          pushApi.listSubscriptions(),
        ])
        if (!isCancelled) {
          setPushStatus(status)
          setSubscriptions(savedSubscriptions)
          setPermission(getNotificationPermission())
        }
      } catch (requestError) {
        if (!isCancelled) {
          setPushStatus(toFallbackPushStatus(digestPreferences))
          setPushError(requestError instanceof Error ? requestError.message : 'Unable to load push notification settings.')
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingPush(false)
        }
      }
    }

    void loadPushState()

    return () => {
      isCancelled = true
    }
  }, [digestPreferences, supportState])

  async function enablePushNotifications() {
    setIsSavingPush(true)
    setPushError(null)
    setPushMessage(null)

    try {
      if (supportState !== 'supported') {
        throw new Error('Push notifications are not supported in this browser.')
      }
      if (!frontendPublicKey || !backendConfigured) {
        throw new Error('Push notifications are not configured for this environment.')
      }

      const nextPermission = await Notification.requestPermission()
      setPermission(nextPermission)
      if (nextPermission !== 'granted') {
        setPushMessage('Notifications are blocked in your browser settings.')
        return
      }

      const registration = await navigator.serviceWorker.ready
      let browserSubscription = await registration.pushManager.getSubscription()
      if (!browserSubscription) {
        browserSubscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(frontendPublicKey),
        })
      }

      await pushApi.saveSubscription(toPushSubscriptionInput(browserSubscription))
      const [nextStatus, savedSubscriptions] = await Promise.all([
        pushApi.getStatus(),
        pushApi.listSubscriptions(),
      ])
      setPushStatus(nextStatus)
      setSubscriptions(savedSubscriptions)
      setPushMessage('Daily Digest push notifications are enabled.')
    } catch (requestError) {
      setPushError(requestError instanceof Error ? requestError.message : 'Unable to enable push notifications.')
    } finally {
      setIsSavingPush(false)
    }
  }

  async function disablePushNotifications() {
    setIsSavingPush(true)
    setPushError(null)
    setPushMessage(null)

    try {
      if (supportState === 'supported') {
        const registration = await navigator.serviceWorker.ready
        const browserSubscription = await registration.pushManager.getSubscription()
        if (browserSubscription) {
          await browserSubscription.unsubscribe()
        }
      }

      await Promise.all(subscriptions.map((subscription) => pushApi.removeSubscription(subscription.subscription_id)))
      const [nextStatus, savedSubscriptions] = await Promise.all([
        pushApi.getStatus(),
        pushApi.listSubscriptions(),
      ])
      setPushStatus(nextStatus)
      setSubscriptions(savedSubscriptions)
      setPushMessage('Daily Digest push notifications are disabled.')
      setIsDisablePushConfirmOpen(false)
    } catch (requestError) {
      setPushError(requestError instanceof Error ? requestError.message : 'Unable to disable push notifications.')
    } finally {
      setIsSavingPush(false)
    }
  }

  async function sendTestPush() {
    setIsSendingTestPush(true)
    setPushError(null)
    setPushMessage(null)

    try {
      await pushApi.sendTestPush()
      const nextStatus = await pushApi.getStatus()
      setPushStatus(nextStatus)
      setPushMessage('Test push sent.')
    } catch (requestError) {
      setPushError(requestError instanceof Error ? requestError.message : 'Unable to send test push.')
    } finally {
      setIsSendingTestPush(false)
    }
  }

  return (
    <section className="settings-digest-card settings-push-card" aria-labelledby="settings-push-heading">
      <div className="settings-card-header settings-digest-header">
        <div>
          <h3 id="settings-push-heading">Push Notifications</h3>
          <p>Daily Digest push notifications send one summary when reminders need attention.</p>
        </div>
        <span className={`settings-push-status-pill settings-push-status-pill-${pushState.tone}`}>
          {pushState.label}
        </span>
      </div>

      <div className="settings-push-summary">
        <strong>{pushState.summary}</strong>
        <span>Uses your Daily Digest schedule.</span>
      </div>

      <p className="settings-push-note">Some browsers require LifeLedger to be installed as a PWA before push notifications can be delivered.</p>

      {pushError ? (
        <div className="settings-push-error settings-push-inline-message" role="alert">
          <span>{pushError}</span>
          <button type="button" className="message-dismiss-button" onClick={() => setPushError(null)} aria-label="Dismiss push notification error">
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      ) : null}
      {pushMessage ? (
        <div className="settings-push-message settings-push-inline-message" role="status">
          <span>{pushMessage}</span>
          <button type="button" className="message-dismiss-button" onClick={() => setPushMessage(null)} aria-label="Dismiss push notification message">
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      ) : null}

      <div className="settings-push-actions">
        {supportState === 'unsupported' || isConfigMissing ? null : isEnabled ? (
          <button type="button" className="secondary-button settings-push-button" disabled={isBusy} onClick={() => setIsDisablePushConfirmOpen(true)}>
            {isSavingPush ? 'Disabling...' : 'Disable push notifications'}
          </button>
        ) : (
          <button type="button" className="primary-button settings-push-button" disabled={isBusy || permission === 'denied'} onClick={() => void enablePushNotifications()}>
            {isSavingPush ? 'Enabling...' : 'Enable push notifications'}
          </button>
        )}
        {shouldShowTestPushButton ? (
          <button type="button" className="secondary-button settings-push-button" disabled={!canSendTestPush} onClick={() => void sendTestPush()}>
            {isSendingTestPush ? 'Sending...' : 'Send test push'}
          </button>
        ) : null}
      </div>

      <details className="settings-push-advanced">
        <summary>Advanced details</summary>
        <div className="settings-push-advanced-list">
          {advancedDetails.map((item) => (
            <div key={item.label} className="settings-push-advanced-row">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </details>
      <ConfirmDialog
        body="Push delivery will be disabled on this device and its saved push subscriptions will be removed. Your reminders and Daily Digest schedule will remain. You can enable push again later."
        busyLabel="Disabling"
        confirmLabel="Disable push notifications"
        isBusy={isSavingPush}
        isOpen={isDisablePushConfirmOpen}
        title="Disable push notifications?"
        onCancel={() => setIsDisablePushConfirmOpen(false)}
        onConfirm={() => void disablePushNotifications()}
      />
    </section>
  )
}

function getPushSupportState(): 'supported' | 'unsupported' {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    return 'unsupported'
  }

  return 'supported'
}

function getNotificationPermission(): NotificationPermission {
  if (!('Notification' in window)) {
    return 'default'
  }

  return Notification.permission
}

function getVapidPublicKey() {
  return (import.meta.env.VITE_VAPID_PUBLIC_KEY ?? '').trim()
}

function getPushUiState(
  supportState: 'supported' | 'unsupported',
  permission: NotificationPermission,
  isConfigMissing: boolean,
  isEnabled: boolean,
  isCheckingConfig: boolean,
) {
  if (supportState === 'unsupported') {
    return {
      label: 'Not supported on this browser',
      summary: 'Push notifications are not supported in this browser.',
      tone: 'disabled',
    }
  }

  if (isCheckingConfig) {
    return {
      label: 'Checking',
      summary: 'Checking push notification setup.',
      tone: 'disabled',
    }
  }

  if (isConfigMissing) {
    return {
      label: 'Not configured',
      summary: 'Push notifications are not configured for this environment.',
      tone: 'disabled',
    }
  }

  if (permission === 'denied') {
    return {
      label: 'Blocked by browser',
      summary: 'Notifications are blocked in your browser settings.',
      tone: 'blocked',
    }
  }

  if (isEnabled) {
    return {
      label: 'Enabled',
      summary: 'Daily Digest push notifications are enabled.',
      tone: 'enabled',
    }
  }

  return {
    label: 'Disabled',
    summary: 'Turn on push notifications to receive your Daily Digest when reminders need attention.',
    tone: 'disabled',
  }
}

function toFallbackPushStatus(digestPreferences: DigestPreferences): PushStatus {
  return {
    configured: false,
    active_subscription_count: 0,
    last_success_at: null,
    last_failure_at: null,
    failure_count: 0,
    digest_enabled: digestPreferences.digest_enabled,
    digest_time: digestPreferences.digest_time,
    timezone: digestPreferences.timezone,
  }
}

function formatNotificationPermission(permission: NotificationPermission) {
  if (permission === 'granted') {
    return 'Granted'
  }
  if (permission === 'denied') {
    return 'Denied'
  }

  return 'Default'
}

function formatPushTimestamp(value: string | null | undefined) {
  if (!value) {
    return 'Not recorded'
  }

  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) {
    return 'Not recorded'
  }

  return timestamp.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function toPushSubscriptionInput(subscription: PushSubscription): {
  endpoint: string
  keys: {
    p256dh: string
    auth: string
  }
  user_agent: string
} {
  const serialized = subscription.toJSON()
  const p256dh = serialized.keys?.p256dh
  const auth = serialized.keys?.auth

  if (!serialized.endpoint || !p256dh || !auth) {
    throw new Error('Browser push subscription is incomplete.')
  }

  return {
    endpoint: serialized.endpoint,
    keys: { p256dh, auth },
    user_agent: navigator.userAgent,
  }
}

function urlBase64ToUint8Array(value: string) {
  const padding = '='.repeat((4 - (value.length % 4)) % 4)
  const base64 = `${value}${padding}`.replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)

  for (let index = 0; index < rawData.length; index += 1) {
    outputArray[index] = rawData.charCodeAt(index)
  }

  return outputArray
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
  }

  return titles[page]
}

export default App
