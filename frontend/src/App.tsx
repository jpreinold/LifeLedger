import { useEffect, useState } from 'react'
import { Authenticator } from '@aws-amplify/ui-react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import {
  AlertCircle,
  Bell,
  CheckCircle2,
  Home,
  LayoutTemplate,
  LogOut,
  Menu,
  Plus,
  RefreshCcw,
  ShieldCheck,
  Settings,
} from 'lucide-react'

import { remindersApi } from './api/remindersApi'
import { isCognitoAuthEnabled } from './auth/config'
import { Dashboard } from './components/Dashboard'
import { EditReminderModal } from './components/EditReminderModal'
import { LifeAdminTemplates } from './components/LifeAdminTemplates'
import { ReminderForm } from './components/ReminderForm'
import type { TemplateDraft } from './components/ReminderForm'
import { ReminderList } from './components/ReminderList'
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
        {({ signOut }) => <ReminderApp onSignOut={signOut} />}
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
}

type AppPage = 'dashboard' | 'reminders' | 'settings'

function ReminderApp({ onSignOut }: ReminderAppProps) {
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editingReminder, setEditingReminder] = useState<Reminder | null>(null)
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft | null>(null)
  const [activePage, setActivePage] = useState<AppPage>('dashboard')
  const [isReminderFormOpen, setIsReminderFormOpen] = useState(false)
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false)

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
    setTemplateDraft(null)
    setIsReminderFormOpen(true)
  }

  function closeAddReminder() {
    setIsReminderFormOpen(false)
    setTemplateDraft(null)
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
    setTemplateDraft({ id: `${input.title}-${Date.now()}`, input })
    setIsReminderFormOpen(true)
  }

  function showPage(page: AppPage) {
    setActivePage(page)
    document.getElementById('app-top')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function getNavClass(page: AppPage) {
    return activePage === page ? 'active' : undefined
  }

  const pageTitle = activePage === 'reminders' ? 'Reminders' : activePage === 'settings' ? 'Settings' : null

  return (
    <main className="app-shell" id="app-top">
      <header className={`app-header ${pageTitle ? 'app-header-page' : 'app-header-brand'}`}>
        <span className="menu-glyph" aria-hidden="true">
          <Menu size={20} aria-hidden="true" />
        </span>

        {pageTitle ? (
          <h1 className="page-title">{pageTitle}</h1>
        ) : (
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">
              <CheckCircle2 size={28} />
            </div>
            <div>
              <h1>LifeLedger</h1>
              <p>Stay on top of life.</p>
            </div>
          </div>
        )}

        <div className="header-actions">
          <button type="button" className="icon-button refresh-button" onClick={loadReminders} aria-label="Refresh reminders">
            <RefreshCcw size={18} aria-hidden="true" />
          </button>
          <button type="button" className="icon-button primary-icon-button" onClick={openAddReminder} aria-label="Add reminder">
            <Plus size={21} aria-hidden="true" />
          </button>
        </div>
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

      {activePage === 'dashboard' ? (
        <Dashboard
          reminders={reminders}
          isLoading={isLoading}
          variant="full"
          onComplete={handleComplete}
          onEdit={setEditingReminder}
          onAddReminder={openAddReminder}
          onBrowseTemplates={openTemplates}
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

      {activePage === 'settings' ? (
        <section className="coming-soon-panel settings-panel" aria-labelledby="settings-heading">
          <div className="coming-soon-icon" aria-hidden="true">
            <Settings size={28} />
          </div>
          <h2 id="settings-heading">Settings</h2>
          <p>Account and app preferences will live here.</p>
          {onSignOut ? (
            <button type="button" className="secondary-button settings-sign-out-button" onClick={onSignOut}>
              <LogOut size={17} aria-hidden="true" />
              Sign out
            </button>
          ) : null}
        </section>
      ) : null}

      <nav className="bottom-nav" aria-label="Primary actions">
        <button type="button" className={!isTemplateModalOpen ? getNavClass('dashboard') : undefined} onClick={() => showPage('dashboard')} aria-current={activePage === 'dashboard' && !isTemplateModalOpen ? 'page' : undefined}>
          <Home size={19} aria-hidden="true" />
          Dashboard
        </button>
        <button type="button" className={!isTemplateModalOpen ? getNavClass('reminders') : undefined} onClick={() => showPage('reminders')} aria-current={activePage === 'reminders' && !isTemplateModalOpen ? 'page' : undefined}>
          <Bell size={19} aria-hidden="true" />
          Reminders
        </button>
        <button type="button" className={isTemplateModalOpen ? 'active' : undefined} onClick={openTemplates}>
          <LayoutTemplate size={19} aria-hidden="true" />
          Templates
        </button>
        <button type="button" className={!isTemplateModalOpen ? getNavClass('settings') : undefined} onClick={() => showPage('settings')} aria-current={activePage === 'settings' && !isTemplateModalOpen ? 'page' : undefined}>
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

export default App
