import { useState } from 'react'
import { api } from '../api'
import type { Citation, Finding } from '../types'
import SeverityBadge from './SeverityBadge'

export default function FindingCard({
  finding,
  docNames,
  onCitationClick,
  onReviewed,
}: {
  finding: Finding
  docNames: Record<string, string>
  onCitationClick?: (c: Citation) => void
  onReviewed?: (f: Finding) => void
}) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const review = async (status: 'accepted' | 'overridden') => {
    if (!reason.trim()) {
      setError('A reason is mandatory for the audit trail (AI Act Art. 26 oversight).')
      return
    }
    setBusy(true)
    setError('')
    try {
      const updated = await api.reviewFinding(finding.id, status, reason, 'reviewer')
      onReviewed?.(updated)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`finding ${finding.severity}`}>
      <div className="flex">
        <SeverityBadge severity={finding.severity} />
        <span className="badge chip">{finding.category}</span>
        {finding.document_id && (
          <span className="muted">{docNames[finding.document_id] ?? ''}</span>
        )}
        <span className="spacer" />
        {finding.human_status !== 'pending' && (
          <span className="badge chip">
            {finding.human_status} by {finding.human_actor}
          </span>
        )}
      </div>
      <p className="title">{finding.title}</p>
      {finding.description && <p className="desc">{finding.description}</p>}
      {finding.citations.map((c, i) => (
        <div
          key={i}
          className="cite"
          title="Click to view the source clause"
          onClick={() => onCitationClick?.(c)}
        >
          Source: {docNames[c.document_id] ?? c.document_id}
          {c.page ? `, p.${c.page}` : ''}
          {c.text_span ? ` — “${c.text_span}”` : ''}
        </div>
      ))}
      {finding.human_status === 'pending' ? (
        <div className="review-row">
          <input
            placeholder="Review reason (mandatory)…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button disabled={busy} onClick={() => review('accepted')}>
            Accept
          </button>
          <button disabled={busy} className="secondary" onClick={() => review('overridden')}>
            Override
          </button>
        </div>
      ) : (
        finding.human_reason && <p className="muted">Reason: {finding.human_reason}</p>
      )}
      {error && <p style={{ color: 'var(--high)' }}>{error}</p>}
    </div>
  )
}
