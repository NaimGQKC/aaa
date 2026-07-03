"""Bail commercial 3/6/9 (FR) — Code de commerce arts. L.145-1 à L.145-60.

Key statutory logic encoded downstream as red flags:
- Indexation index must be ILC (commerce/artisanal) or ILAT (tertiary/offices);
  ICC is no longer a valid exclusive index for leases concluded/renewed since
  loi Pinel (1 Sept 2014).
- Charge inventory (inventaire limitatif des charges) mandatory since Pinel,
  art. L.145-40-2.
- Triennial revision capped at ILC/ILAT variation (art. L.145-38).
- Leases concluded/renewed from 28 May 2026 may include a symmetric "tunnel"
  indexation cap.
"""

from dd_schemas.base import DocSchema, FieldSpec

BAIL_FR = DocSchema(
    key="bail_commercial_fr",
    version="1.0",
    title="Bail commercial 3/6/9",
    language="fr",
    jurisdiction="FR",
    description=(
        "French commercial lease (bail commercial 3/6/9) under Code de "
        "commerce L.145-1 ss.: parties, premises, rent, indexation, charges, "
        "duration, renewal and annexed diagnostics."
    ),
    classification_keywords=(
        "bail commercial",
        "preneur",
        "bailleur",
        "loyer",
        "code de commerce",
        "indexation",
        "3/6/9",
        "clause résolutoire",
    ),
    fields=(
        FieldSpec(
            path="bailleur.nom", type="string",
            description="Landlord (bailleur) name / dénomination sociale.",
            labels=("Bailleur", "BAILLEUR", "Le Bailleur"),
            required=True,
        ),
        FieldSpec(
            path="bailleur.siren", type="string",
            description="Landlord SIREN if a company.",
            labels=("SIREN du bailleur",),
        ),
        FieldSpec(
            path="preneur.nom", type="string",
            description="Tenant (preneur) name / dénomination sociale.",
            labels=("Preneur", "PRENEUR", "Le Preneur"),
            required=True,
        ),
        FieldSpec(
            path="preneur.siren", type="string",
            description="Tenant SIREN (see KBIS).",
            labels=("SIREN", "SIREN du preneur", "RCS"),
        ),
        FieldSpec(
            path="designation_locaux", type="string",
            description="Description/address of the leased premises.",
            labels=("Désignation", "Désignation des locaux", "Locaux loués"),
            required=True,
        ),
        FieldSpec(
            path="surface_m2", type="number",
            description="Leased surface in square metres.",
            labels=("Surface", "Superficie"),
            required=True,
        ),
        FieldSpec(
            path="destination", type="string",
            description="Destination clause ('tous commerces' or restricted use).",
            labels=("Destination", "Destination des lieux"),
            required=True,
        ),
        FieldSpec(
            path="duree_ans", type="number",
            description="Duration in years (statutory minimum 9).",
            labels=("Durée", "Durée du bail"),
            required=True,
        ),
        FieldSpec(
            path="date_effet", type="date",
            description="Effective date (date de prise d'effet).",
            labels=("Date d'effet", "Prise d'effet", "Date de prise d'effet"),
            required=True,
        ),
        FieldSpec(
            path="date_echeance", type="date",
            description="Expiry date (échéance).",
            labels=("Échéance", "Date d'échéance", "Echéance"),
        ),
        FieldSpec(
            path="loyer_annuel_eur", type="money",
            description="Initial annual rent, EUR excl. taxes (loyer initial HT).",
            labels=("Loyer annuel", "Loyer initial", "Loyer"),
            required=True,
        ),
        FieldSpec(
            path="periodicite", type="string",
            description="Payment periodicity (trimestrielle d'avance is standard).",
            labels=("Périodicité", "Modalités de paiement"),
        ),
        FieldSpec(
            path="clause_indexation.index", type="string",
            description="Indexation index: ILC, ILAT — or ICC (invalid since Pinel).",
            labels=("Indice", "Clause d'indexation", "Indexation"),
            required=True, enum=("ILC", "ILAT", "ICC", "autre"),
        ),
        FieldSpec(
            path="clause_indexation.trimestre_reference", type="string",
            description="Reference quarter for the index (trimestre de référence).",
            labels=("Trimestre de référence",),
        ),
        FieldSpec(
            path="clause_indexation.tunnel", type="string",
            description="Symmetric cap ('tunnel', e.g. ±3%) if agreed (possible from 28 May 2026).",
            labels=("Tunnel", "Plafonnement de l'indexation"),
        ),
        FieldSpec(
            path="clause_recette", type="string",
            description="Turnover-rent clause (clause recette), if any.",
            labels=("Clause recette", "Loyer variable"),
        ),
        FieldSpec(
            path="depot_garantie_eur", type="money",
            description="Security deposit (dépôt de garantie), EUR.",
            labels=("Dépôt de garantie",),
            required=True,
        ),
        FieldSpec(
            path="charges.inventaire_limitatif", type="string",
            description="Limitative charge inventory annexed (mandatory since Pinel, L.145-40-2).",
            labels=("Inventaire des charges", "Répartition des charges", "Charges"),
            required=True,
        ),
        FieldSpec(
            path="charges.taxe_fonciere", type="string",
            description="Who bears taxe foncière (normally bailleur unless recharged).",
            labels=("Taxe foncière",),
        ),
        FieldSpec(
            path="charges.article_606", type="string",
            description="Who bears art. 606 Code civil major works (normally bailleur).",
            labels=("Article 606", "Grosses réparations"),
        ),
        FieldSpec(
            path="clause_resolutoire", type="string",
            description="Resolution clause (clause résolutoire).",
            labels=("Clause résolutoire",),
        ),
        FieldSpec(
            path="revision_triennale", type="string",
            description="Triennial revision terms (art. L.145-38, capped at ILC/ILAT variation).",
            labels=("Révision triennale", "Révision du loyer"),
        ),
        FieldSpec(
            path="faculte_resiliation_triennale", type="string",
            description="Tenant triennial break right (faculté de résiliation 3/6/9, 6-month notice) — or waiver.",
            labels=("Résiliation triennale", "Faculté de résiliation"),
        ),
        FieldSpec(
            path="diagnostics.dpe_classe", type="string",
            description="DPE class annexed (A-G, informatif).",
            labels=("DPE", "Diagnostic de performance énergétique"),
            enum=("A", "B", "C", "D", "E", "F", "G"),
        ),
        FieldSpec(
            path="diagnostics.erp", type="string",
            description="État des risques et pollutions annexed (obligatoire).",
            labels=("ERP", "État des risques"),
        ),
        FieldSpec(
            path="diagnostics.amiante", type="string",
            description="Asbestos diagnostic (if construction permit pre-1 July 1997).",
            labels=("Amiante", "DTA"),
        ),
    ),
)
