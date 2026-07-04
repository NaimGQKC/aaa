"""Native PDF report builder using fpdf2.

Why fpdf2 (not WeasyPrint): it's already a dependency, pure-wheel on every OS
including Windows/Python 3.14, and needs no system libraries. It renders the
report directly from the report context (not from HTML), so there are no
CSS-engine surprises. The core Helvetica font is Latin-1 only, so text is
sanitised (smart quotes / em-dashes → ASCII); accented ES/FR letters are kept.
"""

from __future__ import annotations

from typing import Any

from fpdf import FPDF

SEV_COLOR = {
    "high": (179, 38, 30),
    "medium": (178, 106, 0),
    "low": (95, 99, 104),
    "info": (42, 111, 151),
}
INK = (26, 33, 43)
MUTED = (91, 103, 115)
ACCENT = (28, 78, 128)

_REPL = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "•": "-",
    " ": " ", "→": "->", "­": "",
}


def _s(text: Any) -> str:
    if text is None:
        return ""
    t = str(text)
    for k, v in _REPL.items():
        t = t.replace(k, v)
    return t.encode("latin-1", "replace").decode("latin-1")


class _Report(FPDF):
    is_draft = False

    def footer(self) -> None:
        self.set_y(-28)
        self.set_font("Helvetica", size=7)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")
        if self.is_draft:
            # Accountability travels with every page of the artifact.
            self.set_y(-28)
            self.set_font("Helvetica", "B", 7)
            self.set_text_color(*SEV_COLOR["high"])
            self.cell(0, 10, "DRAFT - human review incomplete", align="R")


def _h1(pdf: _Report, text: str) -> None:
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 20, _s(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(1)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(6)
    pdf.set_text_color(*INK)


def build_pdf(ctx: dict) -> bytes:
    oversight = ctx.get("oversight") or {}
    pdf = _Report(format="A4", unit="pt")
    pdf.is_draft = bool(oversight.get("is_draft"))
    pdf.set_auto_page_break(True, margin=42)
    pdf.alias_nb_pages()
    pdf.set_margins(42, 42, 42)
    pdf.add_page()

    # ---- title -------------------------------------------------------------
    deal = ctx["deal"]
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 22, _s(f"Due Diligence Report — {deal.name}"),
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(*MUTED)
    juris = ", ".join(deal.jurisdiction or [])
    pdf.multi_cell(
        0, 12,
        _s(f"Generated {ctx['generated_at']} · Jurisdictions: {juris} · "
           f"{len(ctx['documents'])} documents · report id {ctx['report_id']}"),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_text_color(*INK)

    # ---- oversight status banner (Law 4: the artifact carries the state) ---
    pdf.ln(8)
    if pdf.is_draft:
        color, fill = SEV_COLOR["high"], (253, 236, 234)
        outstanding = oversight.get("spot_checks_total", 0) - oversight.get("spot_checks_done", 0)
        msg = (f"DRAFT - {oversight.get('pending', 0)} of "
               f"{oversight.get('findings_total', 0)} findings await human review")
        if outstanding > 0:
            msg += f", {outstanding} spot-check(s) outstanding"
        msg += ". This report is not signed off."
    else:
        color, fill = (30, 125, 67), (233, 247, 239)
        msg = (f"HUMAN-REVIEWED - all {oversight.get('findings_total', 0)} findings "
               f"adjudicated")
        if oversight.get("spot_checks_done"):
            msg += (f" · spot-check agreement {oversight.get('spot_checks_matched', 0)}"
                    f"/{oversight.get('spot_checks_done', 0)}")
        if oversight.get("reviewers"):
            msg += f" · reviewers: {', '.join(oversight['reviewers'])}"
    pdf.set_draw_color(*color)
    pdf.set_fill_color(*fill)
    pdf.set_text_color(*color)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_line_width(1.5)
    pdf.multi_cell(0, 16, _s(f"  {msg}"), border=1, fill=True,
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)

    # ---- 1. executive summary ---------------------------------------------
    _h1(pdf, "1. Executive summary")
    pdf.set_font("Helvetica", size=9.5)
    pdf.multi_cell(
        0, 14,
        _s(f"{ctx['n_high']} high-severity, {ctx['n_medium']} medium-severity and "
           f"{ctx['n_low_info']} low/informational findings across "
           f"{len(ctx['documents'])} documents. Every conclusion cites its source "
           "clause. This report is decision-support for professional reviewers; "
           "it does not replace legal advice."),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(4)
    for label, n, sev in (
        ("HIGH", ctx["n_high"], "high"),
        ("MEDIUM", ctx["n_medium"], "medium"),
        ("LOW / INFO", ctx["n_low_info"], "low"),
    ):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*SEV_COLOR[sev])
        pdf.cell(90, 14, label)
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 14, str(n), new_x="LMARGIN", new_y="NEXT")

    # ---- 2. findings -------------------------------------------------------
    _h1(pdf, "2. Findings")
    if not ctx["findings"]:
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 14, "No findings.", new_x="LMARGIN", new_y="NEXT")
    for f in ctx["findings"]:
        sev = f["severity"]
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*SEV_COLOR.get(sev, MUTED))
        pdf.multi_cell(0, 14, _s(f"[{sev.upper()}] {f['title']}"),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*MUTED)
        pdf.set_font("Helvetica", size=8)
        meta = f"{f['category']}"
        if f.get("doc_name"):
            meta += f" · {f['doc_name']}"
        meta += f" · review: {f['human_status']}"
        pdf.multi_cell(0, 11, _s(meta), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", size=9)
        if f.get("description"):
            pdf.multi_cell(0, 12, _s(f["description"]), new_x="LMARGIN", new_y="NEXT")
        for c in f.get("citations", []):
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(*MUTED)
            src = f"Source: {c.get('doc_name', '?')}"
            if c.get("page"):
                src += f", p.{c['page']}"
            if c.get("text_span"):
                src += f" — \"{c['text_span']}\""
            pdf.multi_cell(0, 11, _s(src), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*INK)
        pdf.ln(5)

    # ---- 3. per-document abstracts ----------------------------------------
    _h1(pdf, "3. Per-document abstracts")
    for d in ctx["documents"]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(
            0, 14,
            _s(f"{d['filename']}  ({d['doc_type'] or 'unclassified'}, "
               f"{d['language'] or '?'}, {d['page_count'] or '?'} pp, "
               f"{100 * (d['classification_confidence'] or 0):.0f}% classification)"),
            new_x="LMARGIN", new_y="NEXT",
        )
        if not d["fields"]:
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(*MUTED)
            pdf.cell(0, 12, "No registered schema — routed to human review.",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*INK)
            pdf.ln(4)
            continue
        pdf.set_font("Helvetica", size=8)
        with pdf.table(width=pdf.epw, col_widths=(34, 30, 26, 10),
                       first_row_as_headings=True, line_height=11) as table:
            hdr = table.row()
            for h in ("Field", "Value", "Source", "Conf"):
                hdr.cell(h)
            for e in d["fields"]:
                r = table.row()
                r.cell(_s(e["field_path"]))
                r.cell("abstained" if e["abstained"] else _s(e["value"])[:120])
                src = f"p.{e['page']}" if e["page"] else ""
                if e.get("text_span"):
                    src += f" \"{_s(e['text_span'])[:60]}\""
                r.cell(_s(src))
                r.cell(f"{100 * (e['confidence'] or 0):.0f}%")
        pdf.ln(6)

    # ---- 4. reconciliation -------------------------------------------------
    _h1(pdf, "4. Reconciliation")
    recon = ctx["reconciliations"]
    if not recon:
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 14, "No reconciliation rules ran.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", size=8)
        with pdf.table(width=pdf.epw, col_widths=(24, 16, 16, 44),
                       first_row_as_headings=True, line_height=11) as table:
            hdr = table.row()
            for h in ("Rule", "Status", "Severity", "Details"):
                hdr.cell(h)
            for r in recon:
                row = table.row()
                row.cell(_s(r.rule_key))
                row.cell(_s(r.status))
                row.cell(_s(r.severity))
                row.cell(_s(r.details)[:180])

    # ---- 5. human oversight record ------------------------------------------
    _h1(pdf, "5. Human oversight record")
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0, 11,
        _s("Anti-automation-bias controls (EU AI Act Art. 14(4)(b)): findings are "
           "adjudicated by named reviewers with mandatory reasons; the system "
           "samples its own high-confidence extractions for human spot-checking."),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_text_color(*INK)
    pdf.ln(2)
    pdf.set_font("Helvetica", size=8.5)
    sc_done = oversight.get("spot_checks_done", 0)
    rows = [
        ("Findings adjudicated",
         f"{oversight.get('findings_reviewed', 0)} / {oversight.get('findings_total', 0)}"),
        ("Spot-checks completed",
         f"{sc_done} / {oversight.get('spot_checks_total', 0)}"),
        ("Spot-check agreement",
         f"{oversight.get('spot_checks_matched', 0)}/{sc_done}" if sc_done else "-"),
        ("Reviewers", ", ".join(oversight.get("reviewers") or []) or "-"),
        ("Report status", "DRAFT" if pdf.is_draft else "Human-reviewed"),
    ]
    with pdf.table(width=pdf.epw * 0.7, col_widths=(40, 60),
                   first_row_as_headings=False, line_height=13) as table:
        for label, value in rows:
            r = table.row()
            r.cell(label)
            r.cell(_s(value))

    # ---- 6. audit annex ----------------------------------------------------
    _h1(pdf, "6. Audit annex")
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0, 11,
        _s("Engineered to EU AI Act Article 12 (record-keeping) and Article 26(6) "
           "(log retention >= 6 months). Append-only hash chain; integrity is "
           "verifiable end-to-end."),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_text_color(*INK)
    pdf.ln(2)
    pdf.set_font("Helvetica", size=7.5)
    with pdf.table(width=pdf.epw, col_widths=(6, 22, 18, 22, 20, 14),
                   first_row_as_headings=True, line_height=10) as table:
        hdr = table.row()
        for h in ("#", "Time (UTC)", "Event", "Actor", "Model", "Hash"):
            hdr.cell(h)
        for a in ctx["audit_events"]:
            row = table.row()
            row.cell(str(a.id))
            row.cell(_s(str(a.timestamp)[:19]))
            row.cell(_s(a.event_type))
            row.cell(_s(a.actor or ""))
            row.cell(_s(a.model_version or ""))
            row.cell(_s((a.hash or "")[:12]))

    return bytes(pdf.output())
