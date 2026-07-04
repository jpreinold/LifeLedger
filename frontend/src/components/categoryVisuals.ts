import {
  Calendar,
  Car,
  CreditCard,
  FileText,
  Gift,
  HeartPulse,
  Home,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type { ReminderCategory } from '../types/reminder'

export interface CategoryVisual {
  Icon: LucideIcon
  tone: string
}

export const categoryVisuals: Record<ReminderCategory, CategoryVisual> = {
  Car: { Icon: Car, tone: 'car' },
  Health: { Icon: HeartPulse, tone: 'health' },
  Finance: { Icon: CreditCard, tone: 'finance' },
  Home: { Icon: Home, tone: 'home' },
  Family: { Icon: Gift, tone: 'family' },
  Subscriptions: { Icon: Calendar, tone: 'subscriptions' },
  Other: { Icon: FileText, tone: 'other' },
}

export function getCategoryVisual(category: ReminderCategory) {
  return categoryVisuals[category]
}
