import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'

import { capturesApi } from '../../api/capturesApi'
import type { AISettingsResponse } from '../../types/capture'

export function AISettingsSection() {
  const [value, setValue] = useState<AISettingsResponse | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void capturesApi.settings()
      .then((result) => { if (active) setValue(result) })
      .catch((requestError) => { if (active) setError(requestError instanceof Error ? requestError.message : 'AI settings are unavailable.') })
    return () => { active = false }
  }, [])

  async function save(changes: Partial<AISettingsResponse['settings']>) {
    setIsSaving(true)
    setError(null)
    try { setValue(await capturesApi.updateSettings(changes)) }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'AI settings could not be saved.') }
    finally { setIsSaving(false) }
  }

  return (
    <section className="settings-digest-card ai-settings-card" aria-labelledby="ai-settings-heading">
      <div className="settings-card-header settings-digest-header">
        <div>
          <h3 id="ai-settings-heading"><Sparkles size={18} aria-hidden="true" />AI-assisted capture</h3>
          <p>Deterministic commands work first. AI is used only when needed and every change still requires review.</p>
        </div>
        <span className="settings-save-state">{isSaving ? 'Saving' : value ? 'Saved' : 'Loading'}</span>
      </div>
      {value ? <>
        <label className="settings-control-row">
          <span><strong>AI interpretation enabled</strong><small>When off, unsupported captures stay safely in the Inbox.</small></span>
          <input type="checkbox" checked={value.settings.ai_enabled} disabled={isSaving} onChange={(event) => void save({ ai_enabled: event.currentTarget.checked })} />
        </label>
        <label className="settings-control-row">
          <span><strong>Monthly budget</strong><small>Estimated spend: ${value.usage.estimated_cost_usd.toFixed(4)} · Remaining: ${value.usage.remaining_budget_usd.toFixed(4)}</small></span>
          <input type="number" min="0" max="100" step="1" value={value.settings.monthly_budget_usd} disabled={isSaving} onChange={(event) => void save({ monthly_budget_usd: Number(event.currentTarget.value) })} />
        </label>
        <label className="settings-control-row">
          <span><strong>Daily request limit</strong><small>{value.usage.daily_request_count} of {value.usage.daily_request_limit} used today</small></span>
          <input type="number" min="1" max="500" step="1" value={value.settings.daily_request_limit} disabled={isSaving} onChange={(event) => void save({ daily_request_limit: Number(event.currentTarget.value) })} />
        </label>
        <label className="settings-control-row">
          <span><strong>Try deterministic commands first</strong><small>Avoids provider calls for supported reminders and lifecycle commands.</small></span>
          <input type="checkbox" checked={value.settings.deterministic_first} disabled={isSaving} onChange={(event) => void save({ deterministic_first: event.currentTarget.checked })} />
        </label>
        <label className="settings-control-row">
          <span><strong>Allow stronger-model retry</strong><small>Allows one bounded retry only after invalid structured output.</small></span>
          <input type="checkbox" checked={value.settings.allow_model_escalation} disabled={isSaving} onChange={(event) => void save({ allow_model_escalation: event.currentTarget.checked })} />
        </label>
        <p className="settings-inline-note">Backend API usage may incur separate provider charges; a ChatGPT subscription does not include it.</p>
        {!value.provider_configured ? <p className="settings-inline-note">AI provider access is not configured. Supported deterministic captures remain available.</p> : null}
      </> : null}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
    </section>
  )
}
