import { useEffect, useRef, useState } from 'react'
import { Authenticator } from '@aws-amplify/ui-react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import {
  AlertCircle,
  Bell,
  CalendarPlus,
  CalendarX,
  CheckCircle,
  CheckCircle2,
  FileText,
  Home,
  LogOut,
  Menu,
  Plus,
  RefreshCcw,
  ShieldCheck,
  Settings,
  X,
} from 'lucide-react'

import { calendarApi, type GoogleCalendarStatus } from './api/calendarApi'
import { remindersApi } from './api/remindersApi'
import { preferencesApi } from './api/preferencesApi'
import { pushApi, type PushStatus, type PushSubscriptionSummary } from './api/pushApi'
import { isCognitoAuthEnabled } from './auth/config'
import { AddTypeSelector } from './components/AddTypeSelector'
import { AlertCenter } from './components/AlertCenter'
import { ConfirmDialog } from './components/ConfirmDialog'
import { DailyDigestDrawer } from './components/DailyDigestDrawer'
import { Dashboard } from './components/Dashboard'
import { EditReminderModal } from './components/EditReminderModal'
import { HomeDashboard } from './components/HomeDashboard'
import { LifeAdminTemplates } from './components/LifeAdminTemplates'
import { ReminderDetailDrawer } from './components/ReminderDetailDrawer'
import { ReminderForm } from './components/ReminderForm'
import type { TemplateDraft } from './components/ReminderForm'
import { ReminderList } from './components/ReminderList'
import { buildDailyDigest } from './lib/digest'
import { formatCompletionNotice, type ReminderStatusFilter, type ReminderTypeFilter } from './lib/reminderDisplay'
import { createBirthdayReminderInput, createMaintenanceReminderInput, createRenewalReminderInput } from './lib/reminderInput'
import {
  defaultDigestPreferences,
  digestLookaheadOptions,
  getBrowserTimeZone,
  type DigestLookaheadDays,
  type DigestPreferences,
  type DigestPreferencesUpdate,
} from './types/preferences'
import type { Reminder, ReminderAlert, ReminderInput } from './types/reminder'

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

type AppPage = 'home' | 'reminders' | 'records' | 'settings'

function ReminderApp({ onSignOut, userLabel }: ReminderAppProps) {
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [alerts, setAlerts] = useState<ReminderAlert[]>([])
  const [digestPreferences, setDigestPreferences] = useState<DigestPreferences>(() => defaultDigestPreferences())
  const [calendarStatus, setCalendarStatus] = useState<GoogleCalendarStatus | null>(null)
  const [isCalendarStatusLoading, setIsCalendarStatusLoading] = useState(true)
  const [calendarStatusError, setCalendarStatusError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDigestPreferencesLoading, setIsDigestPreferencesLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isSavingDigestPreferences, setIsSavingDigestPreferences] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editingReminder, setEditingReminder] = useState<Reminder | null>(null)
  const [viewingReminder, setViewingReminder] = useState<{ reminder: Reminder; fromAlert: boolean } | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Reminder | null>(null)
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft | null>(null)
  const [activePage, setActivePage] = useState<AppPage>('home')
  const [reminderStatusFilter, setReminderStatusFilter] = useState<ReminderStatusFilter>('active')
  const [reminderTypeFilter, setReminderTypeFilter] = useState<ReminderTypeFilter>('all')
  const [isReminderFormOpen, setIsReminderFormOpen] = useState(false)
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false)
  const [isAddTypeSelectorOpen, setIsAddTypeSelectorOpen] = useState(false)
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
      await remindersApi.create(input)
      await loadReminderData()
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

    try {
      const completedReminder = await remindersApi.complete(id)
      await loadReminderData()
      setNotice(formatCompletionNotice(reminder, completedReminder))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to complete reminder.')
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

  function requestDelete(reminder: Reminder) {
    setPendingDelete(reminder)
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
    setError(null)
    setNotice(null)

    try {
      await remindersApi.snoozeAlert(id, getTomorrowMorningIso())
      await loadReminderData()
      setNotice('Reminder snoozed until tomorrow morning.')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to snooze alert.')
    }
  }

  function replaceReminder(updated: Reminder) {
    setReminders((current) => current.map((item) => (item.id === updated.id ? updated : item)))
    setViewingReminder((current) => (current?.reminder.id === updated.id ? { ...current, reminder: updated } : current))
    setEditingReminder((current) => (current?.id === updated.id ? updated : current))
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
  function openAddReminder() {
    setIsTemplateModalOpen(false)
    setIsReminderFormOpen(false)
    setIsAddTypeSelectorOpen(true)
  }

  function closeAddReminder() {
    setIsReminderFormOpen(false)
    setTemplateDraft(null)
  }

  function openGenericReminderForm() {
    setTemplateDraft(null)
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }

  function openBirthdayReminderForm(input = createBirthdayReminderInput()) {
    setTemplateDraft({ id: `${input.title}-${Date.now()}`, input })
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }

  function openRenewalReminderForm(input = createRenewalReminderInput()) {
    setTemplateDraft({ id: `${input.title}-${Date.now()}`, input })
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }

  function openMaintenanceReminderForm(input = createMaintenanceReminderInput()) {
    setTemplateDraft({ id: `${input.title}-${Date.now()}`, input })
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }
  function openTemplates() {
    setIsReminderFormOpen(false)
    setIsTemplateModalOpen(true)
  }

  function handleStartBlank() {
    setTemplateDraft(null)
    setIsReminderFormOpen(true)
  }

  function handleUseTemplate(input: ReminderInput) {
    if (input.reminder_type === 'birthday') {
      openBirthdayReminderForm(input)
      return
    }

    if (input.reminder_type === 'renewal') {
      openRenewalReminderForm(input)
      return
    }

    if (input.reminder_type === 'maintenance') {
      openMaintenanceReminderForm(input)
      return
    }

    setTemplateDraft({ id: `${input.title}-${Date.now()}`, input })
    setIsAddTypeSelectorOpen(false)
    setIsReminderFormOpen(true)
  }

  function showPage(page: AppPage) {
    setActivePage(page)
    document.getElementById('app-top')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
  const displayName = getUserDisplayName(userLabel)
  const pageTitle = getPageTitle(activePage)

  return (
    <>
      <main className="app-shell" id="app-top">
        <header className="app-header app-header-main">
        <span className="menu-glyph" aria-hidden="true">
          <Menu size={20} aria-hidden="true" />
        </span>

        <h1 className={activePage === 'home' ? 'app-title app-title-brand' : 'app-title'}>
          {activePage === 'home' ? (
            <span className="app-title-logo" aria-hidden="true">
              <CheckCircle size={14} />
            </span>
          ) : null}
          <span>{pageTitle}</span>
        </h1>

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
          userName={displayName}
          onAddReminder={openAddReminder}
          onBrowseTemplates={openTemplates}
          onViewReminders={() => showPage('reminders')}
          onViewAlerts={() => setIsAlertCenterOpen(true)}
          onOpenDigest={openDailyDigest}
          onViewRecords={() => showPage('records')}
          onViewReminder={openReminderDetail}
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
              onEdit={setEditingReminder}
              onDelete={requestDelete}
              onView={openReminderDetail}
              onBrowseTemplates={openTemplates}
              onAddReminder={openAddReminder}
            />
          </section>

          <div className="privacy-note">
            <ShieldCheck size={24} aria-hidden="true" />
            <div>
              <strong>Your data is private and secure.</strong>
              <span>We never share your information.</span>
            </div>
          </div>
        </>
      ) : null}

      {activePage === 'records' ? <RecordsView /> : null}

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
          <Bell size={19} aria-hidden="true" />
          Reminders
        </button>
        <button type="button" className="bottom-nav-add" onClick={openAddReminder} aria-label="Add reminder">
          <Plus size={28} aria-hidden="true" />
        </button>
        <button type="button" className={getNavClass('records')} onClick={() => showPage('records')} aria-current={activePage === 'records' ? 'page' : undefined}>
          <FileText size={19} aria-hidden="true" />
          Records
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
        onClose={() => setIsAddTypeSelectorOpen(false)}
        onChooseReminder={openGenericReminderForm}
        onChooseBirthday={() => openBirthdayReminderForm()}
        onChooseRenewal={() => openRenewalReminderForm()}
        onChooseMaintenance={() => openMaintenanceReminderForm()}
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
        onEdit={openAlertDetail}
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
          calendarStatus={calendarStatus}
          isCalendarStatusLoading={isCalendarStatusLoading}
          isAlertEligible={viewingReminder.fromAlert || alerts.some((alert) => alert.id === viewingReminder.reminder.id)}
          onClose={() => setViewingReminder(null)}
          onComplete={handleComplete}
          onDisableCalendarSync={handleDisableCalendarSync}
          onEnableCalendarSync={handleEnableCalendarSync}
          onDismiss={handleDismissAlert}
          onEdit={openDetailEdit}
          onRequestDelete={requestDelete}
          onSnooze={handleSnoozeAlert}
        />
      ) : null}
      {editingReminder ? (
        <EditReminderModal
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
    </>
  )
}

function RecordsView() {
  return (
    <section className="coming-soon-panel records-panel" aria-labelledby="records-heading">
      <div className="coming-soon-icon" aria-hidden="true">
        <FileText size={28} />
      </div>
      <h2 id="records-heading">Records</h2>
      <p>Secure personal records are coming soon.</p>
      <p>Soon, LifeLedger will help you organize important records, renewals, and reference details in one private place.</p>
    </section>
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
            <strong>Your reminders stay in your private LifeLedger account.</strong>
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
  const [calendarMessage, setCalendarMessage] = useState<string | null>(null)
  const [calendarError, setCalendarError] = useState<string | null>(null)
  const calendarState = getCalendarUiState(calendarStatus, isCalendarStatusLoading, calendarStatusError)
  const canConnect = Boolean(calendarStatus?.configured) && !isCalendarStatusLoading && !isWorking
  const canDisconnect = calendarStatus?.connected === true && !isCalendarStatusLoading && !isWorking
  const shouldShowConnect = calendarStatus?.configured === true && calendarStatus.connected !== true
  const shouldShowDisconnect = calendarStatus?.connected === true

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

  async function disconnectGoogleCalendar() {
    setIsWorking(true)
    setCalendarError(null)
    setCalendarMessage(null)

    try {
      await calendarApi.disconnect()
      const status = await calendarApi.getStatus()
      onCalendarStatusUpdate(status)
      setCalendarMessage('Google Calendar disconnected.')
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
          <button type="button" className="secondary-button settings-push-button" disabled={!canDisconnect} onClick={() => void disconnectGoogleCalendar()}>
            <CalendarX size={17} aria-hidden="true" />
            {isWorking ? 'Disconnecting...' : 'Disconnect Google Calendar'}
          </button>
        ) : null}
      </div>
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
      detail: 'Primary calendar sync only.',
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
      detail: 'Primary calendar',
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
          <button type="button" className="secondary-button settings-push-button" disabled={isBusy} onClick={() => void disablePushNotifications()}>
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
    return `Delete ${name}? This cannot be undone.`
  }

  return 'Are you sure you want to delete this reminder? This cannot be undone.'
}

function getPageTitle(page: AppPage) {
  const titles: Record<AppPage, string> = {
    home: 'LifeLedger',
    reminders: 'Reminders',
    records: 'Records',
    settings: 'Settings',
  }

  return titles[page]
}

export default App
