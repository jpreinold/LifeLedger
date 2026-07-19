import { apiRequest as request } from './apiClient'
import type { DigestPreferences, DigestPreferencesUpdate } from '../types/preferences'

export const preferencesApi = {
  getDigest: () => request<DigestPreferences>('/preferences/digest'),

  updateDigest: (input: DigestPreferencesUpdate) =>
    request<DigestPreferences>('/preferences/digest', {
      method: 'PUT',
      body: JSON.stringify(input),
    }),
}
