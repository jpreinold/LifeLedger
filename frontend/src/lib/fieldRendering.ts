import { formatLongDate } from './reminderDisplay'
import type { DynamicFieldType, DynamicFieldValue } from '../types/record'

export const maskedValue = '••••••••'

export function hasDisplayValue(value: DynamicFieldValue | string | null | undefined) {
  if (value === null || value === undefined) {
    return false
  }
  if (typeof value === 'string') {
    return value.trim().length > 0
  }
  return true
}

export function formatDynamicFieldValue(fieldType: DynamicFieldType, value: DynamicFieldValue) {
  if (!hasDisplayValue(value)) {
    return null
  }

  if (fieldType === 'boolean') {
    return value === true || value === 'true' ? 'Yes' : 'No'
  }

  if (fieldType === 'date' && typeof value === 'string') {
    return formatLongDate(value)
  }

  if ((fieldType === 'money' || fieldType === 'number') && typeof value === 'number') {
    if (fieldType === 'money') {
      return new Intl.NumberFormat(undefined, { currency: 'USD', style: 'currency' }).format(value)
    }
    return new Intl.NumberFormat().format(value)
  }

  return String(value)
}

export function getDynamicFieldTypeLabel(fieldType: DynamicFieldType) {
  const labels: Record<DynamicFieldType, string> = {
    short_text: 'Text',
    long_text: 'Long text',
    date: 'Date',
    number: 'Number',
    money: 'Money',
    phone: 'Phone',
    email: 'Email',
    url: 'URL',
    boolean: 'Yes/No',
    select: 'Select',
  }

  return labels[fieldType]
}

export function getInputTypeForDynamicField(fieldType: DynamicFieldType) {
  if (fieldType === 'date') {
    return 'date'
  }
  if (fieldType === 'number' || fieldType === 'money') {
    return 'number'
  }
  if (fieldType === 'email') {
    return 'email'
  }
  if (fieldType === 'url') {
    return 'url'
  }
  if (fieldType === 'phone') {
    return 'tel'
  }
  return 'text'
}

export function toFieldInputValue(value: DynamicFieldValue) {
  if (value === null || value === undefined) {
    return ''
  }
  return String(value)
}
