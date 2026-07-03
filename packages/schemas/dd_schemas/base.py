"""Base types for the schema registry.

A DocSchema describes one document type: its fields (with multilingual label
variants used both as extraction anchors for the deterministic local provider
and as prompt hints for LLM extraction), plus classification keywords.

Every extracted field must carry provenance: the exact text span used, the
page number and the bounding box of the source block — this is what makes the
output "source-cited" and audit-ready.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

FieldType = Literal["string", "number", "date", "boolean", "money", "array", "object"]


@dataclass(frozen=True)
class FieldSpec:
    """One extractable field of a document type."""

    path: str  # dot/bracket path, e.g. "cargas[].tipo"
    type: FieldType
    description: str  # in English, for prompts and docs
    labels: tuple[str, ...] = ()  # label variants as they appear in source docs
    required: bool = False
    enum: tuple[str, ...] | None = None

    def json_schema(self) -> dict[str, Any]:
        base: dict[str, Any] = {"description": self.description}
        if self.type == "money" or self.type == "number":
            base["type"] = "number"
        elif self.type == "date":
            base["type"] = "string"
            base["format"] = "date"
        elif self.type == "boolean":
            base["type"] = "boolean"
        elif self.type == "array":
            base["type"] = "array"
        elif self.type == "object":
            base["type"] = "object"
        else:
            base["type"] = "string"
        if self.enum:
            base["enum"] = list(self.enum)
        return base


@dataclass(frozen=True)
class DocSchema:
    """A registered document type."""

    key: str  # registry key, e.g. "nota_simple_es"
    version: str
    title: str
    language: str  # primary language: 'es' | 'fr' | 'en'
    jurisdiction: str  # 'ES' | 'FR' | 'EU'
    description: str
    fields: tuple[FieldSpec, ...] = ()
    # Keywords used by the classifier (both providers) to recognise this type.
    classification_keywords: tuple[str, ...] = ()
    # Doc types the registry knows are "clean/registered" get higher default
    # confidence tiers; exotic docs are always routed to human review.
    confidence_tier: Literal["registered", "exotic"] = "registered"

    def field_map(self) -> dict[str, FieldSpec]:
        return {f.path: f for f in self.fields}

    def extraction_json_schema(self) -> dict[str, Any]:
        """JSON schema handed to guided decoding / Mistral structured output.

        Every field is wrapped in an envelope requiring value + provenance so
        the model cannot return an uncited value.
        """
        props: dict[str, Any] = {}
        for f in self.fields:
            props[f.path] = {
                "type": "object",
                "description": f.description,
                "properties": {
                    "value": f.json_schema(),
                    "text_span": {
                        "type": "string",
                        "description": "Exact source text the value was read from, verbatim.",
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "abstained": {
                        "type": "boolean",
                        "description": "True if the field could not be reliably extracted.",
                    },
                },
                "required": ["value", "text_span", "confidence", "abstained"],
            }
        return {
            "type": "object",
            "title": f"{self.key}@{self.version}",
            "properties": props,
        }
