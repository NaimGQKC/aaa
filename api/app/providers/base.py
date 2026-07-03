"""Provider interface — the model layer is abstracted so switching between
the EU API phase (Mistral La Plateforme) and the self-host phase (vLLM +
xgrammar on Scaleway) is a config change, not a rewrite.

Coordinate convention: all bounding boxes are stored in PDF point space
(72 dpi origin top-left), matching what pdf.js uses in the viewer. Providers
that return pixel coordinates at another DPI (Mistral OCR 4) must normalise
at ingestion time (spec §5.2 pitfall).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from dd_schemas import DocSchema


@dataclass
class OcrBlock:
    type: str  # text|title|list|table|image|header|footer|signature|...
    x1: float
    y1: float
    x2: float
    y2: float
    content: str

    def bbox(self) -> dict[str, float]:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}


@dataclass
class OcrPage:
    page_number: int  # 1-based
    markdown: str
    blocks: list[OcrBlock] = field(default_factory=list)
    width: int = 0
    height: int = 0
    dpi: int = 72
    avg_confidence: float = 1.0
    min_confidence: float = 1.0


@dataclass
class ClassificationResult:
    doc_type: str  # registry key or 'unknown'
    language: str  # 'es'|'fr'|'en'|'unknown'
    confidence: float


@dataclass
class ExtractedField:
    field_path: str
    value: Any
    text_span: str | None
    page_number: int | None
    bbox: dict[str, float] | None
    confidence: float
    abstained: bool = False
    method: str = "guided_json"


class Provider(Protocol):
    name: str
    model_version: str
    prompt_version: str

    def ocr(self, pdf_bytes: bytes, filename: str) -> list[OcrPage]: ...

    def classify(self, pages: list[OcrPage], schemas: list[DocSchema]) -> ClassificationResult: ...

    def extract(self, pages: list[OcrPage], schema: DocSchema) -> list[ExtractedField]: ...
