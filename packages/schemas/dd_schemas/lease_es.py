"""Contrato de arrendamiento para uso distinto de vivienda (ES commercial lease, LAU)."""

from dd_schemas.base import DocSchema, FieldSpec

LEASE_ES = DocSchema(
    key="lease_es",
    version="1.0",
    title="Contrato de arrendamiento (uso distinto de vivienda)",
    language="es",
    jurisdiction="ES",
    description=(
        "Spanish commercial lease under the LAU (Ley 29/1994) for non-housing "
        "use: parties, premises, rent, indexation, duration, deposit and "
        "special clauses."
    ),
    classification_keywords=(
        "contrato de arrendamiento",
        "arrendador",
        "arrendatario",
        "renta",
        "fianza",
        "ley de arrendamientos urbanos",
        "uso distinto de vivienda",
        "lau",
    ),
    fields=(
        FieldSpec(
            path="arrendador.nombre", type="string",
            description="Landlord name / razón social.",
            labels=("Arrendador", "ARRENDADOR", "El Arrendador"),
            required=True,
        ),
        FieldSpec(
            path="arrendador.nif_cif", type="string",
            description="Landlord NIF/CIF.",
            labels=("NIF del arrendador", "CIF del arrendador"),
        ),
        FieldSpec(
            path="arrendatario.nombre", type="string",
            description="Tenant name / razón social.",
            labels=("Arrendatario", "ARRENDATARIO", "El Arrendatario"),
            required=True,
        ),
        FieldSpec(
            path="arrendatario.nif_cif", type="string",
            description="Tenant NIF/CIF.",
            labels=("NIF del arrendatario", "CIF del arrendatario"),
        ),
        FieldSpec(
            path="inmueble.direccion", type="string",
            description="Leased premises address.",
            labels=("Inmueble", "Local", "Finca objeto", "Objeto del contrato"),
            required=True,
        ),
        FieldSpec(
            path="inmueble.referencia_catastral", type="string",
            description="Cadastral reference of the premises.",
            labels=("Referencia catastral", "Ref. catastral"),
        ),
        FieldSpec(
            path="superficie_m2", type="number",
            description="Leased surface in square metres.",
            labels=("Superficie", "Superficie del local"),
            required=True,
        ),
        FieldSpec(
            path="destino_uso", type="string",
            description="Permitted use (destino/uso) of the premises.",
            labels=("Destino", "Uso", "Destino del inmueble"),
            required=True,
        ),
        FieldSpec(
            path="renta_mensual_eur", type="money",
            description="Monthly rent in EUR (excluding VAT unless stated).",
            labels=("Renta mensual", "Renta", "Renta inicial"),
            required=True,
        ),
        FieldSpec(
            path="periodicidad_pago", type="string",
            description="Payment periodicity (mensual/trimestral/anual).",
            labels=("Periodicidad", "Forma de pago"),
        ),
        FieldSpec(
            path="fecha_inicio", type="date",
            description="Lease start date.",
            labels=("Fecha de inicio", "Fecha de entrada en vigor", "Inicio del arrendamiento"),
            required=True,
        ),
        FieldSpec(
            path="duracion", type="string",
            description="Contractual duration (e.g. '10 años').",
            labels=("Duración", "Plazo", "Plazo de duración"),
            required=True,
        ),
        FieldSpec(
            path="prorrogas", type="string",
            description="Extension/renewal regime (prórrogas).",
            labels=("Prórroga", "Prórrogas"),
        ),
        FieldSpec(
            path="actualizacion_renta", type="string",
            description="Rent-review / indexation clause (IPC or other index).",
            labels=("Actualización de la renta", "Actualización de renta", "Revisión de la renta"),
            required=True,
        ),
        FieldSpec(
            path="fianza_eur", type="money",
            description="Statutory deposit (fianza) amount, EUR. LAU art. 36 minimum for non-housing use: 2 monthly rents.",
            labels=("Fianza",),
            required=True,
        ),
        FieldSpec(
            path="garantias_adicionales", type="string",
            description="Additional guarantees (aval bancario, garantía adicional).",
            labels=("Garantía adicional", "Aval", "Garantías adicionales"),
        ),
        FieldSpec(
            path="gastos.ibi", type="string",
            description="Who bears IBI property tax (arrendador/arrendatario).",
            labels=("IBI",),
        ),
        FieldSpec(
            path="gastos.comunidad", type="string",
            description="Who bears community charges (gastos de comunidad).",
            labels=("Gastos de comunidad", "Comunidad de propietarios"),
        ),
        FieldSpec(
            path="obras", type="string",
            description="Works regime (obras del arrendatario/arrendador).",
            labels=("Obras",),
        ),
        FieldSpec(
            path="clausula_resolutoria", type="string",
            description="Early-termination / resolution clause, incl. break rights.",
            labels=("Resolución anticipada", "Cláusula resolutoria", "Desistimiento"),
        ),
        FieldSpec(
            path="derecho_adquisicion_preferente", type="string",
            description="Pre-emption rights (tanteo y retracto) — waived or not.",
            labels=("Tanteo", "Retracto", "Adquisición preferente"),
        ),
        FieldSpec(
            path="subarriendo_cesion", type="string",
            description="Sublease/assignment regime (subarriendo y cesión).",
            labels=("Subarriendo", "Cesión"),
        ),
        FieldSpec(
            path="renuncia_indemnizacion", type="string",
            description="Waiver of LAU art. 34 clientele indemnity, if any.",
            labels=("Indemnización por clientela", "Renuncia a la indemnización"),
        ),
    ),
)
