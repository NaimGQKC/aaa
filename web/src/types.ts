export type Severity = 'high' | 'medium' | 'low' | 'info'

export interface Bbox {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface Citation {
  document_id: string
  page: number | null
  bbox: Bbox | null
  text_span: string | null
  field_path?: string
}

export interface DocumentSummary {
  id: string
  filename: string
  doc_type: string | null
  language: string | null
  status: string
  page_count: number | null
  classification_confidence: number
}

export interface OversightStats {
  findings_total: number
  findings_reviewed: number
  pending_high: number
  pending: number
  spot_checks_total: number
  spot_checks_done: number
  spot_checks_matched: number
  reviewers: string[]
  is_draft: boolean
}

export interface SpotCheck {
  id: string
  deal_id: string
  document_id: string
  extraction_id: string
  field_path: string
  value: unknown
  text_span: string | null
  page: number | null
  bbox: Bbox | null
  confidence: number
  status: 'pending' | 'match' | 'mismatch'
  actor: string | null
  reason: string | null
}

export interface Deal {
  id: string
  name: string
  jurisdiction: string[]
  created_at: string
  my_role: Role | null
  documents: DocumentSummary[]
  findings_by_severity: Record<Severity, number>
  oversight: OversightStats
}

export type Role = 'owner' | 'editor' | 'reviewer' | 'viewer'

export interface User {
  id: string
  email: string
  name: string
}

export interface Member {
  user_id: string
  email: string
  name: string
  role: Role
}

export interface Finding {
  id: string
  deal_id: string
  document_id: string | null
  category: string
  severity: Severity
  title: string
  description: string | null
  citations: Citation[]
  rule_key: string | null
  confidence: number
  human_status: 'pending' | 'accepted' | 'overridden'
  human_reason: string | null
  human_actor: string | null
}

export interface Extraction {
  id: string
  field_path: string
  value: unknown
  text_span: string | null
  page: number | null
  bbox: Bbox | null
  confidence: number
  abstained: boolean
  method: string
  schema_key: string
}

export interface Reconciliation {
  id: string
  rule_key: string
  status: 'match' | 'mismatch' | 'missing'
  severity: Severity
  details: Record<string, unknown>
}

export interface ReportInfo {
  id: string
  created_at?: string
  formats: { html: boolean; pdf: boolean; docx: boolean }
}
