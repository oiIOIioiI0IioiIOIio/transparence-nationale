#!/usr/bin/env python3
"""
PDF document parser for HATVP declarations.

Extracts structured financial data from HATVP PDF declarations (DSP / DI)
using text extraction with pdfplumber, falling back to OCR (pytesseract)
when the PDF contains scanned images instead of selectable text.

Sections extracted from DSP (patrimoine):
  - Biens immobiliers
  - Comptes bancaires / épargne
  - Instruments financiers
  - Participations financières
  - Véhicules
  - Biens mobiliers de valeur
  - Dettes et emprunts
  - Revenus

Sources:
  Index CSV     : https://www.hatvp.fr/livraison/opendata/liste.csv
  PDFs          : https://www.hatvp.fr/livraison/dossiers/<nom_fichier>
  Doc officielle: https://www.hatvp.fr/open-data/

Usage:
  python parse_pdf.py --help
  python parse_pdf.py --test-url "https://www.hatvp.fr/livraison/dossiers/exemple.pdf"
  python parse_pdf.py --test-elu "Yaël Braun-Pivet"
  python parse_pdf.py --batch --limit 10
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")
CACHE_DIR = os.path.join(PROJECT_ROOT, "public", "data", "hatvp_cache")
PDF_CACHE_DIR = os.path.join(CACHE_DIR, "pdfs")
PDF_DECLARATIONS_DIR = os.path.join(PROJECT_ROOT, "public", "data", "pdf_declarations")
PDF_MERGED_JSON = os.path.join(PDF_DECLARATIONS_DIR, "pdf_merged.json")
INDEX_CACHE = os.path.join(CACHE_DIR, "liste.csv")

# ── HATVP URLs ─────────────────────────────────────────────────────────────────
HATVP_INDEX_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"
HATVP_DOSSIER_BASE = "https://www.hatvp.fr/livraison/dossiers/"

HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (open source; github.com/transparence-nationale)",
    "Accept": "application/pdf, text/csv, */*",
}

# ── Declaration types ──────────────────────────────────────────────────────────
DSP_TYPES = {"DSP", "DSPM", "DSPFIN", "DSPMAJ"}
DI_TYPES = {"DI", "DIM", "DIMAJ"}
ALL_DOC_TYPES = DSP_TYPES | DI_TYPES

# Minimum chars to consider the PDF has extractable text
MIN_TEXT_LENGTH = 100


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Parse HATVP PDF declarations to extract financial data."
    )
    p.add_argument("--test-url", type=str, help="Test with a specific PDF URL")
    p.add_argument("--test-file", type=str, help="Test with a local PDF file")
    p.add_argument("--test-elu", type=str, help="Test with a specific elu name")
    p.add_argument("--batch", action="store_true",
                   help="Process all elus to extract PDF data")
    p.add_argument("--limit", type=int, default=None,
                   help="Limit number of elus to process in batch mode")
    p.add_argument("--delay", type=float, default=0.5,
                   help="Delay between HTTP requests (default 0.5s)")
    p.add_argument("--force", action="store_true",
                   help="Re-download and re-parse even if cached")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be done without modifying files")
    p.add_argument("--no-ocr", action="store_true",
                   help="Disable OCR fallback (faster but may miss scanned PDFs)")
    p.add_argument("--refresh-index", action="store_true",
                   help="Force re-download of the CSV index")
    p.add_argument("--process-local", type=str, default=None,
                   help="Process a local PDF, save result to public/data/pdf_declarations/")
    p.add_argument("--merge-to-main", action="store_true",
                   help="Merge all PDFs in pdf_declarations/ into elus.json")
    return p.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
# Network utilities
# ══════════════════════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 60, retries: int = 3) -> bytes | None:
    """Download a URL and return binary content, or None on failure.
    Retries transient errors with exponential backoff."""
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 403, 410):
                return None
            if attempt < retries:
                wait = 2 ** attempt
                print(f"  ⚠ HTTP {exc.code} → {url} (retry {attempt}/{retries} in {wait}s)")
                time.sleep(wait)
            else:
                print(f"  ⚠ HTTP {exc.code} → {url} (all {retries} attempts failed)")
        except Exception as exc:
            if attempt < retries:
                wait = 2 ** attempt
                print(f"  ⚠ Network error: {exc} (retry {attempt}/{retries} in {wait}s)")
                time.sleep(wait)
            else:
                print(f"  ⚠ Network error: {exc} (all {retries} attempts failed)")
    return None


def download_file(url: str, cache_path: str, force: bool = False,
                  max_age_h: float = 168, delay: float = 0.5) -> bytes | None:
    """Download a file with local caching."""
    if not force and os.path.exists(cache_path):
        age_h = (time.time() - os.path.getmtime(cache_path)) / 3600
        if age_h < max_age_h:
            with open(cache_path, "rb") as f:
                return f.read()

    time.sleep(delay)
    data = http_get(url)
    if data:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(data)
    return data


# ══════════════════════════════════════════════════════════════════════════════
# Name normalization (shared with generate-elus.py)
# ══════════════════════════════════════════════════════════════════════════════

def normalize_name(s: str) -> str:
    """Normalize a name: lowercase, no accents, no hyphens."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[-\s]+", " ", s).strip()
    return s


# ══════════════════════════════════════════════════════════════════════════════
# PDF text extraction
# ══════════════════════════════════════════════════════════════════════════════

def extract_text_pdfplumber(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber (best for structured PDFs)."""
    try:
        import pdfplumber
    except ImportError:
        print("  ⚠ pdfplumber not installed (pip install pdfplumber)")
        return ""

    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)

                # Also extract tables for structured data
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            cells = [str(cell).strip() if cell else "" for cell in row]
                            text_parts.append(" | ".join(cells))
    except Exception as exc:
        print(f"  ⚠ pdfplumber error: {exc}")

    return "\n".join(text_parts)


def extract_text_ocr(pdf_path: str) -> str:
    """Extract text from scanned PDF using OCR (pytesseract + pdf2image)."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        print("  ⚠ OCR dependencies not installed (pip install pytesseract pdf2image)")
        return ""

    text_parts = []
    try:
        images = convert_from_path(pdf_path, dpi=300)
        for i, img in enumerate(images):
            page_text = pytesseract.image_to_string(img, lang="fra")
            text_parts.append(page_text)
    except Exception as exc:
        print(f"  ⚠ OCR error: {exc}")

    return "\n".join(text_parts)


def extract_text_from_pdf(pdf_path: str, use_ocr: bool = True) -> str:
    """
    Extract text from a PDF file.
    Tries pdfplumber first (handles native text PDFs efficiently),
    falls back to OCR only if text is too short or lacks meaningful content.
    """
    text = extract_text_pdfplumber(pdf_path)

    # Check if pdfplumber found meaningful content
    # Some PDFs have headers/footers but the real content is in images
    text_stripped = text.strip()
    has_meaningful_content = (
        len(text_stripped) >= MIN_TEXT_LENGTH
        and (
            re.search(r"(?i)(?:patrimoin|immobilier|revenus?|emprunt|dettes?|r[ée]mun[ée]ration|employeur|activit[ée])", text_stripped)
            or re.search(r"\d[\d\s]*[.,]\d{1,2}\s*(?:€|euros?)", text_stripped)
        )
    )

    if not has_meaningful_content and use_ocr:
        print("  ℹ Text extraction yielded little content, trying OCR…")
        ocr_text = extract_text_ocr(pdf_path)
        if len(ocr_text.strip()) > len(text_stripped):
            text = ocr_text

    return text


# ══════════════════════════════════════════════════════════════════════════════
# Financial data extraction from text
# ══════════════════════════════════════════════════════════════════════════════

# Section headers as they appear in HATVP PDF declarations
SECTION_PATTERNS = {
    "biens_immobiliers": [
        r"(?i)biens?\s+immobiliers?",
        r"(?i)patrimoine\s+immobilier",
        r"(?i)immeuble[s]?\s+(bâti|non\s+bâti)",
    ],
    "comptes_bancaires": [
        r"(?i)comptes?\s+bancaires?",
        r"(?i)liquidit[ée]s?",
        r"(?i)comptes?\s+d['\u2019]épargne",
        r"(?i)placements?\s+(?:financiers?|bancaires?)",
    ],
    "instruments_financiers": [
        r"(?i)instruments?\s+financiers?",
        r"(?i)valeurs?\s+mobilières?",
        r"(?i)actions?\s+(?:et|ou)\s+obligations?",
        r"(?i)assurance[s]?[\s-]+vie",
    ],
    "participations_financieres": [
        r"(?i)participation[s]?\s+(?:financières?|dans\s+des?\s+soci[ée]t[ée]s?)",
        r"(?i)parts?\s+(?:sociales?|de\s+soci[ée]t[ée])",
    ],
    "vehicules": [
        r"(?i)v[ée]hicules?",
        r"(?i)automobiles?",
    ],
    "biens_mobiliers_valeur": [
        r"(?i)biens?\s+mobiliers?\s+(?:de\s+)?(?:grande\s+)?valeur",
        r"(?i)objets?\s+(?:de\s+)?(?:grande\s+)?valeur",
        r"(?i)œuvres?\s+d['\u2019]art",
    ],
    "dettes": [
        r"(?i)dettes?",
        r"(?i)emprunts?",
        r"(?i)passif",
        r"(?i)capital\s+restant\s+d[ûu]",
    ],
    "revenus": [
        r"(?i)revenus?",
        r"(?i)r[ée]mun[ée]ration",
        r"(?i)indemnit[ée]s?",
        r"(?i)traitements?\s+(?:et|ou)\s+salaires?",
        r"(?i)montant\s+brut\s+annuel",
        r"(?i)r[ée]tribution",
    ],
    "activites_professionnelles": [
        r"(?i)activit[ée]s?\s+professionnelles?",
        r"(?i)fonctions?\s+exerc[ée]es?",
        r"(?i)activit[ée]s?\s+professionnelles?\s+pass[ée]es?",
    ],
    "mandats_electifs": [
        r"(?i)mandats?\s+[ée]lectifs?",
        r"(?i)fonctions?\s+[ée]lectives?",
        r"(?i)mandats?\s+(?:en\s+cours|actuels?)",
    ],
    "activites_conjoint": [
        r"(?i)activit[ée]s?\s+(?:du|de\s+la)\s+conjoint",
        r"(?i)activit[ée]s?\s+professionnelles?\s+(?:du|de\s+la)\s+conjoint",
        r"(?i)conjoint\s*[:;]",
    ],
    "fonctions_benevoles": [
        r"(?i)fonctions?\s+b[ée]n[ée]voles?",
        r"(?i)activit[ée]s?\s+b[ée]n[ée]voles?",
    ],
    "participations_organes": [
        r"(?i)participation[s]?\s+(?:aux?\s+)?organes?\s+dirigeants?",
        r"(?i)organes?\s+dirigeants?",
        r"(?i)fonctions?\s+de\s+direction",
    ],
    "activites_anterieures": [
        r"(?i)activit[ée]s?\s+(?:ant[ée]rieures?|exerc[ée]es?\s+au\s+cours\s+des?\s+cinq)",
        r"(?i)cinq\s+derni[eè]res?\s+ann[ée]es?",
    ],
    "observations": [
        r"(?i)observations?\s+(?:du|de\s+la)\s+d[ée]clarant",
        r"(?i)observations?\s+compl[ée]mentaires?",
    ],
}

# Patterns for extracting monetary values
MONEY_PATTERNS = [
    # "123 456,78 €" or "123456.78€" or "123 456 €"
    r"(\d[\d\s\xa0]*(?:[.,]\d{1,2})?)\s*(?:€|euros?|EUR)",
    # "123 456,78" at end of line or before whitespace (context-dependent)
    r"(\d{1,3}(?:[\s\xa0]\d{3})+(?:[.,]\d{1,2})?)",
    # Simple amounts
    r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?)",
]


def parse_amount(s: str) -> float | None:
    """Parse a French-formatted monetary amount to float."""
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        val = float(s)
        return val if val >= 0 else None
    except ValueError:
        return None


def find_amounts_in_text(text: str) -> list[float]:
    """Extract all monetary amounts from text."""
    amounts = []
    for pattern in MONEY_PATTERNS:
        for match in re.finditer(pattern, text):
            val = parse_amount(match.group(1))
            if val is not None and val > 0:
                amounts.append(val)
    return amounts


def split_into_sections(text: str) -> dict[str, str]:
    """
    Split the full PDF text into sections based on section headers.
    Returns {section_name: section_text}.
    """
    sections = {}
    lines = text.split("\n")
    current_section = "header"
    current_lines = []

    for line in lines:
        matched = False
        for section_name, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line):
                    # Save previous section
                    if current_lines:
                        sections[current_section] = "\n".join(current_lines)
                    current_section = section_name
                    current_lines = [line]
                    matched = True
                    break
            if matched:
                break
        if not matched:
            current_lines.append(line)

    # Save last section
    if current_lines:
        sections[current_section] = "\n".join(current_lines)

    return sections


def extract_section_items(section_text: str, section_name: str) -> list[dict]:
    """Extract individual items from a section's text."""
    items = []
    amounts = find_amounts_in_text(section_text)

    # For revenue sections, try splitting by "Employeur :" blocks first
    if section_name == "revenus":
        employer_blocks = re.split(r"(?=(?:^|\n)\s*Employeur\s*:)", section_text)
        employer_blocks = [b.strip() for b in employer_blocks if b.strip() and len(b.strip()) > 10]
        if len(employer_blocks) > 1 or (employer_blocks and re.search(r"(?i)employeur\s*:", employer_blocks[0])):
            for block in employer_blocks:
                item = {"description": _clean_text(block[:500])}
                block_amounts = find_amounts_in_text(block)
                if block_amounts:
                    item["montant_euro"] = max(block_amounts)
                    if len(block_amounts) > 1:
                        item["montants_details"] = sorted(block_amounts, reverse=True)
                _extract_revenus_fields(block, item)
                if any(v for k, v in item.items() if k != "description"):
                    items.append(item)
            if items:
                return items

    # Split by common item separators
    # HATVP declarations often use numbered items or bullet points
    item_blocks = re.split(
        r"\n\s*(?:\d+[.)]\s*|[-•]\s*|_{3,}\s*\n)",
        section_text
    )

    for block in item_blocks:
        block = block.strip()
        if not block or len(block) < 10:
            continue

        item = {"description": _clean_text(block[:500])}

        # Extract amounts from this block
        block_amounts = find_amounts_in_text(block)
        if block_amounts:
            # Use the largest amount as the primary value
            item["montant_euro"] = max(block_amounts)
            if len(block_amounts) > 1:
                item["montants_details"] = sorted(block_amounts, reverse=True)

        # Try to extract specific fields based on section type
        if section_name == "biens_immobiliers":
            _extract_immobilier_fields(block, item)
        elif section_name == "revenus":
            _extract_revenus_fields(block, item)
        elif section_name == "instruments_financiers":
            _extract_instrument_fields(block, item)
        elif section_name in ("activites_professionnelles",
                              "activites_anterieures",
                              "activites_consultant"):
            _extract_activites_fields(block, item)
        elif section_name in ("participations_financieres",
                              "participations_organes"):
            _extract_company_name(block, item)
        elif section_name == "activites_conjoint":
            _extract_conjoint_fields(block, item)
        elif section_name == "fonctions_benevoles":
            _extract_activites_fields(block, item)
        elif section_name == "dettes":
            _extract_dette_fields(block, item)
        elif section_name == "comptes_bancaires":
            _extract_compte_fields(block, item)
        elif section_name == "vehicules":
            _extract_vehicule_fields(block, item)

        if any(v for k, v in item.items() if k != "description"):
            items.append(item)

    # If no structured items found but we have amounts, create a summary
    if not items and amounts:
        items.append({
            "description": f"Total section {section_name}",
            "montant_euro": sum(amounts),
            "nb_montants_detectes": len(amounts),
        })

    return items


def _clean_text(text: str) -> str:
    """Clean up extracted text."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[|\t]{2,}", " ", text)
    return text


def _extract_immobilier_fields(text: str, item: dict) -> None:
    """Extract real estate specific fields."""
    # Type of property
    for label, pattern in [
        ("Appartement", r"(?i)appartement"),
        ("Maison", r"(?i)maison"),
        ("Terrain", r"(?i)terrain"),
        ("Local commercial", r"(?i)local\s+commercial"),
        ("Immeuble", r"(?i)immeuble"),
    ]:
        if re.search(pattern, text):
            item["type_bien"] = label
            break

    # Surface
    m = re.search(r"(\d+)\s*m[²2]", text)
    if m:
        item["surface_m2"] = int(m.group(1))

    # Location
    for m in re.finditer(r"(?i)(?:situ[ée]e?\s+(?:à|au|en)\s+|commune\s+(?:de\s+)?)([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)*)", text):
        item["localisation"] = m.group(1).strip()
        break

    # Mode of acquisition
    for label, pattern in [
        ("Achat", r"(?i)(?:achat|acquisition|achet[ée])"),
        ("Héritage", r"(?i)(?:h[ée]ritage|succession|hérit)"),
        ("Donation", r"(?i)donation"),
        ("Construction", r"(?i)construction|construit"),
    ]:
        if re.search(pattern, text):
            item["mode_acquisition"] = label
            break


def _extract_revenus_fields(text: str, item: dict) -> None:
    """Extract revenue specific fields including employer and year-by-year salary."""
    for label, pattern in [
        ("Indemnités parlementaires", r"(?i)indemnit[ée]s?\s+parlementaires?"),
        ("Traitement", r"(?i)traitement"),
        ("Salaire", r"(?i)salaire"),
        ("Revenus fonciers", r"(?i)revenus?\s+fonciers?"),
        ("Revenus mobiliers", r"(?i)revenus?\s+mobiliers?"),
        ("Pensions", r"(?i)pensions?|retraite"),
        ("Honoraires", r"(?i)honoraires?"),
        ("Rémunération", r"(?i)r[ée]mun[ée]ration\s+ou\s+gratification"),
    ]:
        if re.search(pattern, text):
            item["type_revenu"] = label
            break

    # Extract employer (Employeur : ...)
    emp_match = re.search(
        r"(?i)employeur\s*[:;]\s*(.+?)(?:\n|$)",
        text,
    )
    if emp_match:
        employer = _clean_text(emp_match.group(1).strip())
        if employer:
            item["denomination"] = employer

    # Extract date range (de MM/YYYY à MM/YYYY)
    period_match = re.search(
        r"(?i)de\s+(\d{1,2}/\d{4})\s+[àa]\s+(\d{1,2}/\d{4})",
        text,
    )
    if period_match:
        item["periode"] = f"{period_match.group(1)} à {period_match.group(2)}"

    # Extract job title/function (line after employer or "Secrétaire d'Etat", "Ministre", etc.)
    for pattern in [
        r"(?i)(?:secr[ée]taire\s+d['\u2019][ée]tat[^\n]*)",
        r"(?i)(?:ministre[^\n]*)",
        r"(?i)(?:premier\s+ministre)",
        r"(?i)(?:pr[ée]sident[^\n]*)",
        r"(?i)(?:d[ée]put[ée]e?[^\n]*)",
        r"(?i)(?:s[ée]nateur|s[ée]natrice)[^\n]*",
    ]:
        m = re.search(pattern, text)
        if m and "fonction" not in item:
            item["fonction"] = _clean_text(m.group(0).strip())

    # Extract company/society names (original pattern)
    if "denomination" not in item:
        _extract_company_name(text, item)

    # Extract year-by-year salary (YYYY : XX XXX € Net or YYYY : XX XXX €)
    year_salaries = []
    for ym in re.finditer(
        r"(20\d{2})\s*:\s*(\d[\d\s\xa0]*(?:[.,]\d{1,2})?)\s*(?:€|euros?)\s*(?:Net|Brut|net|brut)?",
        text,
    ):
        year = ym.group(1)
        amount = parse_amount(ym.group(2))
        if amount is not None and amount > 0:
            year_salaries.append({"annee": year, "montant": amount})

    if year_salaries:
        item["revenus_annuels"] = year_salaries
        # Use total of year salaries as the main amount
        total = sum(ys["montant"] for ys in year_salaries)
        if total > 0 and "montant_euro" not in item:
            item["montant_euro"] = total

    # Extract salary amounts specifically (existing pattern)
    if "salaire_euro" not in item and "montant_euro" not in item:
        salary_match = re.search(
            r"(?i)(?:salaire|r[ée]mun[ée]ration|traitement)"
            r"\s*[:;]?\s*(?:de\s+)?(\d[\d\s.,]*)\s*(?:€|euros?)",
            text,
        )
        if salary_match:
            raw = salary_match.group(1).replace(" ", "").replace(",", ".")
            try:
                item["salaire_euro"] = float(raw)
            except ValueError:
                pass


def _extract_instrument_fields(text: str, item: dict) -> None:
    """Extract financial instrument specific fields."""
    for label, pattern in [
        ("Actions", r"(?i)actions?"),
        ("Obligations", r"(?i)obligations?"),
        ("Assurance-vie", r"(?i)assurance[\s-]+vie"),
        ("OPCVM", r"(?i)OPCVM|FCP|SICAV"),
        ("PEA", r"(?i)PEA"),
        ("PEL", r"(?i)PEL"),
    ]:
        if re.search(pattern, text):
            item["type_instrument"] = label
            break


def _extract_company_name(text: str, item: dict) -> None:
    """Extract company/society name from text."""
    # Match explicit legal forms followed by a name
    m = re.search(
        r"(?i)(?:soci[ée]t[ée]|entreprise|SARL|SAS|SA|SCI|EURL|SASU|SNC)"
        r"\s+([\w][\w\s&\-']{2,60}?)(?:\s*[,.(]|\s*$)",
        text,
    )
    if m:
        item["denomination"] = _clean_text(m.group(1))
        return
    # Match "dénomination :" pattern
    m = re.search(r"(?i)d[ée]nomination\s*[:;]\s*(.+?)(?:\s*[,\n]|$)", text)
    if m:
        item["denomination"] = _clean_text(m.group(1)[:120])


def _extract_activites_fields(text: str, item: dict) -> None:
    """Extract professional activity fields."""
    # Organisation/company name
    _extract_company_name(text, item)

    # Role/function description
    for pattern in [
        r"(?i)(?:fonction|qualit[ée]|poste|r[ôo]le)\s*[:;]\s*(.+?)(?:\s*[,\n]|$)",
        r"(?i)(?:en\s+qualit[ée]\s+de|en\s+tant\s+que)\s+(.+?)(?:\s*[,.\n]|$)",
    ]:
        m = re.search(pattern, text)
        if m:
            item["fonction"] = _clean_text(m.group(1)[:200])
            break

    # Remuneration amount
    m = re.search(
        r"(?i)(?:r[ée]mun[ée]ration|salaire|indemnit[ée]|r[ée]tribution)"
        r"\s*[:;]?\s*(?:de\s+)?(\d[\d\s.,]*)\s*(?:€|euros?)",
        text,
    )
    if m:
        raw = m.group(1).replace(" ", "").replace(",", ".")
        try:
            item["remuneration_euro"] = float(raw)
        except ValueError:
            pass


def _extract_conjoint_fields(text: str, item: dict) -> None:
    """Extract spouse activity fields."""
    # Profession / activité
    for pattern in [
        r"(?i)(?:profession|activit[ée]|m[ée]tier)\s*[:;]\s*(.+?)(?:\s*[,\n]|$)",
        r"(?i)(?:exerce|occupe)\s+(?:la\s+)?(?:profession|activit[ée])\s+(?:de\s+)?(.+?)(?:\s*[,.\n]|$)",
    ]:
        m = re.search(pattern, text)
        if m:
            item["profession_conjoint"] = _clean_text(m.group(1)[:200])
            break

    # Employer
    emp_match = re.search(r"(?i)employeur\s*[:;]\s*(.+?)(?:\n|$)", text)
    if emp_match:
        employer = _clean_text(emp_match.group(1).strip())
        if employer:
            item["employeur_conjoint"] = employer

    # Company name
    _extract_company_name(text, item)


def _extract_dette_fields(text: str, item: dict) -> None:
    """Extract debt/loan specific fields."""
    # Lending institution
    for pattern in [
        r"(?i)(?:organisme|[ée]tablissement|banque|pr[êe]teur)\s*[:;]\s*(.+?)(?:\s*[,\n]|$)",
        r"(?i)(?:auprès\s+(?:de|du|de\s+la)\s+)(.+?)(?:\s*[,.\n]|$)",
    ]:
        m = re.search(pattern, text)
        if m:
            item["etablissement"] = _clean_text(m.group(1)[:120])
            break

    # Date of loan
    m = re.search(r"(?i)(?:date\s+(?:de\s+l['\u2019])?emprunt|contract[ée]e?\s+(?:le|en))\s*[:;]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4})", text)
    if m:
        item["date_emprunt"] = m.group(1).strip()

    # Capital restant dû
    m = re.search(r"(?i)capital\s+restant\s+d[ûu]\s*[:;]?\s*(\d[\d\s.,]*)\s*(?:€|euros?)", text)
    if m:
        raw = m.group(1).replace(" ", "").replace(",", ".")
        try:
            item["capital_restant_du"] = float(raw)
        except ValueError:
            pass


def _extract_compte_fields(text: str, item: dict) -> None:
    """Extract bank account specific fields."""
    # Bank/institution name
    for pattern in [
        r"(?i)(?:[ée]tablissement|banque|organisme)\s*[:;]\s*(.+?)(?:\s*[,\n]|$)",
        r"(?i)(?:tenu[e]?\s+(?:chez|par|auprès\s+de)\s+)(.+?)(?:\s*[,.\n]|$)",
    ]:
        m = re.search(pattern, text)
        if m:
            item["etablissement"] = _clean_text(m.group(1)[:120])
            break

    # Account type
    for label, pattern in [
        ("Compte courant", r"(?i)compte\s+courant"),
        ("Livret A", r"(?i)livret\s+A"),
        ("LDD", r"(?i)LDD|livret\s+de\s+d[ée]veloppement"),
        ("PEL", r"(?i)PEL|plan\s+[ée]pargne\s+logement"),
        ("Compte épargne", r"(?i)compte\s+[ée]pargne|livret"),
        ("Compte titres", r"(?i)compte\s+titres?"),
        ("PEA", r"(?i)PEA|plan\s+[ée]pargne\s+actions?"),
    ]:
        if re.search(pattern, text):
            item["type_compte"] = label
            break


def _extract_vehicule_fields(text: str, item: dict) -> None:
    """Extract vehicle specific fields."""
    # Brand
    for pattern in [
        r"(?i)(?:marque|constructeur)\s*[:;]\s*(.+?)(?:\s*[,\n]|$)",
    ]:
        m = re.search(pattern, text)
        if m:
            item["marque"] = _clean_text(m.group(1)[:60])
            break

    # Common car brands detection
    for brand in ["Peugeot", "Renault", "Citroën", "Audi", "BMW", "Mercedes",
                   "Volkswagen", "Toyota", "Honda", "Ford", "Volvo", "Tesla",
                   "Porsche", "Fiat", "Opel", "Nissan", "Hyundai", "Kia"]:
        if re.search(r"(?i)\b" + re.escape(brand) + r"\b", text):
            if "marque" not in item:
                item["marque"] = brand
            break

    # Year
    m = re.search(r"(?i)(?:ann[ée]e|mis[e]?\s+en\s+circulation)\s*[:;]?\s*((?:19|20)\d{2})", text)
    if m:
        item["annee"] = m.group(1)

    # Model
    m = re.search(r"(?i)mod[èe]le\s*[:;]\s*(.+?)(?:\s*[,\n]|$)", text)
    if m:
        item["modele"] = _clean_text(m.group(1)[:60])


# ══════════════════════════════════════════════════════════════════════════════
# Main PDF parsing pipeline
# ══════════════════════════════════════════════════════════════════════════════

def parse_pdf_declaration(pdf_path: str, use_ocr: bool = True) -> dict:
    """
    Parse a single HATVP PDF declaration and extract all financial data.
    Returns a structured dict with all sections.
    """
    result = {
        "source": "pdf",
        "pdf_path": pdf_path,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": "unknown",
        "raw_text_length": 0,
        "sections_found": [],
    }

    # Extract text
    text = extract_text_from_pdf(pdf_path, use_ocr=use_ocr)
    result["raw_text_length"] = len(text)

    if len(text.strip()) < MIN_TEXT_LENGTH:
        result["extraction_method"] = "failed"
        result["error"] = "Could not extract sufficient text from PDF"
        return result

    result["extraction_method"] = "pdfplumber"  # or "ocr" if OCR was used

    # Detect if this is a DSP (patrimoine) or DI (intérêts)
    is_dsp = bool(re.search(r"(?i)d[ée]claration\s+de\s+(?:situation\s+)?patrimoin", text))
    is_di = bool(re.search(r"(?i)d[ée]claration\s+d['\u2019]int[ée]r[êe]ts?", text))
    result["type_detected"] = "DSP" if is_dsp else ("DI" if is_di else "unknown")

    # Split into sections
    sections = split_into_sections(text)
    result["sections_found"] = [k for k in sections if k != "header"]

    # Extract data from each section
    totals = {
        "immobilier": 0.0,
        "placements": 0.0,
        "instruments": 0.0,
        "participations": 0.0,
        "vehicules": 0.0,
        "biens_mobiliers": 0.0,
        "dettes": 0.0,
        "revenus": 0.0,
    }

    section_mapping = {
        "biens_immobiliers": "immobilier",
        "comptes_bancaires": "placements",
        "instruments_financiers": "instruments",
        "participations_financieres": "participations",
        "vehicules": "vehicules",
        "biens_mobiliers_valeur": "biens_mobiliers",
        "dettes": "dettes",
        "revenus": "revenus",
    }

    for section_name, section_text in sections.items():
        if section_name == "header":
            continue

        items = extract_section_items(section_text, section_name)
        if items:
            result[section_name] = items

            # Accumulate totals
            total_key = section_mapping.get(section_name)
            if total_key:
                section_total = sum(
                    item.get("montant_euro", 0)
                    for item in items
                )
                totals[total_key] += section_total

    # Compute summary
    patrimoine_brut = (
        totals["immobilier"]
        + totals["placements"]
        + totals["instruments"]
        + totals["participations"]
        + totals["vehicules"]
        + totals["biens_mobiliers"]
    )
    patrimoine_net = patrimoine_brut - totals["dettes"]

    result["summary"] = {
        "patrimoine_brut_euro": patrimoine_brut,
        "patrimoine_net_euro": patrimoine_net,
        "immobilier_euro": totals["immobilier"],
        "placements_euro": totals["placements"],
        "instruments_euro": totals["instruments"],
        "participations_euro": totals["participations"],
        "vehicules_euro": totals["vehicules"],
        "biens_mobiliers_euro": totals["biens_mobiliers"],
        "dettes_euro": totals["dettes"],
        "revenus_euro": totals["revenus"],
    }

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CSV index
# ══════════════════════════════════════════════════════════════════════════════

def load_hatvp_index(force_refresh: bool = False, delay: float = 0.5) -> list[dict]:
    """Download and parse the HATVP CSV index."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    raw = download_file(HATVP_INDEX_URL, INDEX_CACHE, force=force_refresh, delay=delay)
    if not raw:
        raise RuntimeError(f"Cannot download HATVP index: {HATVP_INDEX_URL}")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    if rows:
        print(f"  ✓ {len(rows):,} entries — columns: {list(rows[0].keys())}")
    return rows


def find_pdf_urls_for_elu(csv_index: list[dict], prenom: str, nom: str) -> list[dict]:
    """Find PDF declaration URLs for an elu from the CSV index."""
    norm_prenom = normalize_name(prenom)
    norm_nom = normalize_name(nom)
    matched = []

    for row in csv_index:
        r_nom = normalize_name(row.get("nom", ""))
        r_prenom = normalize_name(row.get("prenom", ""))
        if r_nom == norm_nom and r_prenom == norm_prenom:
            doc_type = (row.get("type_document") or "").strip().upper()
            if doc_type in ALL_DOC_TYPES:
                nom_fichier = (row.get("nom_fichier") or "").strip()
                if nom_fichier:
                    url = HATVP_DOSSIER_BASE + nom_fichier
                    matched.append({
                        "url": url,
                        "type": doc_type,
                        "date_publication": row.get("date_publication", ""),
                        "nom_fichier": nom_fichier,
                    })

    # Sort by date (most recent first)
    def sort_key(r):
        d = r.get("date_publication", "")
        try:
            return datetime.strptime(d.strip(), "%Y-%m-%d")
        except (ValueError, AttributeError):
            return datetime.min
    matched.sort(key=sort_key, reverse=True)

    return matched


# ══════════════════════════════════════════════════════════════════════════════
# Elu processing
# ══════════════════════════════════════════════════════════════════════════════

def process_elu_pdfs(
    elu: dict,
    csv_index: list[dict],
    force: bool = False,
    dry_run: bool = False,
    use_ocr: bool = True,
    delay: float = 0.5,
) -> dict | None:
    """
    Download and parse PDF declarations for a single elu.
    Returns aggregated financial data or None if nothing found.
    """
    prenom = elu.get("prenom", "").strip()
    nom = elu.get("nom", "").strip()
    if not prenom or not nom:
        return None

    pdf_entries = find_pdf_urls_for_elu(csv_index, prenom, nom)
    if not pdf_entries:
        return None

    print(f"    📄 {len(pdf_entries)} PDF(s) found")

    # Take the most recent DSP + most recent DI
    selected = []
    seen_categories = set()
    for entry in pdf_entries:
        category = "DSP" if entry["type"] in DSP_TYPES else "DI"
        if category not in seen_categories:
            selected.append(entry)
            seen_categories.add(category)

    aggregated = {
        "source": "pdf",
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "declarations_parsed": 0,
        "summary": {
            "patrimoine_brut_euro": 0,
            "patrimoine_net_euro": 0,
            "immobilier_euro": 0,
            "placements_euro": 0,
            "instruments_euro": 0,
            "participations_euro": 0,
            "dettes_euro": 0,
            "revenus_euro": 0,
        },
    }

    for entry in selected:
        url = entry["url"]
        nom_fichier = entry["nom_fichier"]
        cache_path = os.path.join(PDF_CACHE_DIR, nom_fichier)

        print(f"    🔄 {entry['type']} : {url}")

        if dry_run:
            aggregated["declarations_parsed"] += 1
            continue

        pdf_bytes = download_file(url, cache_path, force=force,
                                  max_age_h=168, delay=delay)
        if not pdf_bytes:
            print(f"    ✗ Failed to download {url}")
            continue

        # Verify it's actually a PDF
        if not pdf_bytes[:5] == b"%PDF-":
            print(f"    ✗ Not a valid PDF: {nom_fichier}")
            continue

        parsed = parse_pdf_declaration(cache_path, use_ocr=use_ocr)
        aggregated["declarations_parsed"] += 1

        # Merge summaries (take maximums to avoid double-counting)
        if parsed.get("summary"):
            for key in aggregated["summary"]:
                existing = aggregated["summary"][key]
                new_val = parsed["summary"].get(key, 0)
                # For patrimoine net, take the most meaningful value
                if key in ("patrimoine_brut_euro", "patrimoine_net_euro"):
                    aggregated["summary"][key] = max(existing, new_val)
                else:
                    aggregated["summary"][key] = max(existing, new_val)

        # Copy section details
        for section in SECTION_PATTERNS:
            if section in parsed:
                if section not in aggregated:
                    aggregated[section] = []
                aggregated[section].extend(parsed[section])

    if aggregated["declarations_parsed"] == 0:
        return None

    return aggregated


def update_elu_with_pdf_data(elu: dict, pdf_data: dict) -> bool:
    """
    Update an elu dict with data extracted from PDF.
    Stores ALL extracted data (patrimoine, revenus, activités, mandats, etc.).
    Returns True if any data was updated.
    """
    summary = pdf_data.get("summary", {})
    updated = False

    # Update patrimoine if PDF data is better
    pdf_patrimoine = summary.get("patrimoine_brut_euro", 0)
    if pdf_patrimoine > 0 and pdf_patrimoine > elu.get("patrimoine", 0):
        elu["patrimoine"] = pdf_patrimoine
        elu["patrimoine_source"] = "pdf_hatvp"
        updated = True

    # Update immobilier
    pdf_immobilier = summary.get("immobilier_euro", 0)
    if pdf_immobilier > 0 and pdf_immobilier > elu.get("immobilier", 0):
        elu["immobilier"] = pdf_immobilier
        updated = True

    # Update placements
    pdf_placements = summary.get("placements_euro", 0) + summary.get("instruments_euro", 0)
    current_placements = elu.get("placements_montant", 0)
    if pdf_placements > 0 and pdf_placements > current_placements:
        elu["placements_montant"] = pdf_placements
        updated = True

    # Update revenus
    pdf_revenus = summary.get("revenus_euro", 0)
    if pdf_revenus > 0 and pdf_revenus > elu.get("revenus", 0):
        elu["revenus"] = pdf_revenus
        elu["revenus_source"] = "pdf_hatvp"
        updated = True

    # Store all section details extracted from PDFs
    section_to_detail_key = {
        "biens_immobiliers": "details_biens_immobiliers",
        "comptes_bancaires": "details_comptes_bancaires",
        "instruments_financiers": "details_instruments_financiers",
        "participations_financieres": "details_participations_financieres",
        "vehicules": "details_vehicules",
        "biens_mobiliers_valeur": "details_biens_mobiliers",
        "dettes": "details_dettes",
        "revenus": "details_revenus",
        "activites_professionnelles": "details_activites_professionnelles",
        "mandats_electifs": "details_mandats_electifs",
    }
    for section_name, detail_key in section_to_detail_key.items():
        items = pdf_data.get(section_name, [])
        if items:
            if detail_key not in elu:
                elu[detail_key] = items
                updated = True
            else:
                existing = {json.dumps(it, sort_keys=True) for it in elu[detail_key]}
                for it in items:
                    if json.dumps(it, sort_keys=True) not in existing:
                        elu[detail_key].append(it)
                        updated = True

    # Add PDF metadata
    if not elu.get("hatvp_pdf"):
        elu["hatvp_pdf"] = {}
    elu["hatvp_pdf"] = {
        "parsed_at": pdf_data.get("parsed_at", ""),
        "declarations_parsed": pdf_data.get("declarations_parsed", 0),
        "patrimoine_brut_euro": summary.get("patrimoine_brut_euro", 0),
        "patrimoine_net_euro": summary.get("patrimoine_net_euro", 0),
        "immobilier_euro": summary.get("immobilier_euro", 0),
        "placements_euro": summary.get("placements_euro", 0),
        "instruments_euro": summary.get("instruments_euro", 0),
        "dettes_euro": summary.get("dettes_euro", 0),
        "revenus_euro": summary.get("revenus_euro", 0),
    }

    return updated


# ══════════════════════════════════════════════════════════════════════════════
# PDF declarations directory management
# ══════════════════════════════════════════════════════════════════════════════

def process_local_pdf(pdf_path: str, use_ocr: bool = True) -> dict | None:
    """
    Parse a local PDF file, save the result to pdf_declarations/ as a per-PDF JSON,
    and return the parsed data.
    """
    if not os.path.exists(pdf_path):
        print(f"  ✗ File not found: {pdf_path}")
        return None

    os.makedirs(PDF_DECLARATIONS_DIR, exist_ok=True)

    print(f"\n📄 Processing: {pdf_path}")
    result = parse_pdf_declaration(pdf_path, use_ocr=use_ocr)

    # Derive a meaningful filename from the PDF
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    out_path = os.path.join(PDF_DECLARATIONS_DIR, f"{base}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  ✓ Saved to {out_path}")

    return result


def merge_pdf_declarations_to_main() -> int:
    """
    Merge all per-PDF JSONs in pdf_declarations/ into a combined pdf_merged.json
    then merge that data into elus.json.
    Returns the number of elus updated.
    """
    if not os.path.isdir(PDF_DECLARATIONS_DIR):
        print(f"  ✗ No pdf_declarations directory: {PDF_DECLARATIONS_DIR}")
        return 0

    # Collect all per-PDF JSONs
    all_pdf_data: list[dict] = []
    for fname in sorted(os.listdir(PDF_DECLARATIONS_DIR)):
        if not fname.endswith(".json") or fname == "pdf_merged.json":
            continue
        fpath = os.path.join(PDF_DECLARATIONS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["_source_file"] = fname
                all_pdf_data.append(data)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  ⚠ Skipping {fname}: {exc}")

    if not all_pdf_data:
        print("  ℹ No PDF declarations to merge")
        return 0

    # Write merged JSON
    merged = {
        "merged_at": datetime.now(timezone.utc).isoformat(),
        "total_pdfs": len(all_pdf_data),
        "declarations": all_pdf_data,
    }
    with open(PDF_MERGED_JSON, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"  ✓ Merged {len(all_pdf_data)} PDFs → {PDF_MERGED_JSON}")

    # Now merge into elus.json by matching names from PDF filenames
    elus = load_elus()
    if not elus:
        print("  ⚠ elus.json empty or not found — skipping merge to main")
        return 0

    updated_count = 0
    for pdf_data in all_pdf_data:
        # Try to match elu by filename pattern: prenom-nom-*.json
        source_file = pdf_data.get("_source_file", "")
        base = source_file.replace(".json", "")
        # HATVP filename pattern: nom-prenom-diaXXXXX-mandat.pdf → nom-prenom-diaXXXXX-mandat
        parts = base.split("-")
        if len(parts) >= 2:
            # Try matching: parts[0]=nom, parts[1]=prenom
            file_nom = parts[0]
            file_prenom = parts[1]
            file_key = normalize_name(f"{file_prenom} {file_nom}")

            for elu in elus:
                elu_key = normalize_name(f"{elu.get('prenom', '')} {elu.get('nom', '')}")
                if elu_key == file_key:
                    # Merge PDF financial data into elu (if any)
                    update_elu_with_pdf_data(elu, pdf_data)
                    # Always store a reference to the PDF data in hatvp
                    if not elu.get("hatvp"):
                        elu["hatvp"] = {}
                    if "pdf_declarations" not in elu["hatvp"]:
                        elu["hatvp"]["pdf_declarations"] = []
                    elu["hatvp"]["pdf_declarations"].append({
                        "source_pdf": source_file.replace(".json", ".pdf"),
                        "parsed_at": pdf_data.get("parsed_at", ""),
                        "extraction_method": pdf_data.get("extraction_method", ""),
                        "sections_found": pdf_data.get("sections_found", []),
                        "summary": pdf_data.get("summary", {}),
                    })
                    updated_count += 1
                    break

    if updated_count:
        save_elus(elus)
        print(f"  ✓ {updated_count} élu(s) mis à jour depuis les PDFs")

    return updated_count


# ══════════════════════════════════════════════════════════════════════════════
# I/O
# ══════════════════════════════════════════════════════════════════════════════

def load_elus() -> list[dict]:
    if not os.path.exists(OUTPUT_JSON):
        return []
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def save_elus(elus: list[dict]) -> None:
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(elus, f, ensure_ascii=False, indent=2)
    print(f"✓ {OUTPUT_JSON} updated ({len(elus)} elus)")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    print("=" * 65)
    print("📄 HATVP PDF DECLARATION PARSER")
    print("   Extracts financial data from PDF declarations")
    print("   Uses pdfplumber + OCR fallback (pytesseract)")
    if args.dry_run:
        print("   ⚠ DRY-RUN MODE — no files will be modified")
    if args.no_ocr:
        print("   ⚠ OCR DISABLED")
    print("=" * 65)

    os.makedirs(PDF_CACHE_DIR, exist_ok=True)
    use_ocr = not args.no_ocr

    # ── Process a local PDF → save to pdf_declarations/ ──────────────────────
    if args.process_local:
        result = process_local_pdf(args.process_local, use_ocr=use_ocr)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # ── Merge all pdf_declarations/*.json → elus.json ────────────────────────
    if args.merge_to_main:
        print("\n🔗 Merging PDF declarations into elus.json…")
        count = merge_pdf_declarations_to_main()
        print(f"\n✅ Merge complete — {count} élu(s) updated")
        return

    # ── Test with specific file ──────────────────────────────────────────────
    if args.test_file:
        print(f"\n🧪 Testing with local file: {args.test_file}")
        if not os.path.exists(args.test_file):
            print(f"  ✗ File not found: {args.test_file}")
            sys.exit(1)
        result = parse_pdf_declaration(args.test_file, use_ocr=use_ocr)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # ── Test with specific URL ───────────────────────────────────────────────
    if args.test_url:
        print(f"\n🧪 Testing with URL: {args.test_url}")
        filename = args.test_url.split("/")[-1]
        cache_path = os.path.join(PDF_CACHE_DIR, filename)
        pdf_bytes = download_file(args.test_url, cache_path, force=args.force,
                                  delay=args.delay)
        if not pdf_bytes:
            print("  ✗ Failed to download PDF")
            sys.exit(1)
        result = parse_pdf_declaration(cache_path, use_ocr=use_ocr)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # ── Load CSV index ───────────────────────────────────────────────────────
    print("\n📥 Loading HATVP CSV index…")
    csv_index = load_hatvp_index(force_refresh=args.refresh_index, delay=args.delay)

    # ── Test with specific elu ───────────────────────────────────────────────
    if args.test_elu:
        print(f"\n🧪 Testing with elu: {args.test_elu}")
        elus = load_elus()
        q = normalize_name(args.test_elu)
        elu = None
        for e in elus:
            full = normalize_name(f"{e.get('prenom', '')} {e.get('nom', '')}")
            if q in full or full in q:
                elu = e
                break
        if not elu:
            parts = args.test_elu.strip().split()
            elu = {"id": "test", "prenom": parts[0], "nom": " ".join(parts[1:])}

        print(f"  Profile: {elu.get('prenom')} {elu.get('nom')}")
        result = process_elu_pdfs(
            elu, csv_index,
            force=args.force,
            dry_run=args.dry_run,
            use_ocr=use_ocr,
            delay=args.delay,
        )
        if result:
            print(f"\n{'=' * 65}")
            print("✅ PDF PARSING RESULT")
            print(f"{'=' * 65}")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("  ✗ No PDF data found")
        return

    # ── Batch mode ───────────────────────────────────────────────────────────
    if not args.batch:
        print("\n⚠ No action specified. Use --test-url, --test-elu, or --batch")
        print("   Run with --help for full usage information.")
        return

    elus = load_elus()
    if not elus:
        print("⚠ elus.json is empty or not found")
        return

    # Process all elus (not just patrimoine=0) to extract all available data
    candidates = list(elus)
    print(f"\n📊 {len(candidates)} elus to process")

    if args.limit:
        candidates = candidates[:args.limit]

    total = len(candidates)
    processed = 0
    updated_count = 0
    failed = 0
    updated_ids: dict[str, dict] = {}

    for i, elu in enumerate(candidates, 1):
        prenom = elu.get("prenom", "")
        nom = elu.get("nom", "")
        elu_id = elu.get("id", f"elu-{i}")
        print(f"\n[{i}/{total}] {prenom} {nom}")

        result = process_elu_pdfs(
            elu, csv_index,
            force=args.force,
            dry_run=args.dry_run,
            use_ocr=use_ocr,
            delay=args.delay,
        )

        if result is None:
            failed += 1
            print(f"  ✗ No PDF declarations found")
            continue

        processed += 1
        summary = result.get("summary", {})
        patrimoine = summary.get("patrimoine_brut_euro", 0)
        revenus = summary.get("revenus_euro", 0)
        sections = result.get("sections_found", []) if isinstance(result.get("sections_found"), list) else []
        has_section_data = any(
            result.get(sec) for sec in SECTION_PATTERNS
        )

        # Save results when ANY useful data is extracted (not just patrimoine)
        if patrimoine > 0 or revenus > 0 or has_section_data:
            updated_count += 1
            updated_ids[elu_id] = result
            parts = []
            if patrimoine > 0:
                parts.append(f"Patrimoine: {patrimoine:,.0f} €")
            if revenus > 0:
                parts.append(f"Revenus: {revenus:,.0f} €")
            if has_section_data:
                section_names = [sec for sec in SECTION_PATTERNS if result.get(sec)]
                parts.append(f"Sections: {', '.join(section_names)}")
            print(f"  ✓ {' | '.join(parts)}")
        else:
            print(f"  ○ PDF parsed but no data extracted")

        # Save detailed result
        if not args.dry_run:
            detail_path = os.path.join(CACHE_DIR, f"{elu_id}_pdf.json")
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

    # ── Update elus.json ─────────────────────────────────────────────────────
    if not args.dry_run and updated_ids:
        all_elus = load_elus()
        for e in all_elus:
            if e.get("id") in updated_ids:
                update_elu_with_pdf_data(e, updated_ids[e["id"]])
        save_elus(all_elus)

    print(f"\n{'=' * 65}")
    print("📊 FINAL REPORT")
    print("=" * 65)
    print(f"  Total candidates     : {total}")
    print(f"  ✓ PDFs processed     : {processed}")
    print(f"  ✓ Elus updated       : {updated_count}")
    print(f"  ✗ No PDFs found      : {failed}")
    print("=" * 65)


if __name__ == "__main__":
    main()
