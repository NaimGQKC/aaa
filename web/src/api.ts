import type { Deal, Extraction, Finding, Reconciliation, ReportInfo } from './types'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init)
  if (!r.ok) throw new Error(`${init?.method ?? 'GET'} ${path}: ${r.status} ${await r.text()}`)
  return r.json() as Promise<T>
}

export const api = {
  listDeals: () => req<Deal[]>('/api/deals'),
  getDeal: (id: string) => req<Deal>(`/api/deals/${id}`),
  createDeal: (name: string, jurisdiction: string[]) =>
    req<Deal>('/api/deals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, jurisdiction }),
    }),
  upload: (dealId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return req<{ documents: { id: string }[] }>(`/api/deals/${dealId}/upload`, {
      method: 'POST',
      body: form,
    })
  },
  processDeal: (dealId: string) =>
    req<{ status: string }>(`/api/deals/${dealId}/process`, { method: 'POST' }),
  findings: (dealId: string) => req<Finding[]>(`/api/deals/${dealId}/findings`),
  reconciliations: (dealId: string) =>
    req<Reconciliation[]>(`/api/deals/${dealId}/reconciliations`),
  extractions: (documentId: string) =>
    req<Extraction[]>(`/api/documents/${documentId}/extractions`),
  reviewFinding: (findingId: string, status: string, reason: string, actor: string) =>
    req<Finding>(`/api/findings/${findingId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, reason, actor }),
    }),
  createReport: (dealId: string) =>
    req<ReportInfo>(`/api/deals/${dealId}/report`, { method: 'POST' }),
  listReports: (dealId: string) => req<ReportInfo[]>(`/api/deals/${dealId}/reports`),
  auditVerify: () => req<{ valid: boolean; events: number }>('/api/audit/verify'),
  health: () => req<{ status: string; provider: string; storage: string }>('/health'),
  pdfUrl: (documentId: string) => `/api/documents/${documentId}/pdf`,
  reportUrl: (reportId: string, ext: string) => `/api/reports/${reportId}.${ext}`,
}
