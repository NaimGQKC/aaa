"""Cited DD report generator (spec §5.4): executive summary -> findings by
severity (with citations) -> per-document abstracts -> reconciliation tables
-> EPC/EPBD matrix -> audit annex.

HTML is always produced; PDF via WeasyPrint and DOCX via python-docx when the
optional [reports] extras are installed (graceful fallback otherwise)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.models import (
    AuditEvent,
    Deal,
    Document,
    Extraction,
    Finding,
    Reconciliation,
    Report,
)
from app.storage import get_storage, report_key

log = logging.getLogger("report")

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}

TEMPLATE = Template(
    """<!-- report content -->
<meta charset="utf-8">
<title>DD Report — {{ deal.name }}</title>
<style>
  body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a;
         max-width: 900px; margin: 2rem auto; line-height: 1.5; padding: 0 1rem; }
  h1 { border-bottom: 3px solid #123; padding-bottom: .3rem; }
  h2 { margin-top: 2rem; border-bottom: 1px solid #ccc; }
  table { border-collapse: collapse; width: 100%; margin: .8rem 0; font-size: .9rem; }
  th, td { border: 1px solid #bbb; padding: .35rem .5rem; text-align: left; vertical-align: top; }
  th { background: #eef2f6; }
  .sev-high { color: #fff; background: #b3261e; padding: 0 .45em; border-radius: 3px; }
  .sev-medium { color: #fff; background: #b26a00; padding: 0 .45em; border-radius: 3px; }
  .sev-low { color: #fff; background: #5f6368; padding: 0 .45em; border-radius: 3px; }
  .sev-info { color: #fff; background: #2a6f97; padding: 0 .45em; border-radius: 3px; }
  .cite { font-size: .8rem; color: #444; background: #f6f6f2; border-left: 3px solid #999;
          padding: .3rem .6rem; margin: .3rem 0; }
  .meta { color: #555; font-size: .85rem; }
  .finding { margin: 1rem 0; padding: .6rem .8rem; border: 1px solid #ddd; border-radius: 4px; }
</style>
<h1>Due Diligence Report — {{ deal.name }}</h1>
<p class="meta">Generated {{ generated_at }} · Jurisdictions: {{ deal.jurisdiction | join(', ') }}
 · {{ documents | length }} documents · report id {{ report_id }}</p>

{% if oversight.is_draft %}
<div style="border:3px solid #b3261e; background:#fdecea; color:#7a1712;
            padding:.8rem 1rem; border-radius:6px; font-weight:700;">
  DRAFT — {{ oversight.pending }} of {{ oversight.findings_total }} findings await human
  review{% if oversight.spot_checks_done < oversight.spot_checks_total %},
  {{ oversight.spot_checks_total - oversight.spot_checks_done }} spot-check(s) outstanding{% endif %}.
  This report is not signed off.
</div>
{% else %}
<div style="border:3px solid #1e7d43; background:#e9f7ef; color:#14532d;
            padding:.8rem 1rem; border-radius:6px; font-weight:700;">
  HUMAN-REVIEWED — all {{ oversight.findings_total }} findings adjudicated
  {% if oversight.spot_checks_total %}· spot-check agreement
  {{ oversight.spot_checks_matched }}/{{ oversight.spot_checks_done }}{% endif %}
  {% if oversight.reviewers %}· reviewers: {{ oversight.reviewers | join(', ') }}{% endif %}.
</div>
{% endif %}

<h2>1. Executive summary</h2>
<p>{{ n_high }} high-severity, {{ n_medium }} medium-severity and {{ n_low_info }}
low/informational findings across {{ documents | length }} documents.
Every conclusion below cites its source clause (document, page, text span).
This report is decision-support for professional reviewers; it does not
replace legal advice.</p>
<table>
  <tr><th>Severity</th><th>Count</th></tr>
  <tr><td><span class="sev-high">HIGH</span></td><td>{{ n_high }}</td></tr>
  <tr><td><span class="sev-medium">MEDIUM</span></td><td>{{ n_medium }}</td></tr>
  <tr><td><span class="sev-low">LOW / INFO</span></td><td>{{ n_low_info }}</td></tr>
</table>

<h2>2. Findings</h2>
{% for f in findings %}
<div class="finding">
  <p><span class="sev-{{ f.severity }}">{{ f.severity | upper }}</span>
     <strong>{{ f.title }}</strong>
     <span class="meta">[{{ f.category }}{% if f.doc_name %} · {{ f.doc_name }}{% endif %}
     · review: {{ f.human_status }}{% if f.human_reason %} — {{ f.human_reason }}{% endif %}]</span></p>
  <p>{{ f.description }}</p>
  {% for c in f.citations %}
  <div class="cite">Source: {{ c.doc_name }}{% if c.page %}, p.{{ c.page }}{% endif %}
    {% if c.text_span %}— “{{ c.text_span }}”{% endif %}</div>
  {% endfor %}
</div>
{% else %}<p>No findings.</p>{% endfor %}

<h2>3. Per-document abstracts</h2>
{% for d in documents %}
<h3>{{ d.filename }} <span class="meta">({{ d.doc_type or 'unclassified' }},
 {{ d.language or '?' }}, {{ d.page_count or '?' }} pp,
 classification confidence {{ '%.0f%%' % (100 * (d.classification_confidence or 0)) }})</span></h3>
{% if d.fields %}
<table>
  <tr><th>Field</th><th>Value</th><th>Source (page · span)</th><th>Conf.</th></tr>
  {% for e in d.fields %}
  <tr>
    <td>{{ e.field_path }}</td>
    <td>{% if e.abstained %}<em>abstained</em>{% else %}{{ e.value }}{% endif %}</td>
    <td class="meta">{% if e.page %}p.{{ e.page }}{% endif %}
        {% if e.text_span %} · “{{ e.text_span[:120] }}”{% endif %}</td>
    <td>{{ '%.0f%%' % (100 * (e.confidence or 0)) }}</td>
  </tr>
  {% endfor %}
</table>
{% else %}<p class="meta">No registered schema — routed to human review.</p>{% endif %}
{% endfor %}

<h2>4. Reconciliation</h2>
<table>
  <tr><th>Rule</th><th>Status</th><th>Severity</th><th>Details</th></tr>
  {% for r in reconciliations %}
  <tr><td>{{ r.rule_key }}</td><td>{{ r.status }}</td><td>{{ r.severity }}</td>
      <td class="meta">{{ r.details }}</td></tr>
  {% else %}<tr><td colspan="4">No reconciliation rules ran.</td></tr>
  {% endfor %}
</table>

<h2>5. EPC / EPBD compliance matrix</h2>
<table>
  <tr><th>Document</th><th>Finding</th><th>Severity</th><th>Detail</th></tr>
  {% for f in epc_findings %}
  <tr><td>{{ f.doc_name }}</td><td>{{ f.title }}</td>
      <td><span class="sev-{{ f.severity }}">{{ f.severity | upper }}</span></td>
      <td class="meta">{{ f.description }}</td></tr>
  {% else %}<tr><td colspan="4">No EPC findings.</td></tr>
  {% endfor %}
</table>

<h2>6. Human oversight record</h2>
<p class="meta">Anti-automation-bias controls (EU AI Act Art. 14(4)(b)): findings are
adjudicated by named reviewers with mandatory reasons; the system samples its own
high-confidence extractions for human spot-checking.</p>
<table>
  <tr><th>Control</th><th>Status</th></tr>
  <tr><td>Findings adjudicated</td>
      <td>{{ oversight.findings_reviewed }} / {{ oversight.findings_total }}</td></tr>
  <tr><td>Spot-checks completed</td>
      <td>{{ oversight.spot_checks_done }} / {{ oversight.spot_checks_total }}</td></tr>
  <tr><td>Spot-check agreement</td>
      <td>{% if oversight.spot_checks_done %}{{ oversight.spot_checks_matched }}/{{ oversight.spot_checks_done }}{% else %}—{% endif %}</td></tr>
  <tr><td>Reviewers</td>
      <td>{{ oversight.reviewers | join(', ') if oversight.reviewers else '—' }}</td></tr>
  <tr><td>Report status</td>
      <td>{{ 'DRAFT' if oversight.is_draft else 'Human-reviewed' }}</td></tr>
</table>

<h2>7. Audit annex</h2>
<p class="meta">Engineered to EU AI Act Article 12 (automatic record-keeping) and
Article 26(6) (log retention ≥ 6 months). The audit log is an append-only
hash chain; integrity is verifiable end-to-end.</p>
<table>
  <tr><th>#</th><th>Time (UTC)</th><th>Event</th><th>Actor</th><th>Model</th><th>Prompt</th><th>Hash (first 16)</th></tr>
  {% for a in audit_events %}
  <tr><td>{{ a.id }}</td><td>{{ a.timestamp }}</td><td>{{ a.event_type }}</td>
      <td>{{ a.actor }}</td><td>{{ a.model_version or '' }}</td>
      <td>{{ a.prompt_version or '' }}</td><td><code>{{ (a.hash or '')[:16] }}</code></td></tr>
  {% endfor %}
</table>
"""
)


def generate_report(db: Session, deal_id: str, actor: str = "report-service") -> Report:
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise ValueError(f"deal {deal_id} not found")

    docs = (
        db.execute(select(Document).where(Document.deal_id == deal_id).order_by(Document.filename))
        .scalars().all()
    )
    doc_names = {d.id: d.filename or d.id for d in docs}
    findings = (
        db.execute(select(Finding).where(Finding.deal_id == deal_id)).scalars().all()
    )
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.category))
    recon = (
        db.execute(select(Reconciliation).where(Reconciliation.deal_id == deal_id))
        .scalars().all()
    )
    audit = (
        db.execute(
            select(AuditEvent).where(AuditEvent.deal_id == deal_id).order_by(AuditEvent.id)
        ).scalars().all()
    )

    def render_finding(f: Finding) -> dict:
        return {
            "severity": f.severity, "category": f.category, "title": f.title,
            "description": f.description or "",
            "human_status": f.human_status, "human_reason": f.human_reason,
            "doc_name": doc_names.get(f.document_id or "", None),
            "citations": [
                {**c, "doc_name": doc_names.get(c.get("document_id", ""), "?")}
                for c in (f.citations or [])
            ],
        }

    doc_views = []
    for d in docs:
        fields = (
            db.execute(
                select(Extraction)
                .where(Extraction.document_id == d.id)
                .order_by(Extraction.field_path)
            ).scalars().all()
        )
        doc_views.append({
            "filename": d.filename, "doc_type": d.doc_type, "language": d.language,
            "page_count": d.page_count,
            "classification_confidence": float(d.classification_confidence or 0),
            "fields": [
                {
                    "field_path": e.field_path,
                    "value": e.value_json,
                    "abstained": e.abstained,
                    "page": e.page_number,
                    "text_span": e.text_span,
                    "confidence": float(e.confidence or 0),
                }
                for e in fields
            ],
        })

    report = Report(deal_id=deal_id)
    db.add(report)
    db.flush()

    from app.services.oversight import oversight_stats

    oversight = oversight_stats(db, deal_id)

    # One context, reused for HTML and PDF so the two never drift.
    ctx = dict(
        deal=deal,
        oversight=oversight,
        report_id=report.id,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        documents=doc_views,
        findings=[render_finding(f) for f in findings],
        n_high=sum(1 for f in findings if f.severity == "high"),
        n_medium=sum(1 for f in findings if f.severity == "medium"),
        n_low_info=sum(1 for f in findings if f.severity in ("low", "info")),
        reconciliations=recon,
        epc_findings=[
            render_finding(f) for f in findings
            if f.category.startswith(("epc", "epbd"))
        ],
        audit_events=audit,
    )
    html = TEMPLATE.render(**ctx)
    storage = get_storage()
    html_key = report_key(deal_id, report.id, "html")
    storage.put(html_key, ("<!doctype html><html><body>" + html + "</body></html>").encode())
    report.storage_key_html = html_key

    # PDF: native fpdf2 builder (always available, cross-platform). WeasyPrint
    # would render the HTML with higher fidelity but needs system libraries, so
    # it's only a best-effort upgrade when installed.
    pdf_bytes: bytes | None = None
    try:
        from weasyprint import HTML  # type: ignore

        pdf_bytes = HTML(string=html).write_pdf()
    except Exception:
        try:
            from app.services.pdf_report import build_pdf

            pdf_bytes = build_pdf(ctx)
        except Exception as exc:
            log.warning("PDF export failed (%s) — HTML report only", exc)
    if pdf_bytes:
        pdf_key = report_key(deal_id, report.id, "pdf")
        storage.put(pdf_key, pdf_bytes)
        report.storage_key_pdf = pdf_key

    try:  # optional: python-docx Word export
        report.storage_key_docx = _export_docx(
            storage, deal, report.id, doc_views, [render_finding(f) for f in findings]
        )
    except Exception as exc:
        log.info("DOCX export unavailable (%s)", exc)

    record_event(
        db, event_type="export", actor=actor, deal_id=deal_id,
        output_ref={"report_id": report.id, "html": html_key,
                    "pdf": bool(report.storage_key_pdf),
                    "docx": bool(report.storage_key_docx)},
    )
    db.flush()
    return report


def _export_docx(storage, deal: Deal, report_id: str, doc_views: list, findings: list) -> str:
    import io

    from docx import Document as Docx  # type: ignore

    dx = Docx()
    dx.add_heading(f"Due Diligence Report — {deal.name}", level=0)
    dx.add_heading("Findings", level=1)
    for f in findings:
        dx.add_heading(f"[{f['severity'].upper()}] {f['title']}", level=2)
        dx.add_paragraph(f["description"])
        for c in f["citations"]:
            dx.add_paragraph(
                f"Source: {c.get('doc_name')}, p.{c.get('page')} — “{c.get('text_span', '')}”",
                style="Intense Quote",
            )
    dx.add_heading("Document abstracts", level=1)
    for d in doc_views:
        dx.add_heading(f"{d['filename']} ({d['doc_type']})", level=2)
        for e in d["fields"]:
            val = "abstained" if e["abstained"] else e["value"]
            dx.add_paragraph(f"{e['field_path']}: {val}")
    buf = io.BytesIO()
    dx.save(buf)
    key = report_key(deal.id, report_id, "docx")
    storage.put(key, buf.getvalue())
    return key
