import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronRight, FileUp, LockKeyhole, RotateCcw, ShieldCheck, X } from 'lucide-react'

import { linkedItemsApi } from '../api/linkedItemsApi'
import { recordsApi } from '../api/recordsApi'
import { remindersApi } from '../api/remindersApi'
import { attachmentAccept, formatAttachmentSize, validateAttachmentFile } from '../lib/attachmentFiles'
import {
  createGuidedWorkflowProgress,
  runGuidedWorkflowAttempt,
  type GuidedWorkflowAttemptResult,
  type GuidedWorkflowProgress,
} from '../lib/guidedWorkflowEngine'
import {
  formatGuidedSchedule,
  getCompatibleActiveItems,
  getGuidedStoredValue,
  getGuidedWorkflow,
  getWorkflowDueDate,
  initializeGuidedWorkflowValues,
  repeatForBillingFrequency,
  type GuidedWorkflowDefinition,
  type GuidedWorkflowField,
  type GuidedWorkflowId,
  type GuidedWorkflowStep,
  type GuidedWorkflowValues,
} from '../lib/guidedWorkflows'
import { getEntityDefinition } from '../lib/entityRegistry'
import type { LifeRecord } from '../types/record'
import { ConfirmDialog } from './ConfirmDialog'
import { SheetDrawer } from './SheetDrawer'

interface GuidedWorkflowDrawerProps {
  initialItem?: LifeRecord | null
  isOpen: boolean
  records: LifeRecord[]
  workflowId: GuidedWorkflowId | null
  onClose: () => void
  onDataChanged: () => Promise<void>
  onOpenItem: (record: LifeRecord) => void
}

type ItemMode = 'existing' | 'new'

const stepLabels: Record<GuidedWorkflowStep, string> = {
  item: 'Item',
  details: 'Details',
  responsibility: 'Responsibility',
  document: 'Document',
  review: 'Review',
}

export function GuidedWorkflowDrawer({
  initialItem = null,
  isOpen,
  records,
  workflowId,
  onClose,
  onDataChanged,
  onOpenItem,
}: GuidedWorkflowDrawerProps) {
  const workflow = getGuidedWorkflow(workflowId)
  const compatibleItems = useMemo(
    () => workflow ? getCompatibleActiveItems(workflow, records) : [],
    [records, workflow],
  )
  const [currentStep, setCurrentStep] = useState<GuidedWorkflowStep>('item')
  const [itemMode, setItemMode] = useState<ItemMode>('new')
  const [selectedExistingItemId, setSelectedExistingItemId] = useState('')
  const [values, setValues] = useState<GuidedWorkflowValues>({})
  const [approvedUpdates, setApprovedUpdates] = useState<Set<string>>(new Set())
  const [document, setDocument] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isDiscardConfirmOpen, setIsDiscardConfirmOpen] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [result, setResult] = useState<GuidedWorkflowAttemptResult | null>(null)
  const progressRef = useRef<GuidedWorkflowProgress>(createGuidedWorkflowProgress())
  const submittingRef = useRef(false)
  const recordsRef = useRef(records)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const stepHeadingRef = useRef<HTMLHeadingElement | null>(null)
  recordsRef.current = records

  const selectedExistingItem = initialItem
    ?? compatibleItems.find((record) => record.id === selectedExistingItemId)
    ?? null
  const visibleSteps = workflow
    ? workflow.requiredSteps.filter((step) => !(initialItem && step === 'item'))
    : []
  const currentStepIndex = Math.max(0, visibleSteps.indexOf(currentStep))

  useEffect(() => {
    if (!isOpen || !workflow) return
    const contextItem = initialItem?.record_type === workflow.associatedItemType ? initialItem : null
    const hasCompatibleItem = getCompatibleActiveItems(workflow, recordsRef.current).length > 0
    const nextMode: ItemMode = contextItem || hasCompatibleItem ? 'existing' : 'new'
    const nextSelectedId = contextItem?.id ?? ''
    setItemMode(nextMode)
    setSelectedExistingItemId(nextSelectedId)
    setValues(initializeGuidedWorkflowValues(workflow, contextItem))
    setApprovedUpdates(new Set())
    setDocument(null)
    setError(null)
    setIsSubmitting(false)
    submittingRef.current = false
    setIsDiscardConfirmOpen(false)
    setIsDirty(false)
    setResult(null)
    progressRef.current = createGuidedWorkflowProgress()
    setCurrentStep(contextItem ? 'details' : 'item')
  }, [initialItem, isOpen, workflow])

  useEffect(() => {
    if (!isOpen || result) return
    const frame = window.requestAnimationFrame(() => stepHeadingRef.current?.focus())
    return () => window.cancelAnimationFrame(frame)
  }, [currentStep, isOpen, result])

  if (!workflow) return null
  const activeWorkflow = workflow

  function chooseItemMode(mode: ItemMode) {
    if (initialItem || mode === itemMode) return
    setItemMode(mode)
    setSelectedExistingItemId('')
    setValues(initializeGuidedWorkflowValues(activeWorkflow))
    setApprovedUpdates(new Set())
    setError(null)
    setIsDirty(true)
  }

  function chooseExistingItem(record: LifeRecord) {
    setSelectedExistingItemId(record.id)
    setValues(initializeGuidedWorkflowValues(activeWorkflow, record))
    setApprovedUpdates(new Set())
    setError(null)
    setIsDirty(true)
  }

  function updateValue(fieldId: string, value: string) {
    setValues((current) => {
      const next = { ...current, [fieldId]: value }
      if (activeWorkflow.id === 'subscription_renewal' && fieldId === 'billing_frequency') {
        next.reminder_repeat = repeatForBillingFrequency(value)
      }
      if (activeWorkflow.id === 'pet_vaccination' && fieldId === 'veterinarian' && !current.vaccination_provider) {
        next.vaccination_provider = value
      }
      return next
    })
    setApprovedUpdates((current) => {
      if (!current.has(fieldId)) return current
      const next = new Set(current)
      next.delete(fieldId)
      return next
    })
    setError(null)
    setIsDirty(true)
  }

  function approveUpdate(fieldId: string) {
    setApprovedUpdates((current) => new Set([...current, fieldId]))
    setError(null)
  }

  function keepCurrentValue(fieldDefinition: GuidedWorkflowField) {
    if (!selectedExistingItem) return
    const stored = getGuidedStoredValue(selectedExistingItem, fieldDefinition)
    setValues((current) => ({ ...current, [fieldDefinition.id]: stored.value ?? '' }))
    setApprovedUpdates((current) => {
      const next = new Set(current)
      next.delete(fieldDefinition.id)
      return next
    })
    setError(null)
  }

  function goNext() {
    const validationMessage = validateStep(activeWorkflow, currentStep, values, itemMode, selectedExistingItem, approvedUpdates)
    if (validationMessage) {
      setError(validationMessage)
      return
    }
    const nextStep = visibleSteps[currentStepIndex + 1]
    if (nextStep) {
      setCurrentStep(nextStep)
      setError(null)
    }
  }

  function goBack() {
    const previousStep = visibleSteps[currentStepIndex - 1]
    if (previousStep) {
      setCurrentStep(previousStep)
      setError(null)
    }
  }

  function requestClose() {
    if (isSubmitting) return
    if (isDirty && !result?.complete) {
      setIsDiscardConfirmOpen(true)
      return
    }
    closeAndClear()
  }

  function closeAndClear() {
    setValues({})
    setDocument(null)
    setApprovedUpdates(new Set())
    setResult(null)
    setError(null)
    setIsDirty(false)
    progressRef.current = createGuidedWorkflowProgress()
    setIsDiscardConfirmOpen(false)
    onClose()
  }

  function handleFile(file: File | null) {
    if (!file) return
    const validationMessage = validateAttachmentFile(file, 0)
    if (validationMessage) {
      setError(validationMessage)
      return
    }
    setDocument(file)
    setError(null)
    setIsDirty(true)
  }

  async function save() {
    if (submittingRef.current) return
    const reviewValidation = validateAll(activeWorkflow, values, itemMode, selectedExistingItem, approvedUpdates)
    if (reviewValidation) {
      setError(reviewValidation)
      return
    }

    submittingRef.current = true
    setIsSubmitting(true)
    setError(null)
    try {
      const nextResult = await runGuidedWorkflowAttempt({
        workflow: activeWorkflow,
        values,
        existingItem: itemMode === 'existing' ? selectedExistingItem : null,
        approvedUpdates,
        document,
        progress: progressRef.current,
      }, {
        createItem: recordsApi.create,
        updateItem: recordsApi.update,
        createDetail: recordsApi.addField,
        updateDetail: recordsApi.updateField,
        saveProtected: (recordId, input, existing) => existing
          ? recordsApi.updateProtected(recordId, input)
          : recordsApi.setProtected(recordId, input),
        createReminder: remindersApi.create,
        createRelationship: (recordId, reminderId, type) => linkedItemsApi.createRecordLink(recordId, {
          target_type: 'reminder',
          target_id: reminderId,
          relationship_type: type,
        }),
        uploadDocument: recordsApi.uploadRecordAttachment,
      })
      setResult(nextResult)
      setIsDirty(!nextResult.complete)
      await onDataChanged()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'LifeLedger could not finish this guided setup. Try again.')
    } finally {
      submittingRef.current = false
      setIsSubmitting(false)
    }
  }

  const footer = result ? null : (
    <div className="guided-workflow-footer-actions">
      {currentStepIndex > 0 ? (
        <button type="button" className="secondary-button" onClick={goBack} disabled={isSubmitting}>Back</button>
      ) : <span />}
      {currentStep === 'review' ? (
        <button type="button" className="primary-button" onClick={() => void save()} disabled={isSubmitting}>
          {isSubmitting ? 'Saving and uploading...' : workflow.reviewPresentation.saveLabel}
        </button>
      ) : (
        <button type="button" className="primary-button" onClick={goNext}>
          Continue
          <ChevronRight size={17} aria-hidden="true" />
        </button>
      )}
    </div>
  )

  return (
    <>
      <SheetDrawer
        bodyClassName="sheet-body guided-workflow-body"
        className="guided-workflow-dialog"
        closeLabel="Close guided tracking"
        footer={footer}
        isOpen={isOpen}
        labelledBy="guided-workflow-title"
        onClose={requestClose}
        subtitle={result ? 'Guided tracking result' : workflow.shortDescription}
        title={workflow.title}
      >
        {result ? (
          <GuidedCompletion
            result={result}
            workflow={workflow}
            isSubmitting={isSubmitting}
            onClose={closeAndClear}
            onOpenItem={() => {
              if (result.item) onOpenItem(result.item)
              closeAndClear()
            }}
            onRetry={() => void save()}
          />
        ) : (
          <>
            <ol className="guided-progress" aria-label="Guided tracking progress" style={{ gridTemplateColumns: `repeat(${visibleSteps.length}, minmax(0, 1fr))` }}>
              {visibleSteps.map((step, index) => (
                <li className={step === currentStep ? 'active' : index < currentStepIndex ? 'complete' : ''} key={step} aria-current={step === currentStep ? 'step' : undefined}>
                  <span>{index < currentStepIndex ? <Check size={13} aria-hidden="true" /> : index + 1}</span>
                    <small>
                      {step === 'responsibility' ? (
                        <><span className="guided-progress-full-label">Responsibility</span><span className="guided-progress-short-label">Task</span></>
                      ) : stepLabels[step]}
                    </small>
                </li>
              ))}
            </ol>
            <p className="sr-only" aria-live="polite">Step {currentStepIndex + 1} of {visibleSteps.length}: {stepLabels[currentStep]}</p>
            <section className="guided-step" aria-labelledby="guided-step-heading">
              <h3 id="guided-step-heading" ref={stepHeadingRef} tabIndex={-1}>{getStepHeading(workflow, currentStep)}</h3>
              {currentStep === 'item' ? (
                <ItemStep
                  compatibleItems={compatibleItems}
                  itemMode={itemMode}
                  selectedId={selectedExistingItemId}
                  values={values}
                  workflow={workflow}
                  onChooseItem={chooseExistingItem}
                  onChooseMode={chooseItemMode}
                  onValueChange={updateValue}
                />
              ) : null}
              {currentStep === 'details' || currentStep === 'responsibility' ? (
                <FieldsStep
                  approvedUpdates={approvedUpdates}
                  existingItem={selectedExistingItem}
                  fields={workflow.fields.filter((fieldDefinition) => fieldDefinition.step === currentStep)}
                  values={values}
                  workflow={workflow}
                  onApproveUpdate={approveUpdate}
                  onKeepCurrent={keepCurrentValue}
                  onValueChange={updateValue}
                />
              ) : null}
              {currentStep === 'responsibility' ? (
                <ScheduleStep values={values} workflow={workflow} onValueChange={updateValue} />
              ) : null}
              {currentStep === 'document' ? (
                <DocumentStep document={document} workflow={workflow} onChoose={() => fileInputRef.current?.click()} onRemove={() => setDocument(null)} />
              ) : null}
              {currentStep === 'review' ? (
                <ReviewStep document={document} existingItem={selectedExistingItem} values={values} workflow={workflow} />
              ) : null}
              {error ? <p className="field-error guided-error-summary" role="alert">{error}</p> : null}
            </section>
          </>
        )}
        <input
          accept={attachmentAccept}
          className="attachment-file-input"
          ref={fileInputRef}
          type="file"
          onChange={(event) => {
            handleFile(event.target.files?.[0] ?? null)
            event.target.value = ''
          }}
        />
      </SheetDrawer>
      <ConfirmDialog
        body="Your unsaved guided setup will be discarded. Protected values are cleared from this device when you close."
        confirmLabel="Discard setup"
        isOpen={isDiscardConfirmOpen}
        title="Discard guided setup?"
        onCancel={() => setIsDiscardConfirmOpen(false)}
        onConfirm={closeAndClear}
      />
    </>
  )
}

function ItemStep({
  compatibleItems,
  itemMode,
  selectedId,
  values,
  workflow,
  onChooseItem,
  onChooseMode,
  onValueChange,
}: {
  compatibleItems: LifeRecord[]
  itemMode: ItemMode
  selectedId: string
  values: GuidedWorkflowValues
  workflow: GuidedWorkflowDefinition
  onChooseItem: (record: LifeRecord) => void
  onChooseMode: (mode: ItemMode) => void
  onValueChange: (id: string, value: string) => void
}) {
  const entity = getEntityDefinition(workflow.associatedItemType)
  return (
    <div className="guided-step-content">
      {compatibleItems.length > 0 ? (
        <div className="guided-item-mode" role="radiogroup" aria-label="Use an existing item or add a new one">
          <button type="button" role="radio" aria-checked={itemMode === 'existing'} className={itemMode === 'existing' ? 'active' : ''} onClick={() => onChooseMode('existing')}>Use an existing {entity.singularLabel.toLocaleLowerCase()}</button>
          <button type="button" role="radio" aria-checked={itemMode === 'new'} className={itemMode === 'new' ? 'active' : ''} onClick={() => onChooseMode('new')}>Add a new {entity.singularLabel.toLocaleLowerCase()}</button>
        </div>
      ) : null}

      {itemMode === 'existing' && compatibleItems.length > 0 ? (
        <div className="guided-existing-items" role="radiogroup" aria-label={`Existing ${entity.pluralLabel}`}>
          {compatibleItems.map((record) => (
            <button type="button" role="radio" aria-checked={selectedId === record.id} className={selectedId === record.id ? 'active' : ''} key={record.id} onClick={() => onChooseItem(record)}>
              <span className={`category-icon tone-${entity.tone}`} aria-hidden="true"><entity.icon size={18} /></span>
              <span><strong>{record.title}</strong><small>{record.subtitle || entity.singularLabel}</small></span>
              {selectedId === record.id ? <Check size={17} aria-hidden="true" /> : null}
            </button>
          ))}
        </div>
      ) : (
        <label>
          <span>{workflow.itemTitleConfiguration.label}</span>
          <input required maxLength={120} value={values.item_title ?? ''} onChange={(event) => onValueChange('item_title', event.target.value)} placeholder={workflow.itemTitleConfiguration.placeholder} />
        </label>
      )}
    </div>
  )
}

function FieldsStep({
  approvedUpdates,
  existingItem,
  fields,
  values,
  workflow,
  onApproveUpdate,
  onKeepCurrent,
  onValueChange,
}: {
  approvedUpdates: Set<string>
  existingItem: LifeRecord | null
  fields: GuidedWorkflowField[]
  values: GuidedWorkflowValues
  workflow: GuidedWorkflowDefinition
  onApproveUpdate: (id: string) => void
  onKeepCurrent: (field: GuidedWorkflowField) => void
  onValueChange: (id: string, value: string) => void
}) {
  return (
    <div className="guided-fields">
      {fields.map((fieldDefinition) => {
        const stored = existingItem ? getGuidedStoredValue(existingItem, fieldDefinition) : null
        const currentValue = values[fieldDefinition.id] ?? ''
        const hasConflict = Boolean(existingItem && stored?.hasValue && !stored.protected && stored.value !== currentValue)
        const replacementCopy = existingItem && stored?.protected && stored.hasValue
          ? 'A protected value is already stored. Enter a new value only to replace it.'
          : null
        return (
          <div className="guided-field" key={fieldDefinition.id}>
            <GuidedInput field={fieldDefinition} value={currentValue} workflow={workflow} onChange={(value) => onValueChange(fieldDefinition.id, value)} />
            {replacementCopy ? <small className="guided-protected-existing"><LockKeyhole size={13} aria-hidden="true" /> {replacementCopy}</small> : null}
            {hasConflict ? (
              <div className="guided-conflict" role="group" aria-label={`Resolve change to ${fieldDefinition.label}`}>
                <p>Current value: <strong>{stored?.value}</strong></p>
                <div>
                  <button type="button" className="small-outline-button" onClick={() => onKeepCurrent(fieldDefinition)}>Keep current</button>
                  <button type="button" className={approvedUpdates.has(fieldDefinition.id) ? 'small-outline-button active' : 'small-outline-button'} onClick={() => onApproveUpdate(fieldDefinition.id)}>
                    {approvedUpdates.has(fieldDefinition.id) ? 'Update approved' : 'Update item'}
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        )
      })}
      {workflow.id === 'pet_vaccination' && fields.some((item) => item.id === 'vaccination_name') ? (
        <p className="guided-advice-note">LifeLedger tracks the date you enter but does not recommend or interpret vaccination schedules.</p>
      ) : null}
      {workflow.id === 'subscription_renewal' ? (
        <p className="guided-advice-note">Do not store passwords, authentication codes, or full payment-card information.</p>
      ) : null}
    </div>
  )
}

function GuidedInput({ field, value, workflow, onChange }: { field: GuidedWorkflowField; value: string; workflow: GuidedWorkflowDefinition; onChange: (value: string) => void }) {
  const inputId = `guided-${workflow.id}-${field.id}`
  const helperId = field.helperText ? `${inputId}-helper` : undefined
  if (field.inputType === 'select') {
    return (
      <label htmlFor={inputId}>
        <span>{field.label}{field.required ? ' *' : ''}</span>
        <select id={inputId} required={field.required} value={value} onChange={(event) => onChange(event.target.value)}>
          <option value="">Choose</option>
          {field.options?.map((option) => <option value={option} key={option}>{option}</option>)}
        </select>
        {field.helperText ? <small id={helperId}>{field.helperText}</small> : null}
      </label>
    )
  }
  if (field.inputType === 'textarea') {
    return (
      <label htmlFor={inputId}>
        <span>{field.label}{field.required ? ' *' : ''}</span>
        <textarea id={inputId} required={field.required} maxLength={1000} rows={3} value={value} onChange={(event) => onChange(event.target.value)} placeholder={field.placeholder} />
        {field.helperText ? <small id={helperId}>{field.helperText}</small> : null}
      </label>
    )
  }
  return (
    <label htmlFor={inputId}>
      <span>{field.label}{field.required ? ' *' : ''}</span>
      <input
        id={inputId}
        aria-describedby={helperId}
        autoComplete={field.protected ? 'off' : undefined}
        list={field.suggestions ? `${inputId}-suggestions` : undefined}
        maxLength={field.inputType === 'url' ? 500 : 160}
        required={field.required}
        step={field.inputType === 'money' ? '0.01' : undefined}
        type={field.inputType === 'money' ? 'number' : field.inputType}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={field.placeholder}
      />
      {field.suggestions ? <datalist id={`${inputId}-suggestions`}>{field.suggestions.map((suggestion) => <option value={suggestion} key={suggestion} />)}</datalist> : null}
      {field.helperText ? <small id={helperId}>{field.helperText}</small> : null}
    </label>
  )
}

function ScheduleStep({ values, workflow, onValueChange }: { values: GuidedWorkflowValues; workflow: GuidedWorkflowDefinition; onValueChange: (id: string, value: string) => void }) {
  const dueDate = getWorkflowDueDate(workflow, values)
  return (
    <section className="guided-schedule" aria-labelledby="guided-schedule-heading">
      <div>
        <h4 id="guided-schedule-heading">When should LifeLedger remind you?</h4>
        <p>{workflow.responsibilityConfiguration.title}{dueDate ? ` · Due ${dueDate}` : ''}</p>
      </div>
      <div className="form-row">
        <label>
          <span>Remind me</span>
          <input type="number" min="1" max="365" value={values.reminder_lead_value ?? ''} onChange={(event) => onValueChange('reminder_lead_value', event.target.value)} />
        </label>
        <label>
          <span>Before</span>
          <select value={values.reminder_lead_unit ?? 'weeks'} onChange={(event) => onValueChange('reminder_lead_unit', event.target.value)}>
            <option value="days">Days</option>
            <option value="weeks">Weeks</option>
            <option value="months">Months</option>
          </select>
        </label>
      </div>
      <label>
        <span>Recurrence</span>
        <select value={values.reminder_repeat ?? 'None'} onChange={(event) => onValueChange('reminder_repeat', event.target.value)}>
          <option value="None">One time</option>
          <option value="Weekly">Weekly</option>
          <option value="Monthly">Monthly</option>
          <option value="Quarterly">Quarterly</option>
          <option value="Yearly">Yearly</option>
        </select>
      </label>
    </section>
  )
}

function DocumentStep({ document, workflow, onChoose, onRemove }: { document: File | null; workflow: GuidedWorkflowDefinition; onChoose: () => void; onRemove: () => void }) {
  return (
    <div className="guided-document-step">
      <span className="guided-document-icon" aria-hidden="true"><ShieldCheck size={24} /></span>
      <div>
        <h4>{workflow.documentPrompt.title}</h4>
        <p>{workflow.documentPrompt.description}</p>
        <small>{workflow.documentPrompt.privacyGuidance}</small>
      </div>
      <div className="documents-meta-strip" aria-label="Document limits">
        <span>Optional</span><span>PDF, JPEG, PNG</span><span>10 MB max</span>
      </div>
      {document ? (
        <div className="guided-document-file">
          <FileUp size={18} aria-hidden="true" />
          <span><strong>{document.name}</strong><small>{formatAttachmentSize(document.size)}</small></span>
          <button type="button" className="icon-button ghost-icon-button" onClick={onRemove} aria-label={`Remove ${document.name}`}><X size={16} aria-hidden="true" /></button>
        </div>
      ) : (
        <button type="button" className="secondary-button" onClick={onChoose}><FileUp size={16} aria-hidden="true" /> Add a document now</button>
      )}
      <p className="field-helper">You can skip this step and add the document from the item later.</p>
    </div>
  )
}

function ReviewStep({ document, existingItem, values, workflow }: { document: File | null; existingItem: LifeRecord | null; values: GuidedWorkflowValues; workflow: GuidedWorkflowDefinition }) {
  const detailRows = workflow.fields
    .filter((field) => values[field.id]?.trim() && !field.protected)
    .map((field) => ({ label: field.reviewLabel, value: values[field.id] }))
  const protectedRows = workflow.fields.filter((field) => field.protected && values[field.id]?.trim())
  const itemTitle = existingItem?.title ?? values.item_title
  return (
    <div className="guided-review">
      <ReviewGroup title="Item" rows={[{ label: workflow.itemTitleConfiguration.reviewLabel, value: itemTitle }]} />
      <ReviewGroup title="Details" rows={detailRows} />
      <ReviewGroup title="Responsibility" rows={[
        { label: 'Responsibility', value: workflow.id === 'pet_vaccination' ? `${values.vaccination_name || 'Vaccination'} vaccination`.replace(/vaccination vaccination$/i, 'vaccination') : workflow.responsibilityConfiguration.title },
        { label: 'Due date', value: getWorkflowDueDate(workflow, values) },
      ]} />
      <ReviewGroup title="Reminder schedule" rows={[
        { label: 'Remind me', value: formatGuidedSchedule(values) },
        { label: 'Recurrence', value: values.reminder_repeat === 'None' ? 'One time' : values.reminder_repeat },
      ]} />
      {protectedRows.length > 0 ? (
        <ReviewGroup title="Protected details" rows={protectedRows.map((field) => ({ label: field.reviewLabel, value: 'Will be encrypted and excluded from search' }))} />
      ) : null}
      {document ? <ReviewGroup title="Document" rows={[{ label: 'Upload', value: document.name }]} /> : null}
      {!document ? <p className="guided-review-skip">Document: Add later</p> : null}
      <p className="guided-review-relationship">LifeLedger will connect the responsibility to this item automatically.</p>
    </div>
  )
}

function ReviewGroup({ title, rows }: { title: string; rows: Array<{ label: string; value: string | null | undefined }> }) {
  const visibleRows = rows.filter((row) => row.value)
  if (visibleRows.length === 0) return null
  return (
    <section className="guided-review-group">
      <h4>{title}</h4>
      <dl>
        {visibleRows.map((row) => <div key={`${title}-${row.label}`}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}
      </dl>
    </section>
  )
}

function GuidedCompletion({ result, workflow, isSubmitting, onClose, onOpenItem, onRetry }: { result: GuidedWorkflowAttemptResult; workflow: GuidedWorkflowDefinition; isSubmitting: boolean; onClose: () => void; onOpenItem: () => void; onRetry: () => void }) {
  return (
    <section className={`guided-completion ${result.complete ? 'complete' : 'partial'}`} aria-labelledby="guided-completion-heading">
      <span className="guided-completion-icon" aria-hidden="true">{result.complete ? <Check size={24} /> : <RotateCcw size={24} />}</span>
      <div>
        <h3 id="guided-completion-heading">{result.complete ? workflow.completionPresentation.title : 'Some setup still needs attention'}</h3>
        <p>{result.message}</p>
      </div>
      <ul className="record-workflow-stages" aria-label="Guided setup progress">
        {result.stages.map((stage) => (
          <li key={stage.id}><span>{stage.label}</span><strong>{stage.status === 'saved' ? 'Saved' : stage.status === 'needs_retry' ? 'Needs retry' : 'Not included'}</strong></li>
        ))}
      </ul>
      <div className="guided-completion-actions">
        {!result.complete ? <button type="button" className="primary-button" onClick={onRetry} disabled={isSubmitting}><RotateCcw size={16} aria-hidden="true" /> {isSubmitting ? 'Retrying...' : 'Retry failed setup'}</button> : null}
        {result.item ? <button type="button" className={result.complete ? 'primary-button' : 'secondary-button'} onClick={onOpenItem}>Open item</button> : null}
        <button type="button" className="secondary-button" onClick={onClose}>{result.complete ? 'Done' : 'Finish later'}</button>
      </div>
    </section>
  )
}

function validateStep(
  workflow: GuidedWorkflowDefinition,
  step: GuidedWorkflowStep,
  values: GuidedWorkflowValues,
  itemMode: ItemMode,
  existingItem: LifeRecord | null,
  approvedUpdates: Set<string>,
) {
  if (step === 'item') {
    if (itemMode === 'existing' && !existingItem) return `Choose an existing ${getEntityDefinition(workflow.associatedItemType).singularLabel.toLocaleLowerCase()}.`
    if (itemMode === 'new' && !values.item_title?.trim()) return `${workflow.itemTitleConfiguration.label} is required.`
  }
  const missing = workflow.fields.find((field) => field.step === step && field.required && !values[field.id]?.trim())
  if (missing) return `${missing.label} is required.`
  const unresolved = workflow.fields.find((field) => {
    if (field.step !== step || !existingItem || field.protected) return false
    const stored = getGuidedStoredValue(existingItem, field)
    return stored.hasValue && stored.value !== (values[field.id] ?? '') && !approvedUpdates.has(field.id)
  })
  if (unresolved) return `Choose whether to keep or update the current ${unresolved.label.toLocaleLowerCase()}.`
  if (step === 'responsibility' && Number(values.reminder_lead_value) <= 0) return 'Choose a reminder time greater than zero.'
  return null
}

function validateAll(
  workflow: GuidedWorkflowDefinition,
  values: GuidedWorkflowValues,
  itemMode: ItemMode,
  existingItem: LifeRecord | null,
  approvedUpdates: Set<string>,
) {
  for (const step of workflow.requiredSteps) {
    const message = validateStep(workflow, step, values, itemMode, existingItem, approvedUpdates)
    if (message) return message
  }
  return null
}

function getStepHeading(workflow: GuidedWorkflowDefinition, step: GuidedWorkflowStep) {
  if (step === 'item') return `Which ${getEntityDefinition(workflow.associatedItemType).singularLabel.toLocaleLowerCase()} should LifeLedger use?`
  if (step === 'details') return 'Add the useful details'
  if (step === 'responsibility') return 'Set up the responsibility'
  if (step === 'document') return 'Add a document now or later'
  return workflow.reviewPresentation.title
}
