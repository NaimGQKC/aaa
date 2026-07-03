"""Rent roll / tenancy schedule (deal-level, usually tabular)."""

from dd_schemas.base import DocSchema, FieldSpec

RENT_ROLL = DocSchema(
    key="rent_roll",
    version="1.0",
    title="Rent roll / tenancy schedule",
    language="en",
    jurisdiction="EU",
    description=(
        "Tenancy schedule listing one row per unit: tenant, area, lease "
        "dates, passing rent, indexation, deposit, arrears; plus deal-level "
        "totals (total area, total passing rent, WAULT, occupancy)."
    ),
    classification_keywords=(
        "rent roll",
        "tenancy schedule",
        "passing rent",
        "wault",
        "occupancy",
        "estado de arrendamientos",
        "état locatif",
        "etat locatif",
    ),
    fields=(
        FieldSpec(
            path="units", type="array",
            description=(
                "One entry per unit with: unit_id, tenant_name, use, area_m2, "
                "lease_start, lease_end, break_date, passing_rent (annual EUR), "
                "rent_frequency, index, deposit, arrears, service_charge, "
                "vacancy_flag."
            ),
            labels=("Unit", "Unidad", "Lot"),
            required=True,
        ),
        FieldSpec(
            path="total_area_m2", type="number",
            description="Total lettable area, m².",
            labels=("Total area", "Superficie total", "Surface totale"),
            required=True,
        ),
        FieldSpec(
            path="total_passing_rent_eur", type="money",
            description="Total annual passing rent, EUR.",
            labels=("Total passing rent", "Renta total", "Loyer total"),
            required=True,
        ),
        FieldSpec(
            path="wault_years", type="number",
            description="Weighted average unexpired lease term, years.",
            labels=("WAULT",),
        ),
        FieldSpec(
            path="occupancy_pct", type="number",
            description="Occupancy percentage.",
            labels=("Occupancy", "Ocupación", "Taux d'occupation"),
        ),
    ),
)
