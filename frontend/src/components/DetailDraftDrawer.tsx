import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, LockKeyhole } from 'lucide-react'

import { getDynamicFieldTypeLabel, getInputTypeForDynamicField, toFieldInputValue } from '../lib/fieldRendering'
import type { DynamicFieldType, DynamicFieldValue, DynamicRecordFieldInput } from '../types/record'
import { dynamicFieldTypes } from '../types/record'
import { SheetDrawer } from './SheetDrawer'

export interface DetailDraft extends DynamicRecordFieldInput {
  id: string
}

interface DetailDraftDrawerProps {
  draft?: DetailDraft | null
  isOpen: boolean
  onClose: () => void
  onSave: (detail: DetailDraft) => void
}

export function DetailDraftDrawer({ draft = null, isOpen, onClose, onSave }: DetailDraftDrawerProps) {
  const [label, setLabel] = useState('')
  const [format, setFormat] = useState<DynamicFieldType>('short_text')
  const [value, setValue] = useState<DynamicFieldValue>(null)
  const [isProtected, setIsProtected] = useState(false)
  const [choiceText, setChoiceText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const labelRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setLabel(draft?.label ?? '')
    setFormat(draft?.field_type ?? 'short_text')
    setValue(draft?.value ?? null)
    setIsProtected(draft?.is_sensitive ?? false)
    setChoiceText(draft?.select_options?.join('\n') ?? '')
    setError(null)
    window.requestAnimationFrame(() => labelRef.current?.focus())
  }, [draft, isOpen])

  const choices = useMemo(
    () => choiceText.split('\n').map((choice) => choice.trim()).filter(Boolean),
    [choiceText],
  )

  function save() {
    const normalizedLabel = label.trim()
    if (!normalizedLabel) {
      setError('Detail name is required.')
      return
    }
    if (format === 'select' && choices.length === 0) {
      setError('Add at least one choice.')
      return
    }

    onSave({
      id: draft?.id ?? crypto.randomUUID(),
      key: normalizeDetailKey(normalizedLabel),
      label: normalizedLabel,
      field_type: format,
      value: normalizeValue(format, value),
      is_sensitive: isProtected,
      select_options: format === 'select' ? choices : [],
      display_order: draft?.display_order ?? null,
    })
    onClose()
  }

  return (
    <SheetDrawer
      bodyClassName="sheet-body add-field-body"
      className="add-dialog add-field-dialog"
      closeLabel="Close detail editor"
      footer={(
        <button type="button" className="primary-button add-field-save-button" onClick={save}>
          <Check size={17} aria-hidden="true" />
          {draft ? 'Save detail' : 'Add detail'}
        </button>
      )}
      isOpen={isOpen}
      labelledBy="detail-draft-heading"
      onClose={onClose}
      subtitle="Add only what will be useful later."
      title={draft ? 'Edit detail' : 'Add another detail'}
    >
      <div className="add-field-form">
        <label>
          <span>Detail name</span>
          <input ref={labelRef} maxLength={80} value={label} onChange={(event) => setLabel(event.target.value)} placeholder="For example, membership level" />
        </label>
        <label>
          <span>Value format</span>
          <select value={format} onChange={(event) => {
            setFormat(event.target.value as DynamicFieldType)
            setValue(null)
          }}>
            {dynamicFieldTypes.map((type) => <option value={type} key={type}>{getDynamicFieldTypeLabel(type)}</option>)}
          </select>
        </label>
        {format === 'select' ? (
          <label>
            <span>Choices</span>
            <textarea rows={3} maxLength={400} value={choiceText} onChange={(event) => setChoiceText(event.target.value)} placeholder="One choice per line" />
          </label>
        ) : null}
        <DraftValueControl format={format} choices={choices} value={value} onChange={setValue} />
        <div className="field-toggle-label">
          <span>
            <strong>Protect this detail</strong>
            <small>Encrypt the value, exclude it from search, and keep it hidden until reveal.</small>
          </span>
          <button
            type="button"
            className={isProtected ? 'privacy-toggle active' : 'privacy-toggle'}
            role="switch"
            aria-label="Protect this detail"
            aria-checked={isProtected}
            onClick={() => setIsProtected((current) => !current)}
          >
            <span aria-hidden="true" />
          </button>
        </div>
        {isProtected ? (
          <p className="field-helper"><LockKeyhole size={14} aria-hidden="true" /> This value will be stored as a protected detail.</p>
        ) : null}
        {error ? <p className="field-error" role="alert">{error}</p> : null}
      </div>
    </SheetDrawer>
  )
}

export function DraftValueControl({
  choices = [],
  format,
  label = 'Value',
  placeholder,
  value,
  onChange,
}: {
  choices?: string[]
  format: DynamicFieldType
  label?: string
  placeholder?: string
  value: DynamicFieldValue
  onChange: (value: DynamicFieldValue) => void
}) {
  if (format === 'boolean') {
    return (
      <label className="field-toggle-label">
        <span><strong>{label}</strong></span>
        <input type="checkbox" checked={value === true} onChange={(event) => onChange(event.target.checked)} />
      </label>
    )
  }
  if (format === 'long_text') {
    return (
      <label>
        <span>{label}</span>
        <textarea rows={3} maxLength={1000} value={toFieldInputValue(value)} onChange={(event) => onChange(event.target.value || null)} placeholder={placeholder} />
      </label>
    )
  }
  if (format === 'select') {
    return (
      <label>
        <span>{label}</span>
        <select value={toFieldInputValue(value)} onChange={(event) => onChange(event.target.value || null)}>
          <option value="">Choose</option>
          {choices.map((choice) => <option value={choice} key={choice}>{choice}</option>)}
        </select>
      </label>
    )
  }

  return (
    <label>
      <span>{label}</span>
      <input
        type={getInputTypeForDynamicField(format)}
        step={format === 'money' ? '0.01' : undefined}
        maxLength={format === 'url' ? 500 : format === 'phone' ? 40 : 160}
        value={toFieldInputValue(value)}
        onChange={(event) => onChange(format === 'number' || format === 'money' ? event.target.value === '' ? null : Number(event.target.value) : event.target.value || null)}
        placeholder={placeholder}
      />
    </label>
  )
}

function normalizeDetailKey(label: string) {
  return label.toLocaleLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 80)
}

function normalizeValue(format: DynamicFieldType, value: DynamicFieldValue) {
  if ((format === 'number' || format === 'money') && typeof value === 'string') {
    return value.trim() ? Number(value) : null
  }
  return value
}
