"""Synthetic demo/eval documents with known ground truth (spec Phase 5:
LLM-free template-filled documents -> gold set without exposing client PII).

Each entry defines the PDF's text lines and the gold extraction values used
by the eval harness. The seeded deal intentionally contains classic DD
defects: a mortgage charge, a stale nota simple, an under-deposited Spanish
lease, an ICC-indexed French bail with DPE F and a missing charge inventory,
a rent mismatch vs the rent roll, arrears and a vacant unit.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SyntheticDoc:
    filename: str
    schema_key: str
    title_lines: tuple[str, ...]
    lines: tuple[str, ...]
    gold: dict = field(default_factory=dict)
    small_font: bool = False


NOTA_SIMPLE = SyntheticDoc(
    filename="nota_simple_serrano45.pdf",
    schema_key="nota_simple_es",
    title_lines=("NOTA SIMPLE INFORMATIVA",),
    lines=(
        "Registro de la Propiedad: Madrid n. 27",
        "Fecha de emisión: 02/01/2026",
        "Finca registral: 12345",
        "CRU: 28123000712345",
        "Tomo: 2201",
        "Libro: 145",
        "Folio: 88",
        "Referencia catastral: 9872023VH5797S0001WX",
        "DESCRIPCION DE LA FINCA",
        "Tipo de inmueble: local comercial",
        "Dirección: Calle de Serrano 45, planta baja, 28001 Madrid",
        "Superficie construida: 452,00 m2",
        "Superficie útil: 418,50 m2",
        "Cuota de participación: 12,50%",
        "Naturaleza: urbana",
        "TITULARIDAD",
        "Titular: Inversiones Iberia Delta S.L.",
        "NIF: B81234567",
        "Participación: 100% en pleno dominio",
        "Tipo de derecho: pleno dominio",
        "CARGAS",
        "Hipoteca a favor de Banco Santander S.A., principal 1.200.000,00 EUR, "
        "fecha 12/03/2019, rango 1",
        "NOTAS MARGINALES",
        "Sin notas marginales",
    ),
    gold={
        "registro_propiedad": "Madrid n. 27",
        "fecha_emision": "2026-01-02",
        "finca_registral": "12345",
        "cru_idufir": "28123000712345",
        "tomo": "2201",
        "libro": "145",
        "folio": "88",
        "referencia_catastral": "9872023VH5797S0001WX",
        "descripcion.tipo": "local comercial",
        "descripcion.direccion": "Calle de Serrano 45, planta baja, 28001 Madrid",
        "descripcion.superficie_construida_m2": 452.0,
        "descripcion.superficie_util_m2": 418.5,
        "descripcion.cuota_participacion": "12,50%",
        "descripcion.naturaleza": "urbana",
        "titularidad[0].nombre": "Inversiones Iberia Delta S.L.",
        "titularidad[0].nif_cif": "B81234567",
        "titularidad[0].porcentaje": 100.0,
        "titularidad[0].tipo_derecho": "pleno dominio",
        "cargas[0].tipo": "hipoteca",
        "cargas[0].importe": 1200000.0,
        "cargas[0].acreedor": "Banco Santander S.A.",
    },
)

LEASE_ES = SyntheticDoc(
    filename="contrato_arrendamiento_acme.pdf",
    schema_key="lease_es",
    title_lines=("CONTRATO DE ARRENDAMIENTO PARA USO DISTINTO DE VIVIENDA",),
    lines=(
        "En Madrid, a 1 de julio de 2021, conforme a la Ley de Arrendamientos "
        "Urbanos (LAU).",
        "Arrendador: Inversiones Iberia Delta S.L.",
        "NIF del arrendador: B81234567",
        "Arrendatario: Acme Retail Iberia S.L.",
        "NIF del arrendatario: B87654321",
        "Inmueble: Calle de Serrano 45, planta baja, 28001 Madrid",
        "Referencia catastral: 9872023VH5797S0001WX",
        "Superficie: 452 m2",
        "Destino: comercio minorista de moda",
        "Renta mensual: 8.000,00 EUR",
        "Periodicidad: mensual",
        "Fecha de inicio: 01/07/2021",
        "Duración: 10 años",
        "Prórroga: prorrogable por periodos anuales por acuerdo expreso",
        "Actualización de la renta: IPC anual (Índice de Precios al Consumo)",
        "Fianza: 8.000,00 EUR",
        "Garantía adicional: aval bancario de 24.000,00 EUR",
        "IBI: a cargo del arrendador",
        "Gastos de comunidad: a cargo del arrendatario",
        "Obras: el arrendatario podrá realizar obras menores con consentimiento previo",
        "Resolución anticipada: el arrendatario podrá desistir a partir del quinto "
        "año con 6 meses de preaviso",
        "Tanteo: las partes excluyen los derechos de tanteo y retracto",
        "Subarriendo: prohibido sin consentimiento escrito del arrendador",
    ),
    gold={
        "arrendador.nombre": "Inversiones Iberia Delta S.L.",
        "arrendador.nif_cif": "B81234567",
        "arrendatario.nombre": "Acme Retail Iberia S.L.",
        "arrendatario.nif_cif": "B87654321",
        "inmueble.direccion": "Calle de Serrano 45, planta baja, 28001 Madrid",
        "inmueble.referencia_catastral": "9872023VH5797S0001WX",
        "superficie_m2": 452.0,
        "destino_uso": "comercio minorista de moda",
        "renta_mensual_eur": 8000.0,
        "periodicidad_pago": "mensual",
        "fecha_inicio": "2021-07-01",
        "duracion": "10 años",
        "actualizacion_renta": "IPC anual (Índice de Precios al Consumo)",
        "fianza_eur": 8000.0,
        "gastos.ibi": "a cargo del arrendador",
        "gastos.comunidad": "a cargo del arrendatario",
    },
)

BAIL_FR = SyntheticDoc(
    filename="bail_commercial_brasserie.pdf",
    schema_key="bail_commercial_fr",
    title_lines=("BAIL COMMERCIAL",),
    lines=(
        "Bail commercial soumis aux articles L.145-1 et suivants du Code de "
        "commerce (bail 3/6/9).",
        "Bailleur: SCI Toulouse Capitole Invest",
        "SIREN du bailleur: 512345678",
        "Preneur: Brasserie du Capitole SARL",
        "SIREN: 498765432",
        "Désignation des locaux: 12 Place du Capitole, 31000 Toulouse, local "
        "commercial en rez-de-chaussée",
        "Surface: 310 m2",
        "Destination: restauration et brasserie",
        "Durée: 9 ans",
        "Date d'effet: 01/01/2023",
        "Échéance: 31/12/2031",
        "Loyer annuel: 150.000,00 EUR hors taxes",
        "Périodicité: trimestrielle d'avance",
        "Indice: ICC (indice du coût de la construction)",
        "Trimestre de référence: deuxième trimestre 2022",
        "Dépôt de garantie: 37.500,00 EUR",
        "Taxe foncière: refacturée au preneur",
        "Article 606: à la charge du bailleur",
        "Clause résolutoire: défaut de paiement d'un terme de loyer",
        "Révision triennale: selon l'article L.145-38 du Code de commerce",
        "Résiliation triennale: le preneur pourra résilier à chaque échéance "
        "triennale moyennant préavis de 6 mois",
        "DPE: F",
        "ERP: annexé au présent bail",
    ),
    gold={
        "bailleur.nom": "SCI Toulouse Capitole Invest",
        "bailleur.siren": "512345678",
        "preneur.nom": "Brasserie du Capitole SARL",
        "preneur.siren": "498765432",
        "surface_m2": 310.0,
        "destination": "restauration et brasserie",
        "duree_ans": 9.0,
        "date_effet": "2023-01-01",
        "date_echeance": "2031-12-31",
        "loyer_annuel_eur": 150000.0,
        "clause_indexation.index": "ICC",
        "depot_garantie_eur": 37500.0,
        "charges.taxe_fonciere": "refacturée au preneur",
        "charges.article_606": "à la charge du bailleur",
        "diagnostics.dpe_classe": "F",
        # gold abstentions — the extractor must NOT invent these:
        "__expect_abstained__": ["charges.inventaire_limitatif"],
    },
)

RENT_ROLL_DOC = SyntheticDoc(
    filename="rent_roll_portfolio.pdf",
    schema_key="rent_roll",
    title_lines=("RENT ROLL - TENANCY SCHEDULE",),
    small_font=True,
    lines=(
        "Portfolio: Iberia-Occitanie Portfolio",
        "Date: 01/06/2026",
        "Unit | Tenant | Use | Area m2 | Lease start | Lease end | Break date | "
        "Passing rent | Frequency | Index | Deposit | Arrears",
        "U1 | Acme Retail Iberia S.L. | retail | 452 | 01/07/2021 | 30/06/2031 | "
        " | 96.000 | monthly | IPC | 16.000 | 0",
        "U2 | Brasserie du Capitole SARL | restaurant | 310 | 01/01/2023 | "
        "31/12/2031 | 31/12/2028 | 138.000 | quarterly | ICC | 37.500 | 11.500",
        "U3 | Vacant |  | 185 |  |  |  |  |  |  |  | ",
        "Total area: 947 m2",
        "Total passing rent: 234.000 EUR",
        "WAULT: 4,9",
        "Occupancy: 80,5%",
    ),
    gold={
        "total_area_m2": 947.0,
        "total_passing_rent_eur": 234000.0,
        "wault_years": 4.9,
        "occupancy_pct": 80.5,
        "__units__": [
            {"unit_id": "U1", "tenant_name": "Acme Retail Iberia S.L.",
             "passing_rent": 96000.0, "arrears": 0.0},
            {"unit_id": "U2", "tenant_name": "Brasserie du Capitole SARL",
             "passing_rent": 138000.0, "arrears": 11500.0},
            {"unit_id": "U3", "tenant_name": "Vacant", "vacancy_flag": True},
        ],
    },
)

ALL_DOCS = [NOTA_SIMPLE, LEASE_ES, BAIL_FR, RENT_ROLL_DOC]


def build_pdf(doc: SyntheticDoc) -> bytes:
    from datetime import datetime, timezone

    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="pt")
    # Fixed creation date -> byte-identical PDFs across runs (SHA-256 dedup
    # and reproducible gold set).
    pdf.set_creation_date(datetime(2026, 6, 1, tzinfo=timezone.utc))
    pdf.set_auto_page_break(auto=True, margin=40)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    for t in doc.title_lines:
        pdf.cell(0, 22, t, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    body_size = 7 if doc.small_font else 10
    for line in doc.lines:
        if line.isupper() and len(line) < 60:
            pdf.set_font("Helvetica", "B", 11)
            pdf.ln(4)
            pdf.cell(0, 18, line, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=body_size)
        else:
            pdf.set_font("Helvetica", size=body_size)
            pdf.cell(0, 15, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
