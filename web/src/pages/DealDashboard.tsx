import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import FindingCard from '../components/FindingCard'
import SeverityBadge from '../components/SeverityBadge'
import type { Deal, Finding, Reconciliation, ReportInfo } from '../types'

export default function DealDashboard() {
  const { dealId = '' } = useParams()
  const navigate = useNavigate()
  const [deal, setDeal] = useState<Deal | null>(null)
  const [findings, setFindings] = useState<Finding[]>([])
  const [recon, setRecon] = useState<Reconciliation[]>([])
  const [reports, setReports] = useState<ReportInfo[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.getDeal(dealId).then(setDeal).catch((e) => setError(String(e)))
    api.findings(dealId).then(setFindings).catch(() => {})
    api.reconciliations(dealId).then(setRecon).catch(() => {})
    api.listReports(dealId).then(setReports).catch(() => {})
  }, [dealId])

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

  const sev = deal.findings_by_severity
  const epcFindings = findings.filter(
    (f) => f.category.startsWith('epc') || f.category.startsWith('epbd'),
  )

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
          <button disabled={busy} onClick={makeReport}>
            Generate report
          </button>
        </div>
        <div className="kpi" style={{ marginTop: '0.8rem' }}>
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
        {error && <p style={{ color: 'var(--high)' }}>{error}</p>}
      </div>

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
        <h2>Findings ({findings.length})</h2>
        {findings.map((f) => (
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
        {findings.length === 0 && (
          <p className="muted">No findings yet — upload documents and run the pipeline.</p>
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
