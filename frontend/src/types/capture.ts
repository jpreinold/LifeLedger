export type CaptureStatus =
  | 'new'
  | 'interpreting'
  | 'needs_clarification'
  | 'ready_for_review'
  | 'executing'
  | 'completed'
  | 'failed'
  | 'dismissed'

export type ProposalStatus =
  | 'draft'
  | 'needs_clarification'
  | 'ready_for_review'
  | 'approved'
  | 'rejected'
  | 'executing'
  | 'partially_completed'
  | 'completed'
  | 'expired'
  | 'failed'

export interface Capture {
  capture_id: string
  source: 'lifeledger_web'
  input_type: 'text'
  original_text: string
  captured_at: string
  client_timestamp: string | null
  timezone: string
  locale: string
  status: CaptureStatus
  interpreter: 'deterministic' | 'openai' | 'mock' | 'disabled' | 'manual' | null
  active_proposal_id: string | null
  clarification_session_id: string | null
  interpretation_summary: string | null
  relevant_action: string | null
  failure_category: string | null
  safe_failure_message: string | null
  attempt_count: number
}

export interface ProposedAction {
  action_id: string
  action_type: string
  fields: Record<string, unknown>
  explanation: string
  risk_level: 'low' | 'medium' | 'high'
  confirmation_requirement: 'always' | 'clarification' | 'prohibited'
}

export interface ActionResult {
  action_id: string
  action_type: string
  status: 'pending' | 'completed' | 'failed' | 'prohibited'
  resulting_entity_id: string | null
  safe_summary: string
  idempotent_replay: boolean
  reconciliation_required: boolean
  correction_available: boolean
}

export interface ActionProposal {
  proposal_id: string
  capture_id: string
  status: ProposalStatus
  proposed_actions: ProposedAction[]
  action_results: ActionResult[]
  ambiguity_reasons: string[]
  conflict_warnings: string[]
  missing_information: string[]
  user_facing_summary: string
  interpreter: string
  expires_at: string
}

export interface ClarificationOption {
  option_id: string
  label: string
}

export interface ClarificationQuestion {
  question_id: string
  prompt: string
  options: ClarificationOption[]
  allow_free_text: boolean
}

export interface ClarificationSession {
  clarification_id: string
  proposal_id: string
  questions: ClarificationQuestion[]
  answers: Record<string, string>
  status: 'open' | 'answered' | 'expired' | 'cancelled'
  expires_at: string
}

export interface CaptureDetail {
  capture: Capture
  proposal: ActionProposal | null
  clarification: ClarificationSession | null
}

export interface CapturePage {
  items: Capture[]
  next_cursor: string | null
}

export interface AIUsageSummary {
  billing_month: string
  estimated_cost_usd: number
  request_count: number
  monthly_budget_usd: number
  remaining_budget_usd: number
  daily_request_count: number
  daily_request_limit: number
}

export interface AISettingsResponse {
  settings: {
    ai_enabled: boolean
    monthly_budget_usd: number
    daily_request_limit: number
    deterministic_first: boolean
    allow_model_escalation: boolean
  }
  usage: AIUsageSummary
  provider_configured: boolean
  default_model: string
  escalation_model: string | null
}
