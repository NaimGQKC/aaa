"""Red-flag rules engine (spec §3.2/§3.3): deterministic per-document rules
plus the EPC/EPBD rule tables from dd_schemas. Every finding is cited back to
the extraction it came from."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Deal, Document, Extraction, Finding
from dd_schemas.epc_rules import assess_epc


def _fields(db: Session, document_id: str) -> dict[str, Extraction]:
    rows = (
        db.execute(
            select(Extraction).where(
                Extraction.document_id == document_id,
                Extraction.abstained == False,  # noqa: E712
            )
        )
        .scalars()
        .all()
    )
    return {r.field_path: r for r in rows}


def _abstained(db: Session, document_id: str) -> set[str]:
    rows = (
        db.execute(
            select(Extraction.field_path).where(
                Extraction.document_id == document_id,
                Extraction.abstained == True,  # noqa: E712
            )
        )
        .scalars()
        .all()
    )
    return set(rows)


def _cite(*exs: Extraction | None) -> list[dict[str, Any]]:
    return [
        {
            "document_id": e.document_id,
            "page": e.page_number,
            "bbox": e.bbox,
            "text_span": e.text_span,
            "field_path": e.field_path,
        }
        for e in exs
        if e is not None
    ]


def _finding(
    db: Session, deal: Deal, doc: Document | None, *,
    category: str, severity: str, title: str, description: str,
    citations: list[dict] | None = None, rule_key: str = "",
    confidence: float = 0.9,
) -> None:
    db.add(Finding(
        deal_id=deal.id,
        document_id=doc.id if doc else None,
        category=category, severity=severity,
        title=title, description=description,
        citations=citations or [], rule_key=rule_key or category,
        confidence=confidence,
    ))


def run_redflags(db: Session, deal: Deal) -> int:
    docs = db.execute(select(Document).where(Document.deal_id == deal.id)).scalars().all()
    today = datetime.now(timezone.utc).date()

    for doc in docs:
        f = _fields(db, doc.id)
        missing = _abstained(db, doc.id)
        if doc.doc_type == "nota_simple_es":
            _nota_simple_flags(db, deal, doc, f, today)
        elif doc.doc_type == "lease_es":
            _lease_es_flags(db, deal, doc, f, missing)
        elif doc.doc_type == "bail_commercial_fr":
            _bail_fr_flags(db, deal, doc, f, missing, today)
        elif doc.doc_type == "rent_roll":
            _rent_roll_flags(db, deal, doc, f)
        elif doc.doc_type in (None, "unknown"):
            _finding(
                db, deal, doc,
                category="unclassified_document", severity="low",
                title=f"Unclassified document: {doc.filename}",
                description=(
                    "This document did not match a registered type — extraction "
                    "was abstained and it requires human review (tiered-"
                    "confidence design: abstention over hallucination)."
                ),
                confidence=1.0,
            )

        # Low OCR confidence -> human triage regardless of type.
        low_conf = [
            e for e in f.values()
            if e.confidence is not None and float(e.confidence) < 0.7
        ]
        if low_conf:
            _finding(
                db, deal, doc,
                category="low_confidence_extraction", severity="low",
                title=f"{len(low_conf)} low-confidence field(s) in {doc.filename}",
                description="Fields extracted below the review threshold; verify manually.",
                citations=_cite(*low_conf[:5]),
                confidence=1.0,
            )

    db.flush()
    return db.query(Finding).filter(Finding.deal_id == deal.id).count()


# --------------------------------------------------------------------------
def _nota_simple_flags(
    db: Session, deal: Deal, doc: Document, f: dict[str, Extraction], today: date
) -> None:
    cargas_ex = f.get("cargas")
    cargas = list(cargas_ex.value_json or []) if cargas_ex else []
    for i, carga in enumerate(cargas):
        tipo = str(carga.get("tipo", "carga"))
        sev = "high" if tipo in ("hipoteca", "embargo", "condición resolutoria") else "medium"
        importe = carga.get("importe")
        acreedor = carga.get("acreedor")
        desc = f"Subsisting charge on title: {tipo}"
        if acreedor:
            desc += f" in favour of {acreedor}"
        if importe:
            desc += f", principal EUR {float(importe):,.0f}"
        desc += ". Must be cancelled or discharged at/before completion."
        cite_ex = f.get(f"cargas[{i}].tipo") or cargas_ex
        _finding(
            db, deal, doc, category="title_charge", severity=sev,
            title=f"Title charge: {tipo}",
            description=desc, citations=_cite(cite_ex),
            rule_key="nota_cargas",
        )
    if cargas_ex and not cargas:
        _finding(
            db, deal, doc, category="title_clear", severity="info",
            title="Title free of charges (libre de cargas)",
            description="The nota simple records no subsisting charges.",
            citations=_cite(cargas_ex), rule_key="nota_cargas",
        )

    fecha_ex = f.get("fecha_emision")
    if fecha_ex and fecha_ex.value_json:
        try:
            issued = date.fromisoformat(str(fecha_ex.value_json))
            if (today - issued).days > 90:
                _finding(
                    db, deal, doc, category="stale_title_extract", severity="medium",
                    title="Nota simple older than 3 months",
                    description=(
                        f"Issued {issued.isoformat()} — banks typically require a "
                        "nota simple under 3 months old; order a fresh extract."
                    ),
                    citations=_cite(fecha_ex), rule_key="nota_age",
                )
        except ValueError:
            pass

    regimen_ex = f.get("descripcion.regimen_especial")
    if regimen_ex and regimen_ex.value_json:
        _finding(
            db, deal, doc, category="special_regime", severity="medium",
            title=f"Special protection regime: {regimen_ex.value_json}",
            description="VPO/protection regimes restrict price and transferability.",
            citations=_cite(regimen_ex), rule_key="nota_regimen",
        )


def _lease_es_flags(
    db: Session, deal: Deal, doc: Document, f: dict[str, Extraction], missing: set[str]
) -> None:
    renta_ex = f.get("renta_mensual_eur")
    fianza_ex = f.get("fianza_eur")
    if renta_ex and fianza_ex and renta_ex.value_json and fianza_ex.value_json:
        renta, fianza = float(renta_ex.value_json), float(fianza_ex.value_json)
        if fianza < 2 * renta - 0.01:
            _finding(
                db, deal, doc, category="deposit_below_statutory", severity="medium",
                title="Deposit below LAU statutory minimum (2 months)",
                description=(
                    f"Fianza EUR {fianza:,.0f} < 2× monthly rent EUR {renta:,.0f} "
                    "(LAU art. 36 minimum for non-housing use is two monthly rents)."
                ),
                citations=_cite(fianza_ex, renta_ex), rule_key="lau_fianza",
            )
    if "actualizacion_renta" in missing:
        _finding(
            db, deal, doc, category="indexation_missing", severity="medium",
            title="Rent indexation clause not found",
            description=(
                "No rent-review/IPC indexation clause was extracted — without "
                "it the rent cannot be updated during the term."
            ),
            rule_key="lau_indexation",
        )
    res_ex = f.get("clausula_resolutoria")
    if res_ex and res_ex.value_json:
        _finding(
            db, deal, doc, category="lease_break", severity="medium",
            title="Early-termination / break clause present",
            description=f"Lease provides: {str(res_ex.value_json)[:300]}",
            citations=_cite(res_ex), rule_key="lau_break",
        )
    ibi_ex = f.get("gastos.ibi")
    if ibi_ex and ibi_ex.value_json and "arrendador" in str(ibi_ex.value_json).lower():
        _finding(
            db, deal, doc, category="cost_allocation", severity="info",
            title="IBI borne by landlord",
            description="Property tax not recharged to tenant — factor into NOI.",
            citations=_cite(ibi_ex), rule_key="lau_ibi",
        )


def _bail_fr_flags(
    db: Session, deal: Deal, doc: Document, f: dict[str, Extraction],
    missing: set[str], today: date,
) -> None:
    idx_ex = f.get("clause_indexation.index")
    idx = str(idx_ex.value_json).upper() if idx_ex and idx_ex.value_json else None
    if idx == "ICC":
        _finding(
            db, deal, doc, category="invalid_index", severity="high",
            title="Indexation clause references ICC — clause validity risk",
            description=(
                "ICC is no longer a valid exclusive index for commercial leases "
                "concluded/renewed since loi Pinel (1 Sept 2014); indexation must "
                "use ILC (commerce/artisanal) or ILAT (tertiary/offices). An "
                "ICC-based clause may be void, blocking rent revision for the "
                "whole term."
            ),
            citations=_cite(idx_ex), rule_key="fr_index_icc",
        )
    dest_ex = f.get("destination")
    if idx and dest_ex and dest_ex.value_json:
        dest = str(dest_ex.value_json).lower()
        is_tertiary = any(w in dest for w in ("bureau", "tertiaire", "office"))
        if is_tertiary and idx == "ILC":
            _finding(
                db, deal, doc, category="index_use_mismatch", severity="medium",
                title="ILC index on tertiary/office premises (expect ILAT)",
                description=(
                    "Offices/tertiary use normally indexes on ILAT; ILC applies "
                    "to commerce/artisanal. Verify the clause is enforceable."
                ),
                citations=_cite(idx_ex, dest_ex), rule_key="fr_index_use",
            )
    if "clause_indexation.index" in missing:
        _finding(
            db, deal, doc, category="indexation_missing", severity="medium",
            title="Indexation clause not found",
            description="No ILC/ILAT indexation clause extracted from the bail.",
            rule_key="fr_index_missing",
        )
    if "charges.inventaire_limitatif" in missing:
        _finding(
            db, deal, doc, category="charge_inventory_missing", severity="medium",
            title="Limitative charge inventory not found (Pinel L.145-40-2)",
            description=(
                "Since loi Pinel a limitative inventory of charges must be "
                "annexed; without it the tenant can contest recharged charges."
            ),
            rule_key="fr_charges_inventory",
        )
    duree_ex = f.get("duree_ans")
    if duree_ex and duree_ex.value_json and float(duree_ex.value_json) < 9:
        _finding(
            db, deal, doc, category="duration_below_statutory", severity="high",
            title=f"Duration {duree_ex.value_json} years below the statutory 9-year minimum",
            description="A bail commercial must run at least 9 years (L.145-4).",
            citations=_cite(duree_ex), rule_key="fr_duree",
        )
    tri_ex = f.get("faculte_resiliation_triennale")
    if tri_ex and tri_ex.value_json and "renonc" not in str(tri_ex.value_json).lower():
        _finding(
            db, deal, doc, category="lease_break", severity="medium",
            title="Tenant triennial break right (3/6/9)",
            description=(
                "Tenant may terminate at each triennial period with 6 months' "
                "notice — model income at each break date."
            ),
            citations=_cite(tri_ex), rule_key="fr_triennale",
        )
    if "diagnostics.erp" in missing:
        _finding(
            db, deal, doc, category="diagnostics_missing", severity="medium",
            title="État des risques et pollutions (ERP) not found",
            description="The ERP annex is mandatory for the bail commercial.",
            rule_key="fr_erp",
        )
    # EPC/EPBD rule tables
    dpe_ex = f.get("diagnostics.dpe_classe")
    dpe = str(dpe_ex.value_json).upper() if dpe_ex and dpe_ex.value_json else None
    for epc_finding in assess_epc(
        country="FR", epc_class=dpe, asset_is_let_or_for_let=True,
        residential=False, today=today,
    ):
        _finding(
            db, deal, doc, category=epc_finding.category,
            severity=epc_finding.severity, title=epc_finding.title,
            description=epc_finding.description,
            citations=_cite(dpe_ex), rule_key="epc_rules_fr",
        )


def _rent_roll_flags(db: Session, deal: Deal, doc: Document, f: dict[str, Extraction]) -> None:
    units_ex = f.get("units")
    units = list(units_ex.value_json or []) if units_ex else []
    arrears = [u for u in units if u.get("arrears") and float(u["arrears"]) > 0]
    if arrears:
        total = sum(float(u["arrears"]) for u in arrears)
        _finding(
            db, deal, doc, category="arrears", severity="medium",
            title=f"Arrears on {len(arrears)} unit(s): EUR {total:,.0f}",
            description=", ".join(
                f"{u.get('tenant_name', u.get('unit_id'))}: EUR {float(u['arrears']):,.0f}"
                for u in arrears
            ),
            citations=_cite(units_ex), rule_key="rr_arrears",
        )
    vacant = [u for u in units if u.get("vacancy_flag")]
    if vacant:
        _finding(
            db, deal, doc, category="vacancy", severity="info",
            title=f"{len(vacant)} vacant unit(s)",
            description=", ".join(str(u.get("unit_id")) for u in vacant),
            citations=_cite(units_ex), rule_key="rr_vacancy",
        )
