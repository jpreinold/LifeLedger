import { getAuthorizationHeaders } from '../auth/session'
import { translateApiPresentationMessage } from '../lib/terminology'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export type ApiErrorCategory =
  | 'validation'
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'conflict'
  | 'network'
  | 'server'

export class ApiError extends Error {
  readonly category: ApiErrorCategory
  readonly status: number | null
  readonly requestId: string | null
  readonly retryable: boolean

  constructor(message: string, options: { category: ApiErrorCategory; status?: number | null; requestId?: string | null; retryable?: boolean }) {
    super(message)
    this.name = 'ApiError'
    this.category = options.category
    this.status = options.status ?? null
    this.requestId = options.requestId ?? null
    this.retryable = options.retryable ?? false
  }
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const authorizationHeaders = await getAuthorizationHeaders()
  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      cache: 'no-store',
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...authorizationHeaders,
        ...options.headers,
      },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new ApiError('LifeLedger is unavailable right now. Check your connection and try again.', {
      category: 'network',
      retryable: true,
    })
  }

  const requestId = response.headers.get('x-request-id') ?? response.headers.get('x-amzn-requestid')
  if (!response.ok) {
    const category = categoryForStatus(response.status)
    const detail = response.status < 500 ? await safeErrorDetail(response) : null
    throw new ApiError(detail ? translateApiPresentationMessage(detail) : defaultMessage(category), {
      category,
      status: response.status,
      requestId,
      retryable: response.status === 408 || response.status === 429 || response.status >= 500,
    })
  }

  if (response.status === 204) {
    return undefined as T
  }

  try {
    return await response.json() as T
  } catch {
    throw new ApiError('LifeLedger returned an unreadable response. Try again.', {
      category: 'server',
      status: response.status,
      requestId,
      retryable: true,
    })
  }
}

async function safeErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = await response.json() as { detail?: unknown }
    return typeof body.detail === 'string' && body.detail.trim() ? body.detail : null
  } catch {
    return null
  }
}

function categoryForStatus(status: number): ApiErrorCategory {
  if (status === 400 || status === 422) return 'validation'
  if (status === 401) return 'unauthorized'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'not_found'
  if (status === 409) return 'conflict'
  return 'server'
}

function defaultMessage(category: ApiErrorCategory): string {
  switch (category) {
    case 'validation': return 'Check the highlighted information and try again.'
    case 'unauthorized': return 'Your session has expired. Sign in again.'
    case 'forbidden': return 'You do not have access to this item.'
    case 'not_found': return 'This item is no longer available.'
    case 'conflict': return 'This change conflicts with an existing item.'
    case 'network': return 'LifeLedger is unavailable right now. Check your connection and try again.'
    default: return 'LifeLedger could not complete this request. Try again.'
  }
}
