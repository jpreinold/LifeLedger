export const digestLookaheadOptions = [7, 14, 30] as const

export type DigestLookaheadDays = (typeof digestLookaheadOptions)[number]

export interface DigestPreferences {
  digest_enabled: boolean
  digest_time: string
  digest_lookahead_days: DigestLookaheadDays
  timezone: string | null
  digest_last_seen_at: string | null
  updated_at: string
}

export type DigestPreferencesUpdate = Partial<
  Pick<DigestPreferences, 'digest_enabled' | 'digest_time' | 'digest_lookahead_days' | 'timezone' | 'digest_last_seen_at'>
>

export function defaultDigestPreferences(): DigestPreferences {
  return {
    digest_enabled: true,
    digest_time: '09:00',
    digest_lookahead_days: 30,
    timezone: getBrowserTimeZone(),
    digest_last_seen_at: null,
    updated_at: new Date().toISOString(),
  }
}

export function getBrowserTimeZone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || null
}
