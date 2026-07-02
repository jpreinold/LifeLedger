import { useEffect, useState } from 'react'
import { AlertCircle, RefreshCcw } from 'lucide-react'

import { remindersApi } from './api/remindersApi'
import { Dashboard } from './components/Dashboard'
import { ReminderForm } from './components/ReminderForm'
import { ReminderList } from './components/ReminderList'
import type { Reminder, ReminderInput } from './types/reminder'

function App() {
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

    try {
      await remindersApi.complete(id)
      await loadReminders()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to complete reminder.')
    }
  }

  async function handleDelete(id: string) {
    setError(null)

    try {
      await remindersApi.remove(id)
      await loadReminders()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to delete reminder.')
    }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">LifeLedger</p>
          <h1>Reminder Hub</h1>
        </div>
        <button type="button" className="icon-button" onClick={loadReminders} aria-label="Refresh reminders">
          <RefreshCcw size={18} aria-hidden="true" />
        </button>
      </header>

      {error ? (
        <div className="alert" role="alert">
          <AlertCircle size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      <Dashboard reminders={reminders} />

      <section className="workspace">
        <ReminderForm onCreate={handleCreate} isSaving={isSaving} />
        <ReminderList
          reminders={reminders}
          isLoading={isLoading}
          onComplete={handleComplete}
          onDelete={handleDelete}
        />
      </section>
    </main>
  )
}

export default App
