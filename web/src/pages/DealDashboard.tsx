import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import FindingCard from '../components/FindingCard'
import OversightPanel from '../components/OversightPanel'
import SeverityBadge from '../components/SeverityBadge'
import type {
  Deal,
  Finding,
  Member,
  Reconciliation,
  ReportInfo,
  Role,
  SpotCheck,
} from '../types'

type ReviewFilter = 'all' | 'pending' | 'reviewed'

export default function DealDashboard() {
  const { dealId = '' } = useParams()
  const navigate = useNavigate()
  const [deal, setDeal] = useState<Deal | null>(null)
  const [findings, setFindings] = useState<Finding[]>([])
  const [recon, setRecon] = useState<Reconciliation[]>([])
  const [reports, setReports] = useState<ReportInfo[]>([])
  const [spotChecks, setSpotChecks] = useState<SpotCheck[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<Role>('reviewer')
  const [inviteError, setInviteError] = useState('')
  const [filter, setFilter] = useState<ReviewFilter>('all')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.getDeal(dealId).then(setDeal).catch((e) => setError(String(e)))
    api.findings(dealId).then(setFindings).catch(() => {})
    api.reconciliations(dealId).then(setRecon).catch(() => {})
    api.listReports(dealId).then(setReports).catch(() => {})
    api.spotChecks(dealId).then(setSpotChecks).catch(() => {})
    api.members(dealId).then(setMembers).catch(() => {})
  }, [dealId])

  const invite = async () => {
    if (!inviteEmail.trim()) return
    setInviteError('')
    try {
      await api.addMember(dealId, inviteEmail.trim(), inviteRole)
      setInviteEmail('')
      load()
    } catch (e) {
      setInviteError(
        String(e).includes('404')
          ? 'No account with that email — ask them to register first (Sign in → Create an account), then invite them.'
          : String(e),
      )
    }
  }

  useEffect(() => {
    load()
  }, [load])

  const docNames = useMemo(
    () => Object.fromEntries((deal?.documents ?? []).map((d) => [d.id, d.filename])),
    [deal],
  )

  const onUpload = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    setError('')
    try {
      for (const f of Array.from(files)) await api.upload(dealId, f)
      await api.processDeal(dealId)
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const runPipeline = async () => {
    setBusy(true)
    try {
      await api.processDeal(dealId)
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const makeReport = async () => {
    setBusy(true)
    try {
      await api.createReport(dealId)
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  if (!deal) return <p className="muted">{error || 'Loading…'}</p>

  const epcFindings = findings.filter(
    (f) => f.category.startsWith('epc') || f.category.startsWith('epbd'),
  )
  const visibleFindings = findings.filter((f) =>
    filter === 'all'
      ? true
      : filter === 'pending'
        ? f.human_status === 'pending'
        : f.human_status !== 'pending',
  )
  const pendingChecks = spotChecks.filter((c) => c.status === 'pending')
  const o = deal.oversight

  return (
    <>
      <div className="panel">
        <div className="flex">
          <h2 style={{ margin: 0 }}>{deal.name}</h2>
          <span className="badge chip">{deal.jurisdiction.join(' · ')}</span>
          <span className="spacer" />
          <button disabled={busy} className="secondary" onClick={runPipeline}>
            Re-run pipeline
          </button>
          <button
            disabled={busy}
            onClick={makeReport}
            title={
              o.is_draft
                ? `The report will be stamped DRAFT — ${o.pending} finding(s) unreviewed`
                : 'All findings reviewed — the report exports as HUMAN-REVIEWED'
            }
          >
            {o.is_draft ? 'Generate report (draft)' : 'Generate report'}
          </button>
        </div>
        <OversightPanel deal={deal} />
        {error && <p style={{ color: 'var(--high)' }}>{error}</p>}
      </div>

      {pendingChecks.length > 0 && (
        <div className="panel spotcheck-panel">
          <h2>
            Spot-check queue ({pendingChecks.length})
            <span className="muted" style={{ fontWeight: 400, fontSize: '.8rem' }}>
              {' '}
              — verify a few of the AI's own high-confidence answers against the source.
              ~10 seconds each; keeps the reviewed stamp honest.
            </span>
          </h2>
          {pendingChecks.map((c) => (
            <div key={c.id} className="spotcheck-row">
              <span className="mono">{c.field_path}</span>
              <span className="spotcheck-value">{String(c.value ?? '—')}</span>
              <span className="muted">p.{c.page ?? '?'}</span>
              <span className="spacer" />
              <button
                className="secondary"
                onClick={() =>
                  navigate(`/deals/${dealId}/documents/${c.document_id}?spotcheck=${c.id}`)
                }
              >
                Verify against source →
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="panel">
        <h2>Documents</h2>
        <label className="dropzone" style={{ display: 'block', marginBottom: '0.8rem' }}>
          {busy ? 'Processing…' : 'Click to upload PDFs or a data-room ZIP'}
          <input
            type="file"
            multiple
            style={{ display: 'none' }}
            accept=".pdf,.zip"
            onChange={(e) => onUpload(e.target.files)}
          />
        </label>
        <table className="grid">
          <thead>
            <tr>
              <th>File</th>
              <th>Type</th>
              <th>Lang</th>
              <th>Pages</th>
              <th>Status</th>
              <th>Classification conf.</th>
            </tr>
          </thead>
          <tbody>
            {deal.documents.map((d) => (
              <tr
                key={d.id}
                className="clickable"
                onClick={() => navigate(`/deals/${dealId}/documents/${d.id}`)}
              >
                <td>{d.filename}</td>
                <td>{d.doc_type ?? <em className="muted">unclassified</em>}</td>
                <td>{d.language ?? '—'}</td>
                <td>{d.page_count ?? '—'}</td>
                <td><span className="badge chip">{d.status}</span></td>
                <td className="conf">{(d.classification_confidence * 100).toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <div className="flex" style={{ marginBottom: '.6rem' }}>
          <h2 style={{ margin: 0 }}>Findings ({visibleFindings.length})</h2>
          <span className="spacer" />
          {(['all', 'pending', 'reviewed'] as ReviewFilter[]).map((f) => (
            <button
              key={f}
              className={`chip-btn ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f}
              {f === 'pending' && o.pending > 0 && ` (${o.pending})`}
            </button>
          ))}
        </div>
        {visibleFindings.map((f) => (
          <FindingCard
            key={f.id}
            finding={f}
            docNames={docNames}
            onCitationClick={(c) =>
              c.document_id && navigate(`/deals/${dealId}/documents/${c.document_id}`)
            }
            onReviewed={() => load()}
          />
        ))}
        {visibleFindings.length === 0 && (
          <p className="muted">
            {findings.length === 0
              ? 'No findings yet — upload documents and run the pipeline.'
              : 'Nothing in this filter.'}
          </p>
        )}
      </div>

      <div className="panel">
        <h2>Reconciliation</h2>
        <table className="grid">
          <thead>
            <tr>
              <th>Rule</th>
              <th>Status</th>
              <th>Severity</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {recon.map((r) => (
              <tr key={r.id}>
                <td className="mono">{r.rule_key}</td>
                <td><span className={`badge ${r.status}`}>{r.status}</span></td>
                <td><SeverityBadge severity={r.severity} /></td>
                <td className="mono muted">{JSON.stringify(r.details)}</td>
              </tr>
            ))}
            {recon.length === 0 && (
              <tr><td colSpan={4} className="muted">No reconciliation rows.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>EPC / EPBD compliance</h2>
        {epcFindings.length === 0 && <p className="muted">No EPC findings.</p>}
        {epcFindings.map((f) => (
          <p key={f.id}>
            <SeverityBadge severity={f.severity} /> {f.title}
            <span className="muted"> — {f.description}</span>
          </p>
        ))}
      </div>

      <div className="panel">
        <h2>
          Team ({members.length})
          <span className="muted" style={{ fontWeight: 400, fontSize: '.8rem' }}>
            {' '}
            — per-deal access, like repo collaborators. Roles: owner · editor (uploads &
            runs) · reviewer (adjudicates & reports) · viewer (read-only, e.g. counterparty).
          </span>
        </h2>
        <table className="grid">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              {deal.my_role === 'owner' && <th></th>}
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.user_id}>
                <td>{m.name}</td>
                <td className="mono">{m.email}</td>
                <td>
                  <span className="badge chip">{m.role}</span>
                </td>
                {deal.my_role === 'owner' && (
                  <td>
                    <button
                      className="secondary"
                      style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                      onClick={() =>
                        api.removeMember(dealId, m.user_id).then(load).catch((e) => setInviteError(String(e)))
                      }
                    >
                      remove
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {deal.my_role === 'owner' && (
          <div className="review-row" style={{ marginTop: '0.7rem' }}>
            <input
              placeholder="Invite by email (they must register first)…"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && invite()}
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as Role)}
              style={{ padding: '0.4rem', border: '1px solid var(--line)', borderRadius: 5 }}
            >
              <option value="viewer">viewer (read-only)</option>
              <option value="reviewer">reviewer</option>
              <option value="editor">editor</option>
              <option value="owner">owner</option>
            </select>
            <button onClick={invite}>Invite</button>
          </div>
        )}
        {inviteError && <p style={{ color: 'var(--high)' }}>{inviteError}</p>}
      </div>

      <div className="panel">
        <h2>Reports</h2>
        {reports.map((r) => (
          <p key={r.id}>
            <span className="mono">{r.id.slice(0, 8)}</span>{'  '}
            {r.formats.pdf && (
              <a href={api.reportUrl(r.id, 'pdf')} target="_blank" rel="noreferrer">
                <strong>⬇ PDF</strong>
              </a>
            )}
            {r.formats.docx && (
              <>
                {'  ·  '}
                <a href={api.reportUrl(r.id, 'docx')}>Word</a>
              </>
            )}
            {r.formats.html && (
              <>
                {'  ·  '}
                <a href={api.reportUrl(r.id, 'html')} target="_blank" rel="noreferrer">
                  view HTML
                </a>
              </>
            )}
          </p>
        ))}
        {reports.length === 0 && <p className="muted">No reports generated yet.</p>}
      </div>

      <p className="muted">
        <Link to="/">← All deals</Link>
      </p>
    </>
  )
}
