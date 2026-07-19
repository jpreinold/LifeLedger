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

export type ApiErrorCode =
  | 'deletion_in_progress'
  | 'export_in_progress'
  | 'reconciliation_required'
  | 'account_unavailable'
  | 'authentication_expired'
  | 'external_cleanup_incomplete'
  | 'export_expired'
  | 'account_operation_not_found'
  | 'unknown'

export class ApiError extends Error {
  readonly category: ApiErrorCategory
  readonly status: number | null
  readonly requestId: string | null
  readonly retryable: boolean
  readonly code: ApiErrorCode

  constructor(message: string, options: { category: ApiErrorCategory; status?: number | null; requestId?: string | null; retryable?: boolean; code?: ApiErrorCode }) {
    super(message)
    this.name = 'ApiError'
    this.category = options.category
    this.status = options.status ?? null
    this.requestId = options.requestId ?? null
    this.retryable = options.retryable ?? false
    this.code = options.code ?? 'unknown'
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
        'X-Correlation-ID': createCorrelationId(),
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
    const code = normalizeErrorCode(detail?.code, response.status)
    if (response.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('lifeledger:authentication-expired'))
    }
    throw new ApiError(detail?.message ? translateApiPresentationMessage(detail.message) : defaultMessage(category, code), {
      category,
      status: response.status,
      requestId,
      retryable: response.status === 408 || response.status === 429 || response.status >= 500,
      code,
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

async function safeErrorDetail(response: Response): Promise<{ message: string | null; code: string | null } | null> {
  try {
    const body = await response.json() as { detail?: unknown }
    if (typeof body.detail === 'string') {
      return { message: body.detail.trim() || null, code: null }
    }
    if (body.detail && typeof body.detail === 'object') {
      const detail = body.detail as { message?: unknown; code?: unknown }
      return {
        message: typeof detail.message === 'string' && detail.message.trim() ? detail.message : null,
        code: typeof detail.code === 'string' ? detail.code : null,
      }
    }
    return null
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

function defaultMessage(category: ApiErrorCategory, code: ApiErrorCode = 'unknown'): string {
  const accountMessages: Partial<Record<ApiErrorCode, string>> = {
    deletion_in_progress: 'New changes are unavailable while account deletion is in progress.',
    export_in_progress: 'An account export is already in progress.',
    reconciliation_required: 'LifeLedger needs to finish a consistency repair before this action can continue.',
    account_unavailable: 'This account is temporarily unavailable.',
    authentication_expired: 'Your session has expired. Sign in again.',
    external_cleanup_incomplete: 'External cleanup is incomplete. LifeLedger will retry safely.',
    export_expired: 'This export has expired. Request a new export.',
  }
  if (accountMessages[code]) return accountMessages[code]!
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

function normalizeErrorCode(value: string | null | undefined, status: number): ApiErrorCode {
  const known: ApiErrorCode[] = [
    'deletion_in_progress',
    'export_in_progress',
    'reconciliation_required',
    'account_unavailable',
    'authentication_expired',
    'external_cleanup_incomplete',
    'export_expired',
    'account_operation_not_found',
  ]
  if (value && known.includes(value as ApiErrorCode)) return value as ApiErrorCode
  if (status === 401) return 'authentication_expired'
  return 'unknown'
}

function createCorrelationId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`
}
