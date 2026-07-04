import { useState } from 'react'
import { api } from '../api'
import type { Citation, Finding } from '../types'
import SeverityBadge from './SeverityBadge'

export default function FindingCard({
  finding,
  docNames,
  onCitationClick,
  onReviewed,
  canReview = true,
}: {
  finding: Finding
  docNames: Record<string, string>
  onCitationClick?: (c: Citation) => void
  onReviewed?: (f: Finding) => void
  canReview?: boolean
}) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // M2 — risk-tiered friction: a high-severity finding can't be dispositioned
  // until its source has been opened. This is enforced server-side too.
  const gated = finding.review_gated

  const review = async (status: 'accepted' | 'overridden') => {
    if (!reason.trim()) {
      setError('A reason is mandatory for the audit trail (AI Act Art. 26 oversight).')
      return
    }
    setBusy(true)
    setError('')
    try {
      const updated = await api.reviewFinding(finding.id, status, reason)
      onReviewed?.(updated)
    } catch (e) {
      setError(
        String(e).includes('409')
          ? 'Open the cited source to verify before dispositioning this high-severity finding.'
          : String(e),
      )
    } finally {
      setBusy(false)
    }
  }

  const rel = finding.reliability
  return (
    <div className={`finding ${finding.severity}`}>
      <div className="flex">
        <SeverityBadge severity={finding.severity} />
        <span className="badge chip">{finding.category}</span>
        {rel?.enough_data && rel.rate !== null && (
          <span
            className="badge chip"
            title={`Measured on your team's ${rel.n} verified dispositions of "${finding.category}" — not model confidence.`}
            style={{ background: rel.rate >= 0.9 ? '#e9f7ef' : '#fdf3e6', color: '#333' }}
          >
            verified {Math.round(rel.rate * 100)}% · n={rel.n}
          </span>
        )}
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
      {canReview &&
        (finding.human_status === 'pending' ? (
          <>
            {gated && (
              <p className="gate-note">
                🔒 High-impact finding — <strong>open the source to verify</strong> before
                accepting.{' '}
                {finding.citations[0] && (
                  <a
                    style={{ cursor: 'pointer' }}
                    onClick={() => onCitationClick?.(finding.citations[0])}
                  >
                    Open source →
                  </a>
                )}
              </p>
            )}
            <div className="review-row">
              <input
                placeholder="Review reason (mandatory)…"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={gated}
              />
              <button disabled={busy || gated} onClick={() => review('accepted')}>
                Accept
              </button>
              <button
                disabled={busy || gated}
                className="secondary"
                onClick={() => review('overridden')}
              >
                Override
              </button>
            </div>
          </>
        ) : (
          finding.human_reason && <p className="muted">Reason: {finding.human_reason}</p>
        ))}
      {!canReview && (
        <p className="muted" style={{ fontSize: '.8rem' }}>
          Read-only — reviewer access required to disposition findings.
        </p>
      )}
      {error && <p style={{ color: 'var(--high)' }}>{error}</p>}
    </div>
  )
}
