export async function onRequestPost({ request }: { request: Request }) {
  try {
    await request.text()
  } catch {
    // CSP reports are best-effort telemetry; malformed bodies should not affect clients.
  }

  return new Response(null, {
    status: 204,
    headers: {
      'Cache-Control': 'no-store',
    },
  })
}

export function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      Allow: 'POST, OPTIONS',
    },
  })
}

export function onRequest() {
  return new Response(null, {
    status: 405,
    headers: {
      Allow: 'POST, OPTIONS',
    },
  })
}
