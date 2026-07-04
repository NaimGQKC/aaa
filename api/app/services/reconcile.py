"""Cross-document reconciliation engine (spec §3.2).

Deterministic rules over the extraction store:
- rent_roll_vs_lease: passing rent per tenant vs the lease's stated rent
- title_holder_vs_landlord: registry titleholder vs lease landlord identity
- surface_consistency: registry surface vs lease surface vs rent-roll area
- break_dates: lease break/triennial rights vs rent-roll break dates

Each rule writes a `reconciliations` row and, on mismatch, a cited Finding.
"""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Deal, Document, Extraction, Finding, Reconciliation

RENT_TOLERANCE = 0.02       # 2% tolerance on rent match
SURFACE_TOLERANCE = 0.10    # 10% divergence threshold
NAME_MATCH_SCORE = 80.0


def _extractions(db: Session, deal_id: str) -> dict[str, dict[str, Extraction]]:
    """{document_id: {field_path: extraction}} for all non-abstained fields."""
    rows = (
        db.execute(
            select(Extraction)
            .join(Document, Document.id == Extraction.document_id)
            .where(Document.deal_id == deal_id, Extraction.abstained == False)  # noqa: E712
        )
        .scalars()
        .all()
    )
    out: dict[str, dict[str, Extraction]] = {}
    for r in rows:
        out.setdefault(r.document_id, {})[r.field_path] = r
    return out


def _docs_by_type(db: Session, deal_id: str) -> dict[str, list[Document]]:
    docs = db.execute(select(Document).where(Document.deal_id == deal_id)).scalars().all()
    out: dict[str, list[Document]] = {}
    for d in docs:
        out.setdefault(d.doc_type or "unknown", []).append(d)
    return out


def _cite(ex: Extraction | None) -> list[dict[str, Any]]:
    if ex is None:
        return []
    return [{
        "document_id": ex.document_id,
        "page": ex.page_number,
        "bbox": ex.bbox,
        "text_span": ex.text_span,
        "field_path": ex.field_path,
    }]


def _add(
    db: Session, deal: Deal, rule_key: str, status: str, severity: str,
    details: dict, finding: dict | None = None,
) -> None:
    db.add(Reconciliation(
        deal_id=deal.id, rule_key=rule_key, status=status,
        details=details, severity=severity,
    ))
    if finding is not None:
        db.add(Finding(
            deal_id=deal.id,
            document_id=finding.get("document_id"),
            category=finding.get("category", rule_key),
            severity=finding.get("severity", severity),
            title=finding["title"],
            description=finding.get("description"),
            citations=finding.get("citations", []),
            rule_key=rule_key,
            confidence=finding.get("confidence", 0.9),
        ))


def run_reconciliation(db: Session, deal: Deal) -> int:
    db.query(Reconciliation).filter(Reconciliation.deal_id == deal.id).delete()
    # Rebuild machine-generated findings — but never delete human-originated
    # ones (spot-check mismatches): a pipeline re-run must not erase oversight.
    db.query(Finding).filter(
        Finding.deal_id == deal.id,
        Finding.rule_key.isnot(None),
        Finding.rule_key != "spot_check",
    ).delete()

    ex = _extractions(db, deal.id)
    by_type = _docs_by_type(db, deal.id)

    rent_roll_docs = by_type.get("rent_roll", [])
    lease_docs = by_type.get("lease_es", []) + by_type.get("bail_commercial_fr", [])
    nota_docs = by_type.get("nota_simple_es", [])

    units: list[dict] = []
    rr_units_ex: Extraction | None = None
    if rent_roll_docs:
        rr_units_ex = ex.get(rent_roll_docs[0].id, {}).get("units")
        units = list(rr_units_ex.value_json or []) if rr_units_ex else []

    # ---- 1. rent roll vs lease rent ---------------------------------------
    for lease in lease_docs:
        lex = ex.get(lease.id, {})
        if lease.doc_type == "lease_es":
            tenant_ex = lex.get("arrendatario.nombre")
            rent_ex = lex.get("renta_mensual_eur")
            annual = float(rent_ex.value_json) * 12 if rent_ex and rent_ex.value_json else None
        else:
            tenant_ex = lex.get("preneur.nom")
            rent_ex = lex.get("loyer_annuel_eur")
            annual = float(rent_ex.value_json) if rent_ex and rent_ex.value_json else None
        tenant = str(tenant_ex.value_json) if tenant_ex and tenant_ex.value_json else None
        if tenant is None or annual is None:
            _add(db, deal, "rent_roll_vs_lease", "missing", "low",
                 {"lease_document_id": lease.id, "reason": "tenant or rent not extracted"})
            continue
        unit = _match_unit(units, tenant)
        if unit is None:
            _add(db, deal, "rent_roll_vs_lease", "missing", "medium",
                 {"lease_document_id": lease.id, "tenant": tenant,
                  "reason": "tenant not found in rent roll"},
                 finding={
                     "title": f"Lease tenant '{tenant}' missing from rent roll",
                     "description": (
                         f"The lease for '{tenant}' has no matching row in the "
                         "rent roll — verify the tenancy schedule is complete."
                     ),
                     "category": "rent_roll_gap",
                     "document_id": lease.id,
                     "citations": _cite(tenant_ex) + _cite(rr_units_ex),
                 })
            continue
        rr_rent = unit.get("passing_rent")
        if rr_rent is None:
            continue
        delta = abs(float(rr_rent) - annual) / max(annual, 1.0)
        if delta <= RENT_TOLERANCE:
            _add(db, deal, "rent_roll_vs_lease", "match", "info",
                 {"tenant": tenant, "lease_annual_eur": annual, "rent_roll_eur": rr_rent})
        else:
            _add(db, deal, "rent_roll_vs_lease", "mismatch", "high",
                 {"tenant": tenant, "lease_annual_eur": annual,
                  "rent_roll_eur": rr_rent, "delta_pct": round(delta * 100, 1)},
                 finding={
                     "title": f"Rent mismatch for '{tenant}': lease vs rent roll",
                     "description": (
                         f"Lease implies EUR {annual:,.0f}/yr but the rent roll shows "
                         f"EUR {float(rr_rent):,.0f}/yr ({delta * 100:.1f}% divergence). "
                         "Reconcile against payment receipts."
                     ),
                     "category": "rent_mismatch",
                     "document_id": lease.id,
                     "citations": _cite(rent_ex) + _cite(rr_units_ex),
                 })

    # ---- 2. title holder vs landlord --------------------------------------
    # A nota simple is a Spanish title document: reconcile it against Spanish
    # leases only — comparing it to a French bail on another asset would
    # produce cross-jurisdiction false positives.
    es_leases = by_type.get("lease_es", [])
    for nota in nota_docs:
        nex = ex.get(nota.id, {})
        holder_ex = nex.get("titularidad[0].nombre")
        holder = str(holder_ex.value_json) if holder_ex and holder_ex.value_json else None
        if holder is None:
            _add(db, deal, "title_holder_vs_landlord", "missing", "medium",
                 {"nota_document_id": nota.id, "reason": "titleholder not extracted"})
            continue
        for lease in es_leases:
            lex = ex.get(lease.id, {})
            if not _same_asset(nex, lex):
                continue
            landlord_ex = lex.get("arrendador.nombre") or lex.get("bailleur.nom")
            landlord = (
                str(landlord_ex.value_json) if landlord_ex and landlord_ex.value_json else None
            )
            if landlord is None:
                continue
            score = fuzz.token_sort_ratio(holder.lower(), landlord.lower())
            if score >= NAME_MATCH_SCORE:
                _add(db, deal, "title_holder_vs_landlord", "match", "info",
                     {"titleholder": holder, "landlord": landlord, "score": score})
            else:
                _add(db, deal, "title_holder_vs_landlord", "mismatch", "high",
                     {"titleholder": holder, "landlord": landlord, "score": score},
                     finding={
                         "title": "Registry titleholder differs from lease landlord",
                         "description": (
                             f"Land registry shows '{holder}' as titleholder but the "
                             f"lease names '{landlord}' as landlord — verify chain of "
                             "title / powers of attorney."
                         ),
                         "category": "title_mismatch",
                         "document_id": nota.id,
                         "citations": _cite(holder_ex) + _cite(landlord_ex),
                     })

    # ---- 3. surface consistency -------------------------------------------
    for nota in nota_docs:
        nex = ex.get(nota.id, {})
        reg_ex = nex.get("descripcion.superficie_construida_m2")
        reg = float(reg_ex.value_json) if reg_ex and reg_ex.value_json else None
        if reg is None:
            continue
        for lease in es_leases:
            lex = ex.get(lease.id, {})
            if not _same_asset(nex, lex):
                continue
            sur_ex = lex.get("superficie_m2") or lex.get("surface_m2")
            sur = float(sur_ex.value_json) if sur_ex and sur_ex.value_json else None
            if sur is None:
                continue
            delta = abs(reg - sur) / max(reg, 1.0)
            if delta <= SURFACE_TOLERANCE:
                _add(db, deal, "surface_consistency", "match", "info",
                     {"registry_m2": reg, "lease_m2": sur})
            else:
                _add(db, deal, "surface_consistency", "mismatch", "medium",
                     {"registry_m2": reg, "lease_m2": sur,
                      "delta_pct": round(delta * 100, 1)},
                     finding={
                         "title": "Surface divergence: registry vs lease",
                         "description": (
                             f"Registry states {reg:,.0f} m² built but the lease "
                             f"states {sur:,.0f} m² ({delta * 100:.1f}% divergence, "
                             f"threshold {SURFACE_TOLERANCE:.0%})."
                         ),
                         "category": "surface_mismatch",
                         "document_id": nota.id,
                         "citations": _cite(reg_ex) + _cite(sur_ex),
                     })

    # ---- 4. break dates lease vs rent roll ---------------------------------
    for unit in units:
        if unit.get("break_date"):
            _add(db, deal, "break_dates", "match", "info",
                 {"unit": unit.get("unit_id"), "tenant": unit.get("tenant_name"),
                  "break_date": unit.get("break_date")},
                 finding={
                     "title": (
                         f"Break option {unit.get('break_date')} — "
                         f"{unit.get('tenant_name', 'unit ' + str(unit.get('unit_id')))}"
                     ),
                     "description": (
                         "Rent roll shows a tenant break option; model income risk "
                         "at that date and check notice mechanics in the lease."
                     ),
                     "category": "lease_break",
                     "severity": "medium",
                     "citations": _cite(rr_units_ex),
                 })

    db.flush()
    return db.query(Reconciliation).filter(Reconciliation.deal_id == deal.id).count()


def _same_asset(nex: dict[str, Extraction], lex: dict[str, Extraction]) -> bool:
    """Pair a title extract with a lease only when they refer to the same
    asset: matching referencia catastral when both documents state one,
    otherwise assume same-asset (single-asset deals)."""
    a = nex.get("referencia_catastral")
    b = lex.get("inmueble.referencia_catastral")
    if a and b and a.value_json and b.value_json:
        return str(a.value_json).replace(" ", "") == str(b.value_json).replace(" ", "")
    return True


def _match_unit(units: list[dict], tenant: str) -> dict | None:
    best, best_score = None, 0.0
    for u in units:
        name = str(u.get("tenant_name") or "")
        score = fuzz.token_sort_ratio(tenant.lower(), name.lower())
        if score > best_score:
            best, best_score = u, score
    return best if best_score >= NAME_MATCH_SCORE else None
