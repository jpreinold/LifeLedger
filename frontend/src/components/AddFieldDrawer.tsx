import { useEffect, useMemo, useRef, useState } from 'react'
import type { MutableRefObject, RefObject } from 'react'
import { ArrowLeft, Check, ListPlus, LockKeyhole, Plus, Type, X } from 'lucide-react'

import { recordsApi } from '../api/recordsApi'
import { getDynamicFieldTypeLabel, getInputTypeForDynamicField, toFieldInputValue } from '../lib/fieldRendering'
import type { DynamicFieldPreset } from '../lib/recordTypes'
import type { DynamicFieldType, DynamicFieldValue, LifeRecord } from '../types/record'
import { dynamicFieldTypes } from '../types/record'
import { SheetDrawer } from './SheetDrawer'

interface AddFieldDrawerProps {
  isOpen: boolean
  record: LifeRecord
  suggestedFields: DynamicFieldPreset[]
  onClose: () => void
  onSaved: (record: LifeRecord) => void
}

type Mode = 'suggested' | 'custom'

export function AddFieldDrawer({ isOpen, record, suggestedFields, onClose, onSaved }: AddFieldDrawerProps) {
  const [mode, setMode] = useState<Mode>('suggested')
  const [selectedPreset, setSelectedPreset] = useState<DynamicFieldPreset | null>(null)
  const [customLabel, setCustomLabel] = useState('')
  const [customType, setCustomType] = useState<DynamicFieldType>('short_text')
  const [customSensitive, setCustomSensitive] = useState(false)
  const [value, setValue] = useState<DynamicFieldValue>(null)
  const [selectOptionsText, setSelectOptionsText] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const firstInputRef = useRef<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setMode('suggested')
      setSelectedPreset(null)
      setCustomLabel('')
      setCustomType('short_text')
      setCustomSensitive(false)
      setValue(null)
      setSelectOptionsText('')
      setError(null)
      setIsSaving(false)
      return
    }

    window.requestAnimationFrame(() => firstInputRef.current?.focus())
  }, [isOpen])

  const customField = useMemo<DynamicFieldPreset>(() => ({
    key: customLabel.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, ''),
    label: customLabel.trim(),
    field_type: customType,
    is_sensitive: customSensitive,
    select_options: parseSelectOptions(selectOptionsText),
  }), [customLabel, customSensitive, customType, selectOptionsText])

  const activeField = selectedPreset ?? customField
  const isCustomMode = mode === 'custom' && selectedPreset === null
  const canSave = selectedPreset !== null || isCustomMode

  function chooseSuggested(field: DynamicFieldPreset) {
    setSelectedPreset(field)
    setValue(null)
    setError(null)
    window.requestAnimationFrame(() => firstInputRef.current?.focus())
  }

  function backToSuggestedList() {
    setSelectedPreset(null)
    setValue(null)
    setError(null)
  }

  async function saveField() {
    if (!activeField.label) {
      setError('Field name is required.')
      return
    }
    if (activeField.field_type === 'select' && (activeField.select_options ?? []).length === 0) {
      setError('Add at least one select option.')
      return
    }

    setIsSaving(true)
    setError(null)
    try {
      const updated = await recordsApi.addField(record.id, {
        key: activeField.key || null,
        label: activeField.label,
        field_type: activeField.field_type,
        value: normalizeValue(activeField.field_type, value),
        is_sensitive: activeField.is_sensitive ?? false,
        select_options: activeField.select_options ?? [],
        display_order: activeField.display_order ?? null,
      })
      onSaved(updated)
      onClose()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to add field.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <SheetDrawer className="add-dialog add-field-dialog" isOpen={isOpen} labelledBy="add-field-heading" onClose={onClose}>
      <div className="sheet-header add-field-header">
        <div className="add-field-title-row">
          {selectedPreset ? (
            <button type="button" className="icon-button ghost-icon-button" onClick={backToSuggestedList} aria-label="Back to suggested fields">
              <ArrowLeft size={18} aria-hidden="true" />
            </button>
          ) : null}
          <div>
            <h2 id="add-field-heading">Add field</h2>
            <p>{record.title}</p>
          </div>
        </div>
        <button type="button" className="icon-button ghost-icon-button" onClick={onClose} aria-label="Close add field">
          <X size={19} aria-hidden="true" />
        </button>
      </div>

      <div className="sheet-body add-field-body">
        {selectedPreset === null ? (
          <div className="add-field-mode-tabs" role="tablist" aria-label="Field source">
            <button type="button" className={mode === 'suggested' ? 'active' : ''} onClick={() => setMode('suggested')}>Suggested</button>
            <button type="button" className={mode === 'custom' ? 'active' : ''} onClick={() => setMode('custom')}>Custom</button>
          </div>
        ) : null}

        {mode === 'suggested' && selectedPreset === null ? (
          suggestedFields.length > 0 ? (
            <div className="add-field-suggestions">
              {suggestedFields.map((field) => (
                <button type="button" className="add-field-suggestion" key={field.key} onClick={() => chooseSuggested(field)}>
                  <span className="add-field-suggestion-icon" aria-hidden="true">
                    {field.is_sensitive ? <LockKeyhole size={18} /> : <ListPlus size={18} />}
                  </span>
                  <span>
                    <strong>{field.label}</strong>
                    <small>{getDynamicFieldTypeLabel(field.field_type)}{field.description ? ` - ${field.description}` : ''}</small>
                  </span>
                  <Plus size={17} aria-hidden="true" />
                </button>
              ))}
            </div>
          ) : (
            <div className="add-field-empty">
              <ListPlus size={22} aria-hidden="true" />
              <p>All suggested fields are already on this record.</p>
              <button type="button" className="secondary-button" onClick={() => setMode('custom')}>Create custom field</button>
            </div>
          )
        ) : null}

        {isCustomMode ? (
          <div className="add-field-form">
            <label>
              <span>Field name</span>
              <input ref={firstInputRef as RefObject<HTMLInputElement>} maxLength={80} value={customLabel} onChange={(event) => setCustomLabel(event.target.value)} />
            </label>
            <label>
              <span>Type</span>
              <select value={customType} onChange={(event) => setCustomType(event.target.value as DynamicFieldType)}>
                {dynamicFieldTypes.map((type) => <option value={type} key={type}>{getDynamicFieldTypeLabel(type)}</option>)}
              </select>
            </label>
            <SwitchRow
              checked={customSensitive}
              description="Useful for identification numbers or private information."
              label="Hide value by default"
              onChange={setCustomSensitive}
            />
            {customType === 'select' ? (
              <label>
                <span>Select options</span>
                <textarea rows={3} maxLength={400} value={selectOptionsText} onChange={(event) => setSelectOptionsText(event.target.value)} placeholder="One option per line" />
              </label>
            ) : null}
            <DynamicValueControl field={customField} inputRef={firstInputRef} value={value} onChange={setValue} />
          </div>
        ) : null}

        {selectedPreset ? (
          <div className="add-field-form">
            <div className="add-field-selected-summary">
              <span className="add-field-suggestion-icon" aria-hidden="true">
                {selectedPreset.is_sensitive ? <LockKeyhole size={18} /> : <Type size={18} />}
              </span>
              <div>
                <strong>{selectedPreset.label}</strong>
                <small>{getDynamicFieldTypeLabel(selectedPreset.field_type)}</small>
              </div>
            </div>
            <DynamicValueControl field={selectedPreset} inputRef={firstInputRef} value={value} onChange={setValue} />
          </div>
        ) : null}

        {error ? <p className="field-error" role="alert">{error}</p> : null}

        {canSave ? (
          <div className="compact-action-bar">
            <button type="button" className="primary-button add-field-save-button" disabled={isSaving} onClick={() => void saveField()}>
              <Check size={17} aria-hidden="true" />
              {isSaving ? 'Saving...' : 'Save field'}
            </button>
          </div>
        ) : null}
      </div>
    </SheetDrawer>
  )
}

function DynamicValueControl({
  field,
  inputRef,
  onChange,
  value,
}: {
  field: DynamicFieldPreset
  inputRef: MutableRefObject<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null>
  value: DynamicFieldValue
  onChange: (value: DynamicFieldValue) => void
}) {
  if (field.field_type === 'boolean') {
    return <SwitchRow checked={value === true} label="Value" onChange={onChange} />
  }

  if (field.field_type === 'long_text') {
    return (
      <label>
        <span>Value</span>
        <textarea ref={inputRef as RefObject<HTMLTextAreaElement>} maxLength={1000} rows={4} value={toFieldInputValue(value)} onChange={(event) => onChange(event.target.value || null)} />
      </label>
    )
  }

  if (field.field_type === 'select') {
    return (
      <label>
        <span>Value</span>
        <select ref={inputRef as RefObject<HTMLSelectElement>} value={toFieldInputValue(value)} onChange={(event) => onChange(event.target.value || null)}>
          <option value="">Choose</option>
          {(field.select_options ?? []).map((option) => <option value={option} key={option}>{option}</option>)}
        </select>
      </label>
    )
  }

  return (
    <label>
      <span>Value</span>
      <input
        ref={inputRef as RefObject<HTMLInputElement>}
        maxLength={field.field_type === 'url' ? 500 : field.field_type === 'phone' ? 40 : 160}
        type={getInputTypeForDynamicField(field.field_type)}
        value={toFieldInputValue(value)}
        onChange={(event) => onChange(field.field_type === 'number' || field.field_type === 'money' ? event.target.value === '' ? null : Number(event.target.value) : event.target.value || null)}
      />
    </label>
  )
}

function SwitchRow({
  checked,
  description,
  label,
  onChange,
}: {
  checked: boolean
  description?: string
  label: string
  onChange: (value: boolean) => void
}) {
  return (
    <div className="field-toggle-label">
      <span>
        <strong>{label}</strong>
        {description ? <small>{description}</small> : null}
      </span>
      <button
        type="button"
        className={checked ? 'privacy-toggle active' : 'privacy-toggle'}
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
      >
        <span aria-hidden="true" />
      </button>
    </div>
  )
}

function normalizeValue(fieldType: DynamicFieldType, value: DynamicFieldValue) {
  if ((fieldType === 'number' || fieldType === 'money') && typeof value === 'string') {
    return value.trim() ? Number(value) : null
  }
  return value
}

function parseSelectOptions(value: string) {
  return value.split('\n').map((option) => option.trim()).filter(Boolean)
}
