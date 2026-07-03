"""dd_schemas — the schema registry: doc-type field definitions, red-flag rules
and EPC/EPBD rule tables. This package is the product's core IP surface and is
shared by the API, the workers and the eval harness."""

from dd_schemas.base import DocSchema, FieldSpec
from dd_schemas.registry import REGISTRY, get_schema, list_schemas

__all__ = ["DocSchema", "FieldSpec", "REGISTRY", "get_schema", "list_schemas"]
