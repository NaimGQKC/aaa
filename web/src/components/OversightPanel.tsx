/**
 * Proof-of-Oversight header — the deal's trust state in one glance:
 * severity counts, human-review progress ring, spot-check agreement and the
 * DRAFT/REVIEWED stamp the exported report will carry. This is the UI
 * embodiment of "the deliverable carries the oversight state".
 */
import type { Deal } from '../types'

function Ring({ done, total, label }: { done: number; total: number; label: string }) {
  const pct = total > 0 ? done / total : 0
  const R = 26
  const C = 2 * Math.PI * R
  const color = pct >= 1 ? 'var(--match)' : pct > 0 ? 'var(--medium)' : 'var(--line)'
  return (
    <div className="ring">
      <svg width="72" height="72" viewBox="0 0 72 72">
        <circle cx="36" cy="36" r={R} fill="none" stroke="var(--line)" strokeWidth="7" />
        <circle
          cx="36"
          cy="36"
          r={R}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${C * pct} ${C}`}
          transform="rotate(-90 36 36)"
          style={{ transition: 'stroke-dasharray .6s ease' }}
        />
        <text x="36" y="40" textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--ink)">
          {done}/{total}
        </text>
      </svg>
      <div className="ring-label">{label}</div>
    </div>
  )
}

export default function OversightPanel({ deal }: { deal: Deal }) {
  const o = deal.oversight
  const sev = deal.findings_by_severity
  const agreementText =
    o.spot_checks_done > 0 ? `${o.spot_checks_matched}/${o.spot_checks_done} agree` : 'not started'

  return (
    <div className="oversight">
      <div className="oversight-sev">
        <div className="item">
          <div className="n" style={{ color: 'var(--high)' }}>{sev.high ?? 0}</div>
          <div className="muted">high</div>
        </div>
        <div className="item">
          <div className="n" style={{ color: 'var(--medium)' }}>{sev.medium ?? 0}</div>
          <div className="muted">medium</div>
        </div>
        <div className="item">
          <div className="n">{(sev.low ?? 0) + (sev.info ?? 0)}</div>
          <div className="muted">low / info</div>
        </div>
        <div className="item">
          <div className="n">{deal.documents.length}</div>
          <div className="muted">documents</div>
        </div>
      </div>

      <div className="oversight-rings">
        <Ring done={o.findings_reviewed} total={o.findings_total} label="findings reviewed" />
        <Ring done={o.spot_checks_done} total={o.spot_checks_total} label="spot-checks" />
      </div>

      <div className="oversight-status">
        <span className={`stamp ${o.is_draft ? 'draft' : 'final'}`}>
          {o.is_draft ? 'DRAFT' : 'HUMAN-REVIEWED'}
        </span>
        <div className="muted" style={{ marginTop: '.4rem', fontSize: '.8rem' }}>
          {o.is_draft ? (
            <>
              {o.pending} finding{o.pending === 1 ? '' : 's'} await review
              {o.pending_high > 0 && (
                <strong style={{ color: 'var(--high)' }}> ({o.pending_high} high)</strong>
              )}
              . Reports export with a DRAFT stamp until oversight is complete.
            </>
          ) : (
            <>
              All findings adjudicated · spot-checks {agreementText}
              {o.reviewers.length > 0 && <> · by {o.reviewers.join(', ')}</>}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
