/**
 * The split-screen review screen (spec §5.1 #2): extracted fields + findings
 * on the left, the source PDF with synchronized bbox highlights on the
 * right. Clicking a field or citation scrolls the viewer to the source
 * clause and highlights it.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import FindingCard from '../components/FindingCard'
import PdfViewer, { Highlight } from '../components/PdfViewer'
import type { Deal, Extraction, Finding } from '../types'

export default function DocumentReview() {
  const { dealId = '', documentId = '' } = useParams()
  const [deal, setDeal] = useState<Deal | null>(null)
  const [extractions, setExtractions] = useState<Extraction[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [highlight, setHighlight] = useState<Highlight | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    api.getDeal(dealId).then(setDeal).catch(() => {})
    api.extractions(documentId).then(setExtractions).catch(() => {})
    api.findings(dealId).then(setFindings).catch(() => {})
  }, [dealId, documentId])

  const doc = deal?.documents.find((d) => d.id === documentId)
  const docNames = useMemo(
    () => Object.fromEntries((deal?.documents ?? []).map((d) => [d.id, d.filename])),
    [deal],
  )
  const docFindings = findings.filter((f) => f.document_id === documentId)

  const focusField = (e: Extraction) => {
    setSelected(e.id)
    if (e.page) setHighlight({ page: e.page, bbox: e.bbox })
  }

  return (
    <>
      <p>
        <Link to={`/deals/${dealId}`}>← {deal?.name ?? 'deal'}</Link>
        {'  '}
        <strong>{doc?.filename}</strong>{' '}
        <span className="badge chip">{doc?.doc_type ?? 'unclassified'}</span>{' '}
        <span className="muted">
          {doc?.language} · {(100 * (doc?.classification_confidence ?? 0)).toFixed(0)}%
          classification confidence
        </span>
      </p>
      <div className="split">
        <div className="left">
          <div className="panel">
            <h2>Extracted fields ({extractions.length})</h2>
            <table className="grid">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Value</th>
                  <th>Conf.</th>
                </tr>
              </thead>
              <tbody>
                {extractions.map((e) => (
                  <tr
                    key={e.id}
                    className={`field-row clickable ${selected === e.id ? 'selected' : ''}`}
                    title={e.text_span ?? ''}
                    onClick={() => focusField(e)}
                  >
                    <td className="mono">{e.field_path}</td>
                    <td className={e.abstained ? 'abstained' : ''}>
                      {e.abstained ? 'abstained → human review' : formatValue(e.value)}
                    </td>
                    <td className="conf">{(e.confidence * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted" style={{ fontSize: '0.8rem' }}>
              Click a row to highlight the source clause in the document. Abstained fields
              were not reliably extractable and are never guessed.
            </p>
          </div>
          <div className="panel">
            <h2>Findings on this document ({docFindings.length})</h2>
            {docFindings.map((f) => (
              <FindingCard
                key={f.id}
                finding={f}
                docNames={docNames}
                onCitationClick={(c) => {
                  if (c.document_id === documentId && c.page) {
                    setHighlight({ page: c.page, bbox: c.bbox })
                  }
                }}
                onReviewed={(updated) =>
                  setFindings((fs) => fs.map((x) => (x.id === updated.id ? updated : x)))
                }
              />
            ))}
            {docFindings.length === 0 && <p className="muted">None.</p>}
          </div>
        </div>
        <div className="right">
          <PdfViewer fileUrl={api.pdfUrl(documentId)} highlight={highlight} />
        </div>
      </div>
    </>
  )
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (Array.isArray(v)) return `${v.length} item(s): ${JSON.stringify(v).slice(0, 160)}…`
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
