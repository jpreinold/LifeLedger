import { X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { pushApi, type PushStatus, type PushSubscriptionSummary } from '../../api/pushApi'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import type { DigestPreferences } from '../../types/preferences'

export function PushNotificationsSection({
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
