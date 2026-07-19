import { CalendarPlus, CalendarX, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { calendarApi, type GoogleCalendarOption, type GoogleCalendarStatus } from '../../api/calendarApi'
import { ConfirmDialog } from '../../components/ConfirmDialog'

export function GoogleCalendarSection({
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
