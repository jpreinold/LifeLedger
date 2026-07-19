import { useState } from 'react'
import { Inbox, Sparkles } from 'lucide-react'

import { capturesApi } from '../../api/capturesApi'
import type { CaptureDetail } from '../../types/capture'

interface QuickCaptureProps {
  onCaptured: (detail: CaptureDetail) => void
  compact?: boolean
}

export function QuickCapture({ onCaptured, compact = false }: QuickCaptureProps) {
  const [text, setText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const value = text.trim()
    if (!value || isSubmitting) return
    setIsSubmitting(true)
    setError(null)
    try {
      const detail = await capturesApi.submit(value)
      setText('')
      onCaptured(detail)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'LifeLedger could not save this capture.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className={`quick-capture ${compact ? 'quick-capture-compact' : ''}`.trim()} onSubmit={(event) => void submit(event)}>
      <div className="quick-capture-heading">
        <span aria-hidden="true"><Sparkles size={18} /></span>
        <div>
          <h2>What should LifeLedger remember?</h2>
          <p>Describe what happened or what matters. You’ll review every proposed change.</p>
        </div>
      </div>
      <label className="sr-only" htmlFor={compact ? 'home-capture-text' : 'inbox-capture-text'}>Capture text</label>
      <textarea
        id={compact ? 'home-capture-text' : 'inbox-capture-text'}
        rows={compact ? 2 : 4}
        value={text}
        maxLength={4000}
        onChange={(event) => setText(event.target.value)}
        placeholder="For example: Remind me tomorrow at 4 to call Mom."
      />
      <div className="quick-capture-footer">
        <small>Don’t enter passwords, codes, payment-card details, passport numbers, full VINs, or other protected identifiers.</small>
        <div className="quick-capture-buttons">
          {text ? <button type="button" className="text-button" disabled={isSubmitting} onClick={() => { setText(''); setError(null) }}>Cancel</button> : null}
          <button type="submit" className="primary-button" disabled={!text.trim() || isSubmitting}>
            <Inbox size={16} aria-hidden="true" />
            {isSubmitting ? 'Organizing…' : 'Save to Inbox'}
          </button>
        </div>
      </div>
      {error ? <p className="form-error" role="alert">{error}</p> : null}
    </form>
  )
}
