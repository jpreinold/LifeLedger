import { useEffect, useState } from 'react'
import { Authenticator } from '@aws-amplify/ui-react'
import { AlertCircle, CheckCircle2, LogOut, RefreshCcw } from 'lucide-react'

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
  if (!isCognitoAuthEnabled) {
    return <ReminderApp />
  }

  return (
    <Authenticator hideSignUp>
      {({ signOut }) => <ReminderApp onSignOut={signOut} />}
    </Authenticator>
  )
}

interface ReminderAppProps {
  onSignOut?: () => void
}

function ReminderApp({ onSignOut }: ReminderAppProps) {
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editingReminder, setEditingReminder] = useState<Reminder | null>(null)
  const [templateDraft, setTemplateDraft] = useState<TemplateDraft | null>(null)
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

  function handleUseTemplate(input: ReminderInput) {
    setTemplateDraft({ id: `${input.title}-${Date.now()}`, input })

    window.requestAnimationFrame(() => {
      document.getElementById('add-reminder-heading')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      })
    })
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">LifeLedger</p>
          <h1>Reminder Hub</h1>
        </div>
        <div className="header-actions">
          <button type="button" className="icon-button" onClick={loadReminders} aria-label="Refresh reminders">
            <RefreshCcw size={18} aria-hidden="true" />
          </button>
          {onSignOut ? (
            <button type="button" className="secondary-button sign-out-button" onClick={onSignOut}>
              <LogOut size={17} aria-hidden="true" />
              Sign out
            </button>
          ) : null}
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

      <Dashboard reminders={reminders} />

      <section className="workspace">
        <ReminderForm
          onCreate={handleCreate}
          isSaving={isSaving}
          onBrowseTemplates={() => setIsTemplateModalOpen(true)}
          templateDraft={templateDraft}
        />
        <ReminderList
          reminders={reminders}
          isLoading={isLoading}
          onComplete={handleComplete}
          onEdit={setEditingReminder}
          onDelete={handleDelete}
          onBrowseTemplates={() => setIsTemplateModalOpen(true)}
        />
      </section>

      <LifeAdminTemplates
        isOpen={isTemplateModalOpen}
        onClose={() => setIsTemplateModalOpen(false)}
        onUseTemplate={handleUseTemplate}
      />

      {editingReminder ? (
        <EditReminderModal
          reminder={editingReminder}
          isSaving={isSaving}
          onCancel={() => setEditingReminder(null)}
          onSave={handleUpdate}
        />
      ) : null}
    </main>
  )
}

export default App
