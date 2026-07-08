/// <reference lib="webworker" />

import { clientsClaim } from 'workbox-core'
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching'

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: Array<unknown> }

interface PushPayload {
  title?: string
  body?: string
  url?: string
  tag?: string
  type?: string
}

cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)
clientsClaim()

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

self.addEventListener('push', (event) => {
  const payload = readPushPayload(event.data)
  const title = payload.title ?? 'LifeLedger Digest'

  event.waitUntil(
    self.registration.showNotification(title, {
      body: payload.body ?? 'Your Daily Digest is ready.',
      badge: '/pwa-192x192.png',
      data: {
        url: payload.url ?? '/?openDigest=1',
        type: payload.type ?? 'daily_digest',
      },
      icon: '/pwa-192x192.png',
      tag: payload.tag ?? 'daily-digest',
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const notificationData = event.notification.data as { url?: string } | undefined
  const targetUrl = new URL(notificationData?.url ?? '/?openDigest=1', self.location.origin).href

  event.waitUntil(openOrFocusClient(targetUrl))
})

function readPushPayload(data: PushMessageData | null): PushPayload {
  if (!data) {
    return {}
  }

  try {
    return data.json() as PushPayload
  } catch {
    return {}
  }
}

async function openOrFocusClient(targetUrl: string) {
  const windowClients = await self.clients.matchAll({
    includeUncontrolled: true,
    type: 'window',
  })

  for (const client of windowClients) {
    const windowClient = client as WindowClient
    if (new URL(windowClient.url).origin !== self.location.origin) {
      continue
    }

    await windowClient.focus()
    if ('navigate' in windowClient) {
      await windowClient.navigate(targetUrl)
    }
    return
  }

  await self.clients.openWindow(targetUrl)
}
