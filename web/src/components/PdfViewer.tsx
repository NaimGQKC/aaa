/**
 * react-pdf viewer with a synchronized bounding-box highlight overlay.
 *
 * Coordinate convention: bboxes arrive in PDF point space with a TOP-LEFT
 * origin (normalised at ingestion — spec §5.2), so overlay placement is a
 * pure scale: css_px = pdf_pt * (renderedWidth / pageWidthPt). Zoom-stable
 * by construction.
 */
import { useEffect, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import type { Bbox } from '../types'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

export interface Highlight {
  page: number
  bbox: Bbox | null
}

const RENDER_WIDTH = 640

export default function PdfViewer({
  fileUrl,
  highlight,
}: {
  fileUrl: string
  highlight: Highlight | null
}) {
  const [numPages, setNumPages] = useState(0)
  const [pageWidths, setPageWidths] = useState<Record<number, number>>({})
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({})

  useEffect(() => {
    if (highlight) {
      const el = pageRefs.current[highlight.page]
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [highlight])

  return (
    <Document
      file={fileUrl}
      onLoadSuccess={(doc) => setNumPages(doc.numPages)}
      loading={<p style={{ color: '#ddd' }}>Loading document…</p>}
      error={<p style={{ color: '#f99' }}>Failed to load PDF.</p>}
    >
      {Array.from({ length: numPages }, (_, i) => {
        const pageNo = i + 1
        const widthPt = pageWidths[pageNo]
        const scale = widthPt ? RENDER_WIDTH / widthPt : 1
        const hl = highlight && highlight.page === pageNo ? highlight.bbox : null
        return (
          <div
            key={pageNo}
            className="pdf-page-wrap"
            ref={(el) => {
              pageRefs.current[pageNo] = el
            }}
          >
            <Page
              pageNumber={pageNo}
              width={RENDER_WIDTH}
              onLoadSuccess={(page) => {
                const w = page.view[2] - page.view[0]
                setPageWidths((prev) => (prev[pageNo] === w ? prev : { ...prev, [pageNo]: w }))
              }}
            />
            {hl && widthPt && (
              <div
                className="bbox-highlight"
                style={{
                  left: hl.x1 * scale - 3,
                  top: hl.y1 * scale - 3,
                  width: (hl.x2 - hl.x1) * scale + 6,
                  height: (hl.y2 - hl.y1) * scale + 6,
                }}
              />
            )}
          </div>
        )
      })}
    </Document>
  )
}
