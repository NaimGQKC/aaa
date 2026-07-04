"""Vigilance instrumentation + calibrated-trust metrics (ERS §4, M7).

Two truths this module encodes, straight from the science:
- A near-ZERO override rate is a RED FLAG for automation bias, not proof of a
  good model (Art 14 implementation guidance / Art 26(5)).
- "Reliability" must come from THIS deployment's verified human dispositions,
  never from raw model confidence (Finding 4). We treat an accepted finding as
  a human-verified-correct signal and an overridden one as human-contested;
  spot-check matches/mismatches add ground truth on the extractions.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Deal, DealMember, Finding, SpotCheck

MIN_SAMPLES = 5  # below this we say "not enough verified data yet"


def _deal_ids_for_scope(db: Session, deal_id: str, org_scope: bool) -> list[str]:
    """Reliability is more meaningful across a team's whole history; scope to
    every deal that shares at least one member with this deal, else just this
    deal."""
    if not org_scope:
        return [deal_id]
    member_ids = [
        m.user_id for m in db.execute(
            select(DealMember).where(DealMember.deal_id == deal_id)
        ).scalars()
    ]
    if not member_ids:
        return [deal_id]
    peer_deals = set(
        db.execute(
            select(DealMember.deal_id).where(DealMember.user_id.in_(member_ids))
        ).scalars()
    )
    peer_deals.add(deal_id)
    return list(peer_deals)


def reliability_by_category(db: Session, deal_id: str) -> dict[str, dict]:
    """Per finding-category verified-correct rate from human dispositions
    across the team's deals. category -> {rate, n, verified, contested}."""
    deal_ids = _deal_ids_for_scope(db, deal_id, org_scope=True)
    rows = db.execute(
        select(Finding).where(
            Finding.deal_id.in_(deal_ids),
            Finding.human_status != "pending",
        )
    ).scalars().all()
    agg: dict[str, dict] = {}
    for f in rows:
        a = agg.setdefault(f.category, {"verified": 0, "contested": 0})
        if f.human_status == "accepted":
            a["verified"] += 1
        else:  # overridden
            a["contested"] += 1
    out: dict[str, dict] = {}
    for cat, a in agg.items():
        n = a["verified"] + a["contested"]
        out[cat] = {
            "n": n,
            "verified": a["verified"],
            "contested": a["contested"],
            "rate": round(a["verified"] / n, 3) if n else None,
            "enough_data": n >= MIN_SAMPLES,
        }
    return out


def vigilance_stats(db: Session, deal_id: str) -> dict:
    """Per-deal oversight-quality signals for the vigilance panel + Art 26(5)
    monitoring. Deliberately flags anomalously LOW override rates."""
    findings = db.execute(
        select(Finding).where(Finding.deal_id == deal_id)
    ).scalars().all()
    reviewed = [f for f in findings if f.human_status != "pending"]
    accepted = [f for f in reviewed if f.human_status == "accepted"]
    overridden = [f for f in reviewed if f.human_status == "overridden"]
    high = [f for f in findings if f.severity == "high"]
    high_reviewed = [f for f in high if f.human_status != "pending"]
    high_sourced = [f for f in high if f.source_viewed]

    checks = db.execute(select(SpotCheck).where(SpotCheck.deal_id == deal_id)).scalars().all()
    decided = [c for c in checks if c.status != "pending"]

    override_rate = (len(overridden) / len(reviewed)) if reviewed else None
    source_open_rate = (len(high_sourced) / len(high)) if high else None

    flags: list[dict] = []
    # counterintuitive but load-bearing: 0% override on a non-trivial sample
    if len(reviewed) >= MIN_SAMPLES and override_rate == 0.0:
        flags.append({
            "level": "warning",
            "code": "zero_override_rate",
            "message": (
                f"0% override across {len(reviewed)} reviewed findings. A near-zero "
                "override rate is a known automation-bias signal, not proof the AI "
                "was right — consider a second reviewer on accepted items."
            ),
        })
    if high and len(high_sourced) < len(high):
        flags.append({
            "level": "info",
            "code": "unsourced_high",
            "message": (
                f"{len(high) - len(high_sourced)} of {len(high)} high-severity findings "
                "not yet opened at source. High-severity dispositions require it."
            ),
        })
    if decided and (sum(1 for c in decided if c.status == "mismatch")):
        flags.append({
            "level": "warning",
            "code": "spot_check_mismatch",
            "message": f"{sum(1 for c in decided if c.status == 'mismatch')} spot-check(s) "
                       "failed — extraction quality issue confirmed by a human.",
        })

    return {
        "reviewed": len(reviewed),
        "accepted": len(accepted),
        "overridden": len(overridden),
        "override_rate": round(override_rate, 3) if override_rate is not None else None,
        "high_total": len(high),
        "high_reviewed": len(high_reviewed),
        "high_source_open_rate": round(source_open_rate, 3) if source_open_rate is not None else None,
        "spot_checks_decided": len(decided),
        "spot_checks_mismatch": sum(1 for c in decided if c.status == "mismatch"),
        "flags": flags,
    }


def certification_statement(certifier_name: str) -> str:
    """Pre-decisional, process-based certification language (Lerner & Tetlock
    1999). Explicitly NOT the discredited sign-at-the-top mechanic — this is
    presented as a statement of the process the certifier followed, to an
    audit audience."""
    return (
        f"I, {certifier_name}, have reviewed the findings in this report, opened "
        "and checked the flagged sources, and exercised independent professional "
        "judgment. My dispositions and this certification are logged and subject "
        "to independent review."
    )


def deal_reliability_scoped(db: Session, deal: Deal) -> dict[str, dict]:
    return reliability_by_category(db, deal.id)
