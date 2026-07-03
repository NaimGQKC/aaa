"""The schema registry: doc-type key -> DocSchema."""

from dd_schemas.bail_fr import BAIL_FR
from dd_schemas.base import DocSchema
from dd_schemas.lease_es import LEASE_ES
from dd_schemas.nota_simple import NOTA_SIMPLE_ES
from dd_schemas.rent_roll import RENT_ROLL

REGISTRY: dict[str, DocSchema] = {
    s.key: s
    for s in (NOTA_SIMPLE_ES, LEASE_ES, BAIL_FR, RENT_ROLL)
}

UNKNOWN_DOC_TYPE = "unknown"


def get_schema(key: str) -> DocSchema | None:
    return REGISTRY.get(key)


def list_schemas() -> list[DocSchema]:
    return list(REGISTRY.values())
