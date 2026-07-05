import { useEffect, useState } from 'react'
import { Authenticator } from '@aws-amplify/ui-react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import {
  AlertCircle,
  Bell,
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
} from 'lucide-react'

import { remindersApi } from './api/remindersApi'
import { isCognitoAuthEnabled } from './auth/config'
import { AddTypeSelector } from './components/AddTypeSelector'
import { Dashboard } from './components/Dashboard'
import { EditReminderModal } from './components/EditReminderModal'
import { HomeDashboard } from './components/HomeDashboard'
import { LifeAdminTemplates } from './components/LifeAdminTemplates'
import { ReminderForm } from './components/ReminderForm'
import type { TemplateDraft } from './components/ReminderForm'
import { ReminderList } from './components/ReminderList'
import { createBirthdayReminderInput } from './lib/reminderInput'
import { getNeedsAttention } from './lib/reminderSchedule'
import type { Reminder, ReminderInput } from './types/reminder'

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
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editingReminder, setEditingReminder] = useState<Reminder | null>(null)
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft | null>(null)
  const [activePage, setActivePage] = useState<AppPage>('home')
  const [isReminderFormOpen, setIsReminderFormOpen] = useState(false)
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false)
  const [isAddTypeSelectorOpen, setIsAddTypeSelectorOpen] = useState(false)

  async function loadReminders() {
    setIsLoading(true)
    setError(null)

    try {
      const data = await remindersApi.list()
      setReminders(data)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load reminders.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadReminders()
  }, [])

  async function handleCreate(input: ReminderInput) {
    setIsSaving(true)
    setError(null)
    setNotice(null)

    try {
      await remindersApi.create(input)
      await loadReminders()
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
      await remindersApi.complete(id)
      await loadReminders()
      setNotice(reminder?.repeat && reminder.repeat !== 'None' ? 'Moved to next due date.' : 'Reminder completed.')
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
      await loadReminders()
      setNotice('Reminder updated.')
      return true
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to update reminder.')
      return false
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete(id: string) {
    setError(null)
    setNotice(null)

    try {
      await remindersApi.remove(id)
      await loadReminders()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to delete reminder.')
    }
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

  const attentionCount = getNeedsAttention(reminders).length
  const displayName = getUserDisplayName(userLabel)
  const pageTitle = getPageTitle(activePage)

  return (
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
          onClick={() => showPage('reminders')}
          aria-label="View reminders"
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
        </div>
      ) : null}

      {notice ? (
        <div className="notice" role="status">
          <CheckCircle2 size={18} aria-hidden="true" />
          <span>{notice}</span>
        </div>
      ) : null}

      {activePage === 'home' ? (
        <HomeDashboard
          reminders={reminders}
          isLoading={isLoading}
          userName={displayName}
          onAddReminder={openAddReminder}
          onBrowseTemplates={openTemplates}
          onViewReminders={() => showPage('reminders')}
          onViewRecords={() => showPage('records')}
          onEditReminder={setEditingReminder}
        />
      ) : null}

      {activePage === 'reminders' ? (
        <>
          <Dashboard reminders={reminders} />

          <section className="workspace" id="reminders-section">
            <ReminderList
              reminders={reminders}
              isLoading={isLoading}
              onComplete={handleComplete}
              onEdit={setEditingReminder}
              onDelete={handleDelete}
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

      {activePage === 'settings' ? <SettingsView userLabel={userLabel} onSignOut={onSignOut} /> : null}

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
      />

      <LifeAdminTemplates
        isOpen={isTemplateModalOpen}
        onClose={() => setIsTemplateModalOpen(false)}
        onStartBlank={handleStartBlank}
        onUseTemplate={handleUseTemplate}
      />

      {editingReminder ? (
        <EditReminderModal
          reminder={editingReminder}
          isSaving={isSaving}
          onCancel={() => setEditingReminder(null)}
          onDelete={handleDelete}
          onSave={handleUpdate}
        />
      ) : null}
    </main>
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

function SettingsView({ userLabel, onSignOut }: { userLabel?: string | null; onSignOut?: () => void }) {
  const accountLabel = userLabel?.trim() || (isCognitoAuthEnabled ? 'Signed in' : 'Local development mode')

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

        {onSignOut ? (
          <button type="button" className="secondary-button settings-sign-out-button" onClick={onSignOut}>
            <LogOut size={17} aria-hidden="true" />
            Sign out
          </button>
        ) : null}
      </div>
    </section>
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
