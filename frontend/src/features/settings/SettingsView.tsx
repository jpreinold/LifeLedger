import { LogOut, Settings } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { GoogleCalendarStatus } from '../../api/calendarApi'
import { isCognitoAuthEnabled } from '../../auth/config'
import { AccountDataSection } from '../account/AccountDataSection'
import {
  digestLookaheadOptions,
  getBrowserTimeZone,
  type DigestLookaheadDays,
  type DigestPreferences,
  type DigestPreferencesUpdate,
} from '../../types/preferences'
import { GoogleCalendarSection } from './GoogleCalendarSection'
import { PushNotificationsSection } from './PushNotificationsSection'
import { AISettingsSection } from './AISettingsSection'

export function SettingsView({
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

        <AISettingsSection />

        <PushNotificationsSection
          digestPreferences={digestPreferences}
          isDigestPreferencesLoading={isDigestPreferencesLoading}
        />

        <AccountDataSection onAccountDeleted={onSignOut} />

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
