"""One-command Mistral connectivity + capability check.

Run on a machine with internet access (NOT the locked-down cloud sandbox):

    make mistral-check      # or: python scripts/mistral_check.py

It reads MISTRAL_API_KEY and the model names from your .env and runs three
tiny probes, printing OK or the exact error for each:

  1. Auth        — GET /v1/models      (is the key valid?)
  2. Extraction  — small chat completion with the extraction LLM
  3. OCR         — /v1/ocr on a 1-page generated PDF (blocks + confidence)

Total cost: a fraction of a cent. No documents leave your machine except the
tiny throwaway test page.
"""

from __future__ import annotations

import base64
import os
import sys

import httpx

API_BASE = "https://api.mistral.ai/v1"


def _load_dotenv() -> None:
    """Minimal .env loader so the script needs no extra deps."""
    from pathlib import Path

    env = Path(__file__).resolve().parents[1] / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _ok(msg: str) -> None:
    print(f"  \033[32mOK\033[0m   {msg}")


def _fail(msg: str, detail: str) -> None:
    print(f"  \033[31mFAIL\033[0m {msg}\n       {detail}")


def main() -> int:
    _load_dotenv()
    key = os.environ.get("MISTRAL_API_KEY", "").strip()
    llm = os.environ.get("MISTRAL_LLM_MODEL", "mistral-large-latest")
    ocr = os.environ.get("MISTRAL_OCR_MODEL", "mistral-ocr-latest")

    if not key:
        _fail("API key", "MISTRAL_API_KEY is empty in .env")
        return 1
    print(f"Testing Mistral — LLM={llm}  OCR={ocr}\n")

    client = httpx.Client(
        base_url=API_BASE, headers={"Authorization": f"Bearer {key}"}, timeout=120
    )
    failures = 0

    # 1) Auth ---------------------------------------------------------------
    try:
        r = client.get("/models")
        r.raise_for_status()
        names = [m.get("id", "") for m in r.json().get("data", [])]
        _ok(f"Auth — key valid, {len(names)} models available")
        for want in (llm, ocr):
            base = want.replace("-latest", "")
            if want in names or any(base in n for n in names):
                _ok(f"model reachable: {want}")
            else:
                _fail(f"model '{want}' not found",
                      f"available e.g.: {', '.join(names[:8])} …")
                failures += 1
    except Exception as e:
        _fail("Auth", _describe(e))
        return 1  # nothing else will work without auth

    # 2) Extraction LLM -----------------------------------------------------
    try:
        r = client.post("/chat/completions", json={
            "model": llm,
            "messages": [{"role": "user",
                          "content": "Reply with a JSON object: {\"ok\": true}"}],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        })
        r.raise_for_status()
        _ok(f"Extraction LLM responded ({llm})")
    except Exception as e:
        _fail("Extraction LLM", _describe(e))
        failures += 1

    # 3) OCR ----------------------------------------------------------------
    try:
        pdf = _tiny_pdf()
        b64 = base64.b64encode(pdf).decode()
        r = client.post("/ocr", json={
            "model": ocr,
            "document": {"type": "document_url",
                         "document_url": f"data:application/pdf;base64,{b64}"},
            "include_blocks": True,
        })
        r.raise_for_status()
        pages = r.json().get("pages", [])
        nblocks = sum(len(p.get("blocks") or []) for p in pages)
        _ok(f"OCR ran — {len(pages)} page(s), {nblocks} block(s) with bounding boxes")
    except Exception as e:
        _fail("OCR", _describe(e))
        failures += 1

    print()
    if failures:
        print(f"\033[31m{failures} check(s) failed.\033[0m Paste the FAIL lines to your dev.")
        return 1
    print("\033[32mAll checks passed — you're ready to upload real documents.\033[0m")
    return 0


def _describe(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        body = e.response.text[:400]
        return f"HTTP {e.response.status_code}: {body}"
    if isinstance(e, (httpx.ConnectError, httpx.ProxyError)):
        return ("Cannot reach api.mistral.ai — a network/proxy is blocking the "
                "connection (403 CONNECT). Run this on a machine with open "
                "internet, not inside a locked-down/corporate sandbox.")
    return f"{type(e).__name__}: {e}"


def _tiny_pdf() -> bytes:
    try:
        from fpdf import FPDF
    except ImportError:
        sys.exit("fpdf2 not installed — run `make setup` first.")
    from datetime import datetime, timezone

    pdf = FPDF(format="A4", unit="pt")
    pdf.set_creation_date(datetime(2026, 6, 1, tzinfo=timezone.utc))
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    # ASCII only — the built-in Helvetica font can't encode chars like em-dash.
    pdf.cell(0, 20, "Mistral OCR test page - Registro de la Propiedad")
    return bytes(pdf.output())


if __name__ == "__main__":
    raise SystemExit(main())
