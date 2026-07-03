import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Deal } from '../types'

export default function DealList() {
  const [deals, setDeals] = useState<Deal[]>([])
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const load = () => api.listDeals().then(setDeals).catch((e) => setError(String(e)))
  useEffect(() => {
    load()
  }, [])

  const create = async () => {
    if (!name.trim()) return
    await api.createDeal(name.trim(), ['ES', 'FR'])
    setName('')
    load()
  }

  return (
    <>
      <div className="panel">
        <h2>Deals</h2>
        <div className="review-row" style={{ marginBottom: '0.8rem' }}>
          <input
            placeholder="New deal name…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && create()}
          />
          <button onClick={create}>Create deal</button>
        </div>
        {error && <p style={{ color: 'var(--high)' }}>{error}</p>}
        <table className="grid">
          <thead>
            <tr>
              <th>Deal</th>
              <th>Jurisdictions</th>
              <th>Documents</th>
              <th>High</th>
              <th>Medium</th>
              <th>Low/Info</th>
            </tr>
          </thead>
          <tbody>
            {deals.map((d) => (
              <tr key={d.id}>
                <td>
                  <Link to={`/deals/${d.id}`}>{d.name}</Link>
                </td>
                <td>{d.jurisdiction.join(', ')}</td>
                <td>{d.documents.length}</td>
                <td>{d.findings_by_severity.high ?? 0}</td>
                <td>{d.findings_by_severity.medium ?? 0}</td>
                <td>{(d.findings_by_severity.low ?? 0) + (d.findings_by_severity.info ?? 0)}</td>
              </tr>
            ))}
            {deals.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  No deals yet — create one, or run <code>make seed</code> for the demo deal.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="panel muted">
        <strong>Sovereignty posture:</strong> documents are processed entirely under EU
        jurisdiction — offline local provider or Mistral La Plateforme (EU data residency,
        Zero Data Retention, DPA); no US CLOUD Act exposure. Every pipeline step writes to a
        hash-chained audit log engineered to EU AI Act Articles 12 &amp; 26.
      </div>
    </>
  )
}
