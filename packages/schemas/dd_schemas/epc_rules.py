"""EPC / EPBD rule tables.

- France: hard DPE letting-ban calendar (loi Climat & Résilience). NOTE: the
  bans stem from residential decency law; for commercial assets we frame the
  calendar as compliance-trajectory / capex risk, not a hard letting ban.
- Spain: CEE (RD 390/2021) validity rules + EPBD-trajectory flags (no hard
  letter bans transposed as of mid-2026).
- EPBD (EU) 2024/1275 art. 9(1): non-residential MEPS — worst 16% of stock
  renovated by 2030, 26% by 2033; national thresholds due by 1 Jan 2027.
  Encoded as a configurable per-country table with 'pending' status.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

Severity = str  # 'high' | 'medium' | 'low' | 'info'

# --- France: DPE letting-ban calendar (metropolitan France) -----------------
FR_LETTING_BAN_DATES: dict[str, date] = {
    "G": date(2025, 1, 1),
    "F": date(2028, 1, 1),
    "E": date(2034, 1, 1),
}

# --- Spain: CEE validity (RD 390/2021) --------------------------------------
ES_CEE_VALIDITY_YEARS = 10
ES_CEE_VALIDITY_YEARS_IF_G = 5

# --- EPBD non-residential MEPS: configurable national threshold table -------
@dataclass(frozen=True)
class MepsEntry:
    country: str
    status: str            # 'transposed' | 'pending'
    worst_bands: tuple[str, ...]  # bands treated as renovation-exposed
    milestone_2030: str
    milestone_2033: str
    note: str

EPBD_MEPS_TABLE: dict[str, MepsEntry] = {
    "ES": MepsEntry(
        country="ES", status="pending", worst_bands=("E", "F", "G"),
        milestone_2030="worst 16% of non-residential stock renovated",
        milestone_2033="worst 26% of non-residential stock renovated",
        note=(
            "National thresholds not yet published (transposition deadline "
            "29 May 2026; MEPS due 1 Jan 2027). Flag worst bands as capex/"
            "renovation-trajectory risk, not a hard ban."
        ),
    ),
    "FR": MepsEntry(
        country="FR", status="pending", worst_bands=("E", "F", "G"),
        milestone_2030="worst 16% of non-residential stock renovated",
        milestone_2033="worst 26% of non-residential stock renovated",
        note=(
            "For let residential assets the loi Climat & Résilience ban "
            "calendar applies in addition (G since 2025, F from 2028, E from "
            "2034); for commercial assets treat as trajectory/capex risk."
        ),
    ),
}


@dataclass(frozen=True)
class EpcFinding:
    severity: Severity
    category: str
    title: str
    description: str


def assess_epc(
    *,
    country: str,
    epc_class: str | None,
    asset_is_let_or_for_let: bool = True,
    residential: bool = False,
    epc_issue_date: date | None = None,
    today: date | None = None,
) -> list[EpcFinding]:
    """Apply the country rule tables to one asset's EPC data."""
    today = today or date.today()
    findings: list[EpcFinding] = []
    if not epc_class:
        findings.append(EpcFinding(
            severity="medium", category="epc_missing",
            title="EPC certificate missing",
            description=(
                f"No EPC class found for this {country} asset. An EPC is "
                "mandatory on sale/lease (ES: CEE under RD 390/2021; FR: DPE)."
            ),
        ))
        return findings
    epc_class = epc_class.strip().upper()

    # Certificate validity (ES rules; FR DPE validity is 10y as well).
    if epc_issue_date is not None:
        years = ES_CEE_VALIDITY_YEARS_IF_G if epc_class == "G" else ES_CEE_VALIDITY_YEARS
        age_days = (today - epc_issue_date).days
        if age_days > years * 365:
            findings.append(EpcFinding(
                severity="medium", category="epc_expired",
                title=f"EPC certificate expired (class {epc_class})",
                description=(
                    f"Certificate issued {epc_issue_date.isoformat()} exceeds "
                    f"the {years}-year validity"
                    + (" (5 years for class G under RD 390/2021)" if epc_class == "G" and country == "ES" else "")
                    + "."
                ),
            ))

    if country == "FR":
        ban_date = FR_LETTING_BAN_DATES.get(epc_class)
        if ban_date:
            years_to_ban = (ban_date - today).days / 365.25
            if residential:
                if ban_date <= today:
                    findings.append(EpcFinding(
                        severity="high", category="epc_ban",
                        title=f"DPE class {epc_class}: letting ban in force",
                        description=(
                            f"Class {epc_class} residential assets cannot be newly "
                            f"let since {ban_date.isoformat()} (loi Climat & Résilience)."
                        ),
                    ))
                else:
                    sev = "high" if years_to_ban <= 3 else "medium"
                    findings.append(EpcFinding(
                        severity=sev, category="epc_ban_trajectory",
                        title=f"DPE class {epc_class}: letting ban from {ban_date.year}",
                        description=(
                            f"Class {epc_class} residential assets cannot be newly let "
                            f"from {ban_date.isoformat()} ({years_to_ban:.1f} years away)."
                        ),
                    ))
            elif asset_is_let_or_for_let:
                sev = "medium" if (ban_date <= today or years_to_ban <= 5) else "low"
                findings.append(EpcFinding(
                    severity=sev, category="epc_trajectory",
                    title=f"DPE class {epc_class}: energy-compliance trajectory risk",
                    description=(
                        f"Commercial asset with DPE class {epc_class}. The residential "
                        f"letting-ban calendar (class {epc_class}: {ban_date.isoformat()}) "
                        "does not directly ban letting commercial assets, but EPBD "
                        "non-residential MEPS (worst 16% renovated by 2030, 26% by "
                        "2033) creates renovation/capex exposure."
                    ),
                ))

    meps = EPBD_MEPS_TABLE.get(country)
    if meps and epc_class in meps.worst_bands and not residential:
        findings.append(EpcFinding(
            severity="medium" if epc_class in ("F", "G") else "low",
            category="epbd_meps",
            title=f"EPC class {epc_class}: EPBD MEPS renovation exposure ({meps.status})",
            description=(
                f"{meps.milestone_2030}; {meps.milestone_2033}. {meps.note}"
            ),
        ))
    return findings
