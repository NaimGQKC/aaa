"""Nota simple registral (ES) — land-registry title extract.

Structure: Datos registrales -> Descripción de la finca -> Titularidad ->
Cargas -> Notas marginales.
"""

from dd_schemas.base import DocSchema, FieldSpec

NOTA_SIMPLE_ES = DocSchema(
    key="nota_simple_es",
    version="1.0",
    title="Nota simple registral",
    language="es",
    jurisdiction="ES",
    description=(
        "Spanish land-registry title extract issued by the Registro de la "
        "Propiedad: registry identifiers, property description, ownership, "
        "charges and marginal notes."
    ),
    classification_keywords=(
        "nota simple",
        "registro de la propiedad",
        "finca registral",
        "idufir",
        "cru",
        "cargas",
        "titularidad",
    ),
    fields=(
        FieldSpec(
            path="registro_propiedad", type="string",
            description="Issuing land registry office (Registro de la Propiedad).",
            labels=("Registro de la Propiedad", "Registro"),
            required=True,
        ),
        FieldSpec(
            path="finca_registral", type="string",
            description="Registry estate number (número de finca registral).",
            labels=("Finca registral", "Finca", "Finca de"),
            required=True,
        ),
        FieldSpec(
            path="cru_idufir", type="string",
            description="Unique registry identifier CRU / IDUFIR.",
            labels=("CRU", "IDUFIR", "C.R.U."),
            required=True,
        ),
        FieldSpec(
            path="tomo", type="string", description="Volume (tomo).",
            labels=("Tomo",),
        ),
        FieldSpec(
            path="libro", type="string", description="Book (libro).",
            labels=("Libro",),
        ),
        FieldSpec(
            path="folio", type="string", description="Folio.",
            labels=("Folio",),
        ),
        FieldSpec(
            path="fecha_emision", type="date",
            description="Issue date of the nota simple.",
            labels=("Fecha de emisión", "Fecha de expedición", "Fecha emisión"),
            required=True,
        ),
        FieldSpec(
            path="referencia_catastral", type="string",
            description="Cadastral reference (referencia catastral), 20 chars.",
            labels=("Referencia catastral", "Ref. catastral"),
            required=True,
        ),
        FieldSpec(
            path="descripcion.tipo", type="string",
            description="Property type: vivienda / local / garaje / nave / oficina / suelo.",
            labels=("Tipo de inmueble", "Naturaleza del inmueble", "Clase"),
        ),
        FieldSpec(
            path="descripcion.direccion", type="string",
            description="Property address.",
            labels=("Dirección", "Situación", "Domicilio"),
            required=True,
        ),
        FieldSpec(
            path="descripcion.superficie_construida_m2", type="number",
            description="Built surface area in square metres.",
            labels=("Superficie construida", "Superficie construída"),
            required=True,
        ),
        FieldSpec(
            path="descripcion.superficie_util_m2", type="number",
            description="Usable surface area in square metres.",
            labels=("Superficie útil", "Superficie util"),
        ),
        FieldSpec(
            path="descripcion.cuota_participacion", type="string",
            description="Participation quota in the horizontal division (%).",
            labels=("Cuota de participación", "Cuota"),
        ),
        FieldSpec(
            path="descripcion.naturaleza", type="string",
            description="Urbana or rústica.",
            labels=("Naturaleza",), enum=("urbana", "rustica"),
        ),
        FieldSpec(
            path="descripcion.regimen_especial", type="string",
            description="Special regime if any (VPO / protección oficial).",
            labels=("Régimen especial", "Régimen de protección"),
        ),
        FieldSpec(
            path="titularidad", type="array",
            description=(
                "Owners: each with nombre/razón social, NIF/CIF, porcentaje, "
                "tipo de derecho (pleno dominio/usufructo/nuda propiedad), "
                "carácter (ganancial/privativo), título adquisitivo and fecha."
            ),
            labels=("TITULARIDAD", "Titulares", "Titular"),
            required=True,
        ),
        FieldSpec(
            path="titularidad[0].nombre", type="string",
            description="First titleholder name / razón social.",
            labels=("Titular", "Nombre"),
            required=True,
        ),
        FieldSpec(
            path="titularidad[0].nif_cif", type="string",
            description="First titleholder NIF/CIF.",
            labels=("NIF", "CIF", "N.I.F.", "C.I.F."),
        ),
        FieldSpec(
            path="titularidad[0].porcentaje", type="number",
            description="Ownership percentage of the first titleholder.",
            labels=("Participación", "Porcentaje"),
        ),
        FieldSpec(
            path="titularidad[0].tipo_derecho", type="string",
            description="Right held: pleno dominio / usufructo / nuda propiedad.",
            labels=("Tipo de derecho", "Derecho"),
        ),
        FieldSpec(
            path="cargas", type="array",
            description=(
                "Charges/encumbrances: each with tipo (hipoteca/embargo/"
                "servidumbre/condición resolutoria/afección fiscal), importe, "
                "acreedor, fecha, rango. 'LIBRE DE CARGAS' means empty."
            ),
            labels=("CARGAS", "Cargas"),
            required=True,
        ),
        FieldSpec(
            path="cargas[0].tipo", type="string",
            description="Type of the first charge.",
            labels=("Hipoteca", "Embargo", "Servidumbre", "Afección fiscal", "Condición resolutoria"),
        ),
        FieldSpec(
            path="cargas[0].importe", type="money",
            description="Principal amount secured by the first charge, EUR.",
            labels=("Importe", "Principal", "Responsabilidad hipotecaria"),
        ),
        FieldSpec(
            path="cargas[0].acreedor", type="string",
            description="Creditor / beneficiary of the first charge.",
            labels=("Acreedor", "A favor de"),
        ),
        FieldSpec(
            path="notas_marginales", type="array",
            description="Marginal notes, verbatim list.",
            labels=("NOTAS MARGINALES", "Notas marginales"),
        ),
    ),
)
