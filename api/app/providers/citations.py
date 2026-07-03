"""Citation recovery: fuzzy-match an extracted text span back to the OCR block
it came from, recovering page + bbox (spec §4.5 step 3)."""

from __future__ import annotations

from rapidfuzz import fuzz

from app.providers.base import OcrBlock, OcrPage


def find_span(
    pages: list[OcrPage], text_span: str, min_score: float = 70.0
) -> tuple[int, OcrBlock] | None:
    """Return (page_number, block) best containing the span, or None."""
    if not text_span or not text_span.strip():
        return None
    needle = text_span.strip().lower()
    best: tuple[float, int, OcrBlock] | None = None
    for page in pages:
        for block in page.blocks:
            hay = block.content.strip().lower()
            if not hay:
                continue
            if needle in hay:
                return (page.page_number, block)
            score = fuzz.partial_ratio(needle, hay)
            if best is None or score > best[0]:
                best = (score, page.page_number, block)
    if best and best[0] >= min_score:
        return (best[1], best[2])
    return None
