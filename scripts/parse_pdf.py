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
from progress import BatchProgress

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")
ELUS_DETAIL_DIR = os.path.join(PROJECT_ROOT, "public", "data", "elus")
CACHE_DIR = os.path.join(PROJECT_ROOT, "public", "data", "hatvp_cache")
PDF_CACHE_DIR = os.path.join(CACHE_DIR, "pdfs")
PDF_DECLARATIONS_DIR = os.path.join(PROJECT_ROOT, "public", "data", "pdf_declarations")
PROGRESS_JSON = os.path.join(PROJECT_ROOT, "public", "data", "progress.json")
PDF_MERGED_JSON = os.path.join(PDF_DECLARATIONS_DIR, "pdf_merged.json")
INDEX_CACHE = os.path.join(CACHE_DIR, "liste.csv")

# ── HATVP URLs ─────────────────────────────────────────────────────────────────
HATVP_INDEX_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"
HATVP_DOSSIER_BASE = "https://www.hatvp.fr/livraison/dossiers/"

HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (open source; github.com/transparence-nationale)",
    "Accept": "application/pdf, text/csv, */*",
}

# Known car brands for vehicle section detection
KNOWN_CAR_BRANDS = [
    "Peugeot", "Renault", "Citroën", "Audi", "BMW", "Mercedes",
    "Volkswagen", "Toyota", "Honda", "Ford", "Volvo", "Tesla",
    "Porsche", "Fiat", "Opel", "Nissan", "Hyundai", "Kia",
]

# ── Declaration types ──────────────────────────────────────────────────────────
DSP_TYPES = {"DSP", "DSPM", "DSPFIN", "DSPMAJ", "DSPFM"}
DI_TYPES = {"DI", "DIM", "DIMAJ", "DIA", "DIAM"}
ALL_DOC_TYPES = DSP_TYPES | DI_TYPES

# Minimum chars to consider the PDF has extractable text
MIN_TEXT_LENGTH = 100

# ── DIA numbered section mapping (1° through 8°) ──────────────────────────────
DIA_SECTION_MAP = {
    1: "activites_professionnelles",
    2: "activites_consultant",
    3: "participations_organes",
    4: "participations_financieres",
    5: "activites_conjoint",
    6: "fonctions_benevoles",
    7: "mandats_electifs",
    8: "collaborateurs",
}

# Lines that are table headers — should NOT trigger a new section
TABLE_HEADER_PATTERNS = [
    r"^(?:Rémunération|Description|ou gratification|gratification|Néant)$",
    r"^(?:Rémunération ou|gratification perçue au|cours de l'année précédente)$",
    r"^(?:Conjoint|Nom et objet|ou de la personne|et responsabilités)$",
    r"^(?:Description des activités|Description des autres|professionnelles exercées)$",
    r"^(?:Activité professionnelle)$",
    r"^(?:Rémunération,?\s*indemnité)$",
    r"^(?:Rémunération,?\s*indemnité\s*Description\s*ou\s*gratification)$",
    r"^(?:Conjoint,?\s*partenaire\s+lié\s+par\s+PACS\s+ou\s+concubin)$",
    r"^(?:Commentaire\s*:\s*Page\s+\d+/\d+\s+D[IA]+/.*)$",
]

# Lines to strip from section text during cleaning (DIA table header fragments, page footers, doc IDs)
DIA_NOISE_PATTERNS = [
    r"^\d+°\s+.*(?:exerc[ée]es?|d[ée]clar[ée]es?|d[ée]tenues?).*$",  # numbered section title lines
    r"^Rémunération,?\s*indemnité.*$",
    r"^Description\s*$",
    r"^ou\s+gratification\s*$",
    r"^Rémunération\s*$",
    r"^Rémunération\s+ou\s*$",
    r"^gratification\s+perçue\s+au\s*$",
    r"^cours\s+de\s+l'année\s+précédente\s*$",
    r"^Conjoint,?\s*partenaire\s+lié\s+par\s+PACS\s+ou\s+concubin\s*$",
    r"^Activité\s+professionnelle\s*$",
    r"^Nom\s+et\s+objet\s+social\s+de\s+la\s+structure\s*$",
    r"^ou\s+de\s+la\s+personne\s+morale\s*$",
    r"^Description\s+des\s+activités\s*$",
    r"^Description\s+des\s+autres\s+activités\s*$",
    r"^et\s+responsabilités\s+exercées\s*$",
    r"^professionnelles\s+exercées\s*$",
    r"^Nom\s*$",
    r"^Page\s+\d+/\d+\s*$",
    r"^Page\s+\d+/\d+\s+D[IA]+/.*$",
    r"^D[IA]+/[A-Z].*$",                   # document IDs like "DI/ABADIE-Muriel"
    r"^Commentaire\s*:\s*Page\s+\d+/\d+\s+D[IA]+/.*$",
    r"^Commentaire\s*:\s*$",
]


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
    p.add_argument("--save-every", type=int, default=100,
                   help="Save individual JSONs + elus.json every N elus (default 100)")
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
    """Extract text from PDF using pdfplumber (best for structured PDFs).
    Uses only page.extract_text() to avoid duplicating table content."""
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
    "activites_consultant": [
        r"(?i)activit[ée]s?\s+de\s+consultant",
        r"(?i)activit[ée]s?\s+de\s+conseil",
    ],
    "collaborateurs": [
        r"(?i)collaborateurs?\s+parlementaires?",
    ],
    "observations": [
        r"(?i)observations?\s+(?:du|de\s+la)\s+d[ée]clarant",
        r"(?i)observations?\s+compl[ée]mentaires?",
        r"(?i)^Observations\s*$",
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


def _is_table_header(line: str) -> bool:
    """Check if a line is a table header that should not trigger a new section."""
    stripped = line.strip()
    for pat in TABLE_HEADER_PATTERNS:
        if re.match(pat, stripped, re.IGNORECASE):
            return True
    return False


def _clean_section_text(text: str) -> str:
    """Remove DIA table headers, page footers, and document IDs from section text.
    This prevents noise like 'Rémunération, indemnité Description ou gratification'
    or 'Commentaire : Page 2/3 DI/ABADIE-Muriel' from polluting extracted data."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue
        is_noise = False
        for pat in DIA_NOISE_PATTERNS:
            if re.match(pat, stripped, re.IGNORECASE):
                is_noise = True
                break
        if not is_noise:
            cleaned.append(line)
    result = "\n".join(cleaned)
    # Also remove inline page footers and document references
    result = re.sub(r"Page\s+\d+/\d+\s+D[IA]+/[A-Z][^\n]*", "", result)
    result = re.sub(r"Page\s+\d+/\d+\s*$", "", result, flags=re.MULTILINE)
    # Remove trailing whitespace lines
    result = re.sub(r"\n\s*\n\s*\n", "\n\n", result)
    return result.strip()


def _split_dia_numbered(text: str) -> dict[str, str] | None:
    """Split DIA format text by numbered sections (1°, 2°, etc.).
    Returns {section_name: section_text} or None if not DIA format."""
    # Check if this looks like a DIA (has numbered sections like "1°")
    if not re.search(r'(?m)^\s*1°\s', text):
        return None

    sections = {}

    # Find all numbered section markers
    markers = list(re.finditer(r'(?m)^\s*(\d+)°\s', text))
    if not markers:
        return None

    # Add header (text before first section)
    if markers[0].start() > 0:
        sections["header"] = text[:markers[0].start()].strip()

    # Also find "Observations" section
    obs_match = re.search(r'(?mi)^Observations\s*$', text)

    for i, marker in enumerate(markers):
        num = int(marker.group(1))
        section_name = DIA_SECTION_MAP.get(num, f"section_{num}")

        # Section text goes until next section, observations, or end
        start = marker.start()
        if i + 1 < len(markers):
            end = markers[i + 1].start()
        elif obs_match and obs_match.start() > start:
            end = obs_match.start()
        else:
            end = len(text)

        section_text = text[start:end].strip()
        # Remove page footers like "Page 2/3"
        section_text = re.sub(r'\nPage\s+\d+/\d+\s*$', '', section_text)
        # Clean DIA table headers and noise from section text
        section_text = _clean_section_text(section_text)
        sections[section_name] = section_text

    # Add observations
    if obs_match:
        obs_text = text[obs_match.start():].strip()
        obs_text = re.sub(r'\nPage\s+\d+/\d+\s*$', '', obs_text)
        sections["observations"] = obs_text

    return sections


def split_into_sections(text: str) -> dict[str, str]:
    """
    Split the full PDF text into sections based on section headers.
    Handles both DIA numbered format (1°, 2°, ...) and keyword-based DSP format.
    Returns {section_name: section_text}.
    """
    # First, try DIA numbered format
    dia_sections = _split_dia_numbered(text)
    if dia_sections:
        return dia_sections

    # Fall back to keyword-based splitting for DSP and other formats
    sections = {}
    lines = text.split("\n")
    current_section = "header"
    current_lines = []

    for line in lines:
        # Skip table headers that could be mistaken for section markers
        if _is_table_header(line):
            current_lines.append(line)
            continue

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


def _section_is_neant(text: str) -> bool:
    """Check if a section's content is essentially 'Néant' (nothing to declare)."""
    # Remove the section header/title lines and table headers
    lines = text.split("\n")
    content_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip numbered section title, table headers, page footers
        if re.match(r'^\d+°\s', stripped):
            continue
        if _is_table_header(stripped):
            continue
        if re.match(r'^Page\s+\d+/\d+', stripped):
            continue
        if re.match(r'^DIA/', stripped) or re.match(r'^DSP/', stripped):
            continue
        # Skip column header lines
        if stripped in ("Description", "ou gratification", "Rémunération",
                        "Rémunération ou", "gratification perçue au",
                        "cours de l'année précédente", "Activité professionnelle",
                        "Conjoint, partenaire lié par PACS ou concubin",
                        "Nom et objet social de la structure",
                        "ou de la personne morale",
                        "Description des activités", "et responsabilités exercées",
                        "Rémunération, indemnité", "Nom",
                        "Description des autres activités", "professionnelles exercées"):
            continue
        # Skip very short lines that are just prepositions/articles
        if len(stripped) < 3:
            continue
        content_lines.append(stripped)

    # Check if the remaining content is just "Néant"
    remaining = " ".join(content_lines).strip()
    if not remaining:
        return True
    if re.match(r'^(?:Néant|NEANT|neant|N[ée]ant)\s*$', remaining, re.IGNORECASE):
        return True
    # Also handle "Néant" being the only meaningful word
    cleaned = re.sub(r'(?i)\b(?:les|la|le|de|du|des|à|au|aux|en|et|ou|par|pour|dans|sur|un|une)\b', '', remaining)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if re.match(r'^(?:Néant|NEANT|neant|N[ée]ant)\s*$', cleaned, re.IGNORECASE):
        return True
    return False


def _extract_dia_employer_blocks(text: str) -> list[dict]:
    """Extract employer blocks from DIA section 1° (activités professionnelles).
    Each block starts with 'Employeur :' and contains function, period, and year-by-year salary."""
    items = []

    # Split by "Employeur :" markers
    employer_blocks = re.split(r'(?=Employeur\s*:)', text)

    for block in employer_blocks:
        block = block.strip()
        if not block or not re.search(r'Employeur\s*:', block):
            continue

        item = {}

        # Extract employer name
        emp_match = re.search(r'Employeur\s*:\s*(.+?)(?:\s+\d{4}\s*:|$)', block)
        if emp_match:
            employer = _clean_text(emp_match.group(1).strip())
            # Clean trailing date patterns
            employer = re.sub(r'\s+\d{4}\s*$', '', employer).strip()
            if employer:
                item['denomination'] = employer

        # Extract period
        period_match = re.search(r'de\s+(\d{1,2}/\d{4})\s+à\s+(\d{1,2}/\d{4})', block)
        if period_match:
            item['periode'] = f"{period_match.group(1)} à {period_match.group(2)}"

        # Extract function/role - look for known government titles or multi-line function
        for pattern in [
            r"(?m)^((?:Secr[ée]taire\s+d[''\u2019]Etat|Ministre|Premier\s+ministre|Pr[ée]sident)[^\n]*)",
            r"(?m)^((?:D[ée]put[ée]e?|S[ée]nateur|S[ée]natrice|Conseiller)[^\n]*)",
        ]:
            fm = re.search(pattern, block)
            if fm and 'fonction' not in item:
                fn = _clean_text(fm.group(1))
                # Don't use the employer line as function
                if not fn.startswith('Employeur'):
                    # Remove trailing year:amount patterns
                    fn = re.sub(r'\s+\d{4}\s*:\s*\d[\d\s]*€.*$', '', fn).strip()
                    if fn:
                        item['fonction'] = fn

        # Extract year-by-year revenues
        year_salaries = []
        for ym in re.finditer(
            r'(20\d{2})\s*:\s*(\d[\d\s\xa0]*(?:[.,]\d{1,2})?)\s*(?:€|euros?)\s*(?:Net|Brut|net|brut)?',
            block,
        ):
            year = ym.group(1)
            amount = parse_amount(ym.group(2))
            if amount is not None and amount > 0:
                year_salaries.append({"annee": year, "montant": amount})

        if year_salaries:
            item['revenus_annuels'] = year_salaries
            item['montant_euro'] = sum(ys['montant'] for ys in year_salaries)

        # Extract comment
        comment_match = re.search(r'Commentaire\s*:\s*(.+?)(?:\n|$)', block)
        if comment_match:
            comment = _clean_text(comment_match.group(1))
            if comment:
                item['commentaire'] = comment

        if item:
            item['description'] = _clean_text(block[:500])
            items.append(item)

    return items


def _extract_participation_financiere_items(text: str) -> list[dict]:
    """Extract financial participation data (e.g., SCI shares) from DIA section 4°."""
    items = []

    # Look for "Société :" blocks
    societe_blocks = re.split(r'(?=Soci[ée]t[ée]\s*:)', text)

    for block in societe_blocks:
        block = block.strip()
        if not block or not re.search(r'Soci[ée]t[ée]\s*:', block):
            continue

        item = {}

        # Extract society name
        soc_match = re.search(r'Soci[ée]t[ée]\s*:\s*(.+?)(?:\s+\d|$|\n)', block)
        if soc_match:
            name = _clean_text(soc_match.group(1))
            if name:
                item['denomination'] = name

        # Extract number of shares
        parts_match = re.search(r'Nombre de parts d[ée]tenues\s*:\s*(\d[\d\s]*)', block)
        if parts_match:
            item['nombre_parts'] = parts_match.group(1).replace(' ', '').strip()

        # Extract percentage
        pct_match = re.search(r'Pourcentage du capital d[ée]tenu\s*:\s*(\d+(?:[.,]\d+)?)\s*%', block)
        if pct_match:
            item['pourcentage_capital'] = pct_match.group(1) + ' %'

        # Extract conseil control
        conseil_match = re.search(r"Contr[ôo]le d'une activit[ée] de conseil\s*:\s*(Oui|Non)", block, re.IGNORECASE)
        if conseil_match:
            item['controle_conseil'] = conseil_match.group(1)

        # --- Amount extraction ---
        # HATVP DIA declarations list TWO separate amounts per participation:
        #   1. Valeur du capital détenu (capital value = goes into patrimoine)
        #   2. Revenus générés par la participation (dividends / income)
        # These must be kept separate; combining them produces absurdly large numbers.

        valeur_capital = None
        revenus_participation = None

        # Strategy 1: look for explicitly labeled fields (some PDF formats)
        val_match = re.search(
            r'Valeur\s+des?\s+parts?\s+(?:ou\s+actions?\s+)?d[ée]tenu(?:e)?s?\s*:?\s*'
            r'([\d][\d\s\xa0]*(?:[.,]\d{1,2})?)\s*€',
            block, re.IGNORECASE)
        if val_match:
            valeur_capital = parse_amount(val_match.group(1))

        rev_match = re.search(
            r'Revenus?\s+(?:générés?\s+(?:par\s+ces?\s+participations?|par\s+la\s+participation)?'
            r'|produits?)\s*:?\s*([\d][\d\s\xa0]*(?:[.,]\d{1,2})?)\s*€',
            block, re.IGNORECASE)
        if rev_match:
            revenus_participation = parse_amount(rev_match.group(1))

        if valeur_capital is None and revenus_participation is None:
            # Strategy 2: HATVP DIA table format – two unlabeled amounts appear together
            # before the first labeled field, e.g. "SCI 37 442 280000 €"
            # where "37 442" = 37 442 € (capital) and "280000" = 280 000 € (revenus).
            # NOTE: the same pattern is used in verify_coherence.py (_RE_TWO_AMOUNTS_MERGED)
            # for detecting and fixing already-parsed data – keep them in sync.
            first_label = re.search(
                r'Nombre de parts|Pourcentage du capital|Contr[ôo]le', block)
            # Limit to a generous prefix when no label is found; a company header
            # is always short (name + two amounts), well within 300 chars.
            pre_label_text = block[:first_label.start()] if first_label else block[:300]

            two_amounts = re.search(
                r'(\d+(?:[\s\xa0]\d{3})*(?:[.,]\d{1,2})?)\s+'
                r'(\d+(?:[\s\xa0]\d{3})*(?:[.,]\d{1,2})?)\s*€',
                pre_label_text)
            if two_amounts:
                valeur_capital = parse_amount(two_amounts.group(1))
                revenus_participation = parse_amount(two_amounts.group(2))

        if valeur_capital is not None or revenus_participation is not None:
            # Store capital and revenues as distinct fields
            if valeur_capital is not None:
                item['valeur_capital'] = valeur_capital
            if revenus_participation is not None:
                item['revenus_participation'] = revenus_participation
            # montant_euro = capital value only (what belongs in patrimoine)
            if valeur_capital is not None and valeur_capital > 0:
                item['montant_euro'] = valeur_capital
        else:
            # Fallback for non-DIA PDFs: use the largest amount found
            amounts = find_amounts_in_text(block)
            if amounts:
                item['montant_euro'] = max(amounts)

        if item:
            item['description'] = _clean_text(block[:500])
            items.append(item)

    return items


def _extract_mandat_electif_items(text: str) -> list[dict]:
    """Extract elective mandate data from DIA section 7°."""
    items = []

    # Clean the text first: remove DIA table header noise
    text = _clean_section_text(text)

    # Remove the section title line (7° Les fonctions et mandats électifs...)
    text = re.sub(r'^\s*7°\s+.*?\n', '', text, count=1)

    # Look for mandate entries — typically start with a function name or [Fonction conservée]
    # Split on "[Fonction conservée]" or similar markers, or "depuis le" blocks
    blocks = re.split(r'(?=\[Fonction\s+conserv[ée]e\]|\[Fonction\s+nouvelle\])', text)
    if len(blocks) <= 1:
        # Try splitting on double newlines (paragraph breaks)
        para_blocks = re.split(r'\n\s*\n', text)
        if len(para_blocks) > 1:
            blocks = [b for b in para_blocks if b.strip()]
        else:
            blocks = [text]

    for block in blocks:
        block = block.strip()
        if not block or len(block) < 5:
            continue
        if _section_is_neant(block):
            continue

        item = {}

        # Check for "Fonction conservée" marker
        if re.search(r'\[Fonction\s+conserv[ée]e\]', block):
            item['statut'] = 'Fonction conservée'
        elif re.search(r'\[Fonction\s+nouvelle\]', block):
            item['statut'] = 'Fonction nouvelle'

        # Extract mandate name (e.g., "Conseiller municipal", "Maire", etc.)
        for pattern in [
            r"(?m)^((?:Conseill|D[ée]put|S[ée]nat|Maire|Pr[ée]sident|Vice|Adjoint|Membre)[^\n]*)",
        ]:
            fm = re.search(pattern, block)
            if fm and 'mandat' not in item:
                mandat_text = _clean_text(fm.group(1))
                # Remove trailing year:amount patterns and noise
                mandat_text = re.sub(r'\s+\d{4}\s*:\s*\d[\d\s]*€.*$', '', mandat_text).strip()
                mandat_text = re.sub(r'\s+Net\s*$', '', mandat_text).strip()
                mandat_text = re.sub(r'\s+depuis\s+le\s+\d{1,2}/\d{4}.*$', '', mandat_text).strip()
                if mandat_text:
                    item['mandat'] = mandat_text

        # Extract "depuis le MM/YYYY" as start date
        depuis_match = re.search(r'depuis\s+le\s+(\d{1,2}/\d{4})', block)
        if depuis_match:
            item['date_debut'] = depuis_match.group(1)

        # Extract period
        period_match = re.search(r'de\s+(\d{1,2}/\d{4})\s+à\s+(\d{1,2}/\d{4})', block)
        if period_match:
            item['periode'] = f"{period_match.group(1)} à {period_match.group(2)}"

        # Extract comment — but filter out page footers and doc IDs
        comment_match = re.search(r'Commentaire\s*:\s*(.+?)(?:\n|$)', block)
        if comment_match:
            comment = _clean_text(comment_match.group(1))
            # Remove trailing year:amount patterns
            comment = re.sub(r'\s+\d{4}\s*:\s*\d[\d\s]*€.*$', '', comment).strip()
            # Remove page footer references
            comment = re.sub(r'\s*Page\s+\d+/\d+\s*D[IA]+/.*$', '', comment).strip()
            if comment and not re.match(r'^Page\s+\d+/\d+', comment):
                item['commentaire'] = comment

        # Extract year-by-year revenues
        year_salaries = []
        for ym in re.finditer(
            r'(20\d{2})\s*:\s*(\d[\d\s\xa0]*(?:[.,]\d{1,2})?)\s*(?:€|euros?)\s*(?:Net|Brut|net|brut)?',
            block,
        ):
            year = ym.group(1)
            amount = parse_amount(ym.group(2))
            if amount is not None and amount > 0:
                year_salaries.append({"annee": year, "montant": amount})

        if year_salaries:
            item['revenus_annuels'] = year_salaries
            item['montant_euro'] = sum(ys['montant'] for ys in year_salaries)

        if item and any(v for k, v in item.items() if k != 'description'):
            # Clean description: remove table header noise
            desc = _clean_section_text(block[:500])
            item['description'] = _clean_text(desc)
            items.append(item)

    return items


def _extract_observations(text: str) -> list[dict]:
    """Extract observation text from the observations section."""
    # Remove the "Observations" header
    content = re.sub(r'(?i)^Observations\s*\n?', '', text).strip()
    # Remove page footers
    content = re.sub(r'\nPage\s+\d+/\d+\s*$', '', content).strip()
    if not content:
        return []
    return [{"description": _clean_text(content)}]


def extract_section_items(section_text: str, section_name: str) -> list[dict]:
    """Extract individual items from a section's text."""
    # Check for "Néant" sections first
    if _section_is_neant(section_text):
        return []

    # Clean DIA table header noise from section text before processing
    section_text = _clean_section_text(section_text)

    items = []
    amounts = find_amounts_in_text(section_text)

    # DIA-specific section handlers
    if section_name == "activites_professionnelles":
        # Try DIA employer blocks first
        dia_items = _extract_dia_employer_blocks(section_text)
        if dia_items:
            return dia_items

    if section_name == "participations_financieres":
        # Try DIA société blocks
        part_items = _extract_participation_financiere_items(section_text)
        if part_items:
            return part_items

    if section_name == "mandats_electifs":
        # Try DIA mandate extraction
        mandat_items = _extract_mandat_electif_items(section_text)
        if mandat_items:
            return mandat_items

    if section_name == "observations":
        return _extract_observations(section_text)

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
    # Clean the text first: remove DIA table headers and page footers
    text = _clean_section_text(text)
    # Remove the section title line (5° Les activités professionnelles...)
    text = re.sub(r'^\s*5°\s+.*?\n', '', text, count=1)

    # Profession / activité
    for pattern in [
        r"(?i)(?:profession|activit[ée]|m[ée]tier)\s*[:;]\s*(.+?)(?:\s*[,\n]|$)",
        r"(?i)(?:exerce|occupe)\s+(?:la\s+)?(?:profession|activit[ée])\s+(?:de\s+)?(.+?)(?:\s*[,.\n]|$)",
    ]:
        m = re.search(pattern, text)
        if m:
            val = _clean_text(m.group(1)[:200])
            # Filter out noise values
            if val and val.lower() not in ("néant", "neant"):
                item["profession_conjoint"] = val
            break

    # Employer
    emp_match = re.search(r"(?i)employeur\s*[:;]\s*(.+?)(?:\n|$)", text)
    if emp_match:
        employer = _clean_text(emp_match.group(1).strip())
        # Remove page footer that may be appended
        employer = re.sub(r'\s*Page\s+\d+/\d+\s*D[IA]+/.*$', '', employer).strip()
        if employer and employer.lower() not in ("néant", "neant"):
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
    for brand in KNOWN_CAR_BRANDS:
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
        "neant_sections": [],
    }

    # Extract text
    text = extract_text_from_pdf(pdf_path, use_ocr=use_ocr)
    result["raw_text_length"] = len(text)

    if len(text.strip()) < MIN_TEXT_LENGTH:
        result["extraction_method"] = "failed"
        result["error"] = "Could not extract sufficient text from PDF"
        return result

    result["extraction_method"] = "pdfplumber"  # or "ocr" if OCR was used

    # Detect if this is a DSP (patrimoine) or DI/DIA (intérêts)
    is_dsp = bool(re.search(r"(?i)d[ée]claration\s+de\s+(?:situation\s+)?patrimoin", text))
    is_dia = bool(re.search(r"(?i)DIA/", text)) or bool(re.search(r"(?i)d[ée]claration\s+d['\u2019]int[ée]r[êe]ts?\s+et\s+d['\u2019]activit[ée]s?", text))
    is_di = bool(re.search(r"(?i)d[ée]claration\s+d['\u2019]int[ée]r[êe]ts?", text))
    if is_dsp:
        result["type_detected"] = "DSP"
    elif is_dia:
        result["type_detected"] = "DIA"
    elif is_di:
        result["type_detected"] = "DI"
    else:
        result["type_detected"] = "unknown"

    # Extract declarant name from header if available
    name_match = re.search(r'(?:DIA|DI|DSP|DSPM)/([A-ZÀ-Ü\-]+)-([A-ZÀ-Ü\-]+)', text)
    if name_match:
        result["declarant_nom"] = name_match.group(1).title()
        result["declarant_prenom"] = name_match.group(2).title()

    # Extract date from "Fait, le DD/MM/YYYY HH:MM:SS"
    date_match = re.search(r'Fait,?\s+le\s+(\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}:\d{2})?)', text)
    if date_match:
        result["date_declaration"] = date_match.group(1)

    # Split into sections
    sections = split_into_sections(text)
    result["sections_found"] = [k for k in sections if k != "header"]

    # Track which sections are "Néant"
    neant_sections = []
    for section_name, section_text in sections.items():
        if section_name == "header":
            continue
        if _section_is_neant(section_text):
            neant_sections.append(section_name)
    result["neant_sections"] = neant_sections

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

    # For DIA format, revenues from activites_professionnelles and mandats_electifs
    # should also count towards total revenues
    revenue_sections = {"revenus", "activites_professionnelles", "mandats_electifs"}

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

            # For DIA, also count revenues from professional activities and mandates
            if section_name in revenue_sections and section_name != "revenus":
                section_total = sum(
                    item.get("montant_euro", 0)
                    for item in items
                )
                totals["revenus"] += section_total

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
    Stores ALL extracted data inside elu['hatvp'] so the frontend can find it,
    and also updates top-level financial summary fields.
    Returns True if any data was updated.
    """
    summary = pdf_data.get("summary", {})
    updated = False

    # Ensure hatvp dict exists
    if not elu.get("hatvp"):
        elu["hatvp"] = {}
    hatvp = elu["hatvp"]

    # Update top-level patrimoine if PDF data is better
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

    # Mapping: PDF section name → (hatvp nb_* key, hatvp details_* key)
    # The details_* keys must match what the frontend expects in NB_TO_DETAILS_KEY
    section_to_hatvp = {
        "activites_professionnelles": ("nb_activites_professionnelles", "details_activites"),
        "activites_consultant":       ("nb_activites_consultant", "details_activites_consultant"),
        "participations_organes":     ("nb_participations_organes", "details_participations_organes"),
        "participations_financieres": ("nb_participations_financieres", "details_participations_financieres"),
        "activites_conjoint":         ("nb_activites_conjoint", "details_activites_conjoint"),
        "fonctions_benevoles":        ("nb_fonctions_benevoles", "details_fonctions_benevoles"),
        "mandats_electifs":           ("nb_mandats_electifs", "details_mandats"),
        "collaborateurs":             ("nb_activites_collaborateurs", "details_collaborateurs"),
        "revenus":                    ("nb_revenus", "details_revenus"),
        "biens_immobiliers":          ("nb_biens_immobiliers", "details_biens_immobiliers"),
        "comptes_bancaires":          ("nb_comptes_bancaires", "details_comptes_bancaires"),
        "instruments_financiers":     ("nb_instruments_financiers", "details_instruments_financiers"),
        "vehicules":                  ("nb_vehicules", "details_vehicules"),
        "biens_mobiliers_valeur":     ("nb_biens_mobiliers_valeur", "details_biens_divers"),
        "dettes":                     ("nb_dettes", "details_dettes"),
        "observations":               (None, "details_observations"),
    }

    for section_name, (nb_key, detail_key) in section_to_hatvp.items():
        items = pdf_data.get(section_name, [])
        if not items:
            continue

        # Set count in hatvp
        if nb_key:
            current_count = hatvp.get(nb_key, 0)
            if len(items) > current_count:
                hatvp[nb_key] = len(items)
                updated = True

        # Store detail items in hatvp
        if detail_key not in hatvp:
            hatvp[detail_key] = items
            updated = True
        else:
            existing = {json.dumps(it, sort_keys=True, default=str) for it in hatvp[detail_key]}
            for it in items:
                if json.dumps(it, sort_keys=True, default=str) not in existing:
                    hatvp[detail_key].append(it)
                    updated = True
            # Update count after merge
            if nb_key:
                hatvp[nb_key] = len(hatvp[detail_key])

    # Store neant sections info
    neant_sections = pdf_data.get("neant_sections", [])
    if neant_sections:
        hatvp["pdf_neant_sections"] = neant_sections

    # Store observations text
    if pdf_data.get("observations"):
        hatvp["details_observations"] = pdf_data["observations"]

    # Store PDF type detected
    type_detected = pdf_data.get("type_detected", "")
    if type_detected:
        hatvp["pdf_type_detected"] = type_detected

    # Store declaration date
    date_decl = pdf_data.get("date_declaration", "")
    if date_decl:
        hatvp["pdf_date_declaration"] = date_decl

    # Update total_revenus_euro in hatvp if PDF has better data
    if pdf_revenus > 0 and pdf_revenus > (hatvp.get("total_revenus_euro") or 0):
        hatvp["total_revenus_euro"] = pdf_revenus

    # Add PDF metadata
    if not elu.get("hatvp_pdf"):
        elu["hatvp_pdf"] = {}
    elu["hatvp_pdf"] = {
        "parsed_at": pdf_data.get("parsed_at", ""),
        "declarations_parsed": pdf_data.get("declarations_parsed", 0),
        "type_detected": type_detected,
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


def _flush_pending_updates(pending_ids: dict[str, dict]) -> None:
    """Apply pending PDF updates to elus.json and individual JSON files.

    For individual JSONs, merges PDF data into the EXISTING file (which may
    contain full XML detail data) rather than overwriting with data from
    elus.json (which may be slim). This preserves full detail data.
    """
    all_elus = load_elus()
    os.makedirs(ELUS_DETAIL_DIR, exist_ok=True)
    for e in all_elus:
        eid = e.get("id")
        if eid in pending_ids:
            update_elu_with_pdf_data(e, pending_ids[eid])
            # Merge PDF data into existing individual JSON (preserves full data)
            out_path = os.path.join(ELUS_DETAIL_DIR, f"{eid}.json")
            individual = e  # fallback: use elus.json entry
            if os.path.exists(out_path):
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        individual = json.load(f)
                    # Apply PDF data to the full individual data
                    update_elu_with_pdf_data(individual, pending_ids[eid])
                except (json.JSONDecodeError, OSError):
                    print(f"    ⚠ Could not read existing {eid}.json, using elus.json entry")
                    pass  # fall back to elus.json entry
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(individual, f, ensure_ascii=False, separators=(",", ":"))
    save_elus(all_elus)
    print(f"  ✓ Saved {len(pending_ids)} individual JSONs + elus.json")


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
    save_every = args.save_every
    bp = BatchProgress(
        "📄 PDF Processing",
        total=total,
        save_interval=save_every,
        progress_json_path=PROGRESS_JSON,
    )

    processed = 0
    updated_count = 0
    failed = 0
    # Buffer of updates accumulated since last checkpoint save
    pending_ids: dict[str, dict] = {}

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
            is_checkpoint = bp.tick(failed=True)
        else:
            processed += 1
            summary = result.get("summary", {})
            patrimoine = summary.get("patrimoine_brut_euro", 0)
            revenus = summary.get("revenus_euro", 0)
            has_section_data = any(
                result.get(sec) for sec in SECTION_PATTERNS
            )

            # Save results when ANY useful data is extracted (not just patrimoine)
            if patrimoine > 0 or revenus > 0 or has_section_data:
                updated_count += 1
                pending_ids[elu_id] = result
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

            is_checkpoint = bp.tick(updated=(patrimoine > 0 or revenus > 0 or has_section_data))

        # ── Incremental save every save_every elus ───────────────────────
        if is_checkpoint and not args.dry_run and pending_ids:
            print(f"\n💾 Checkpoint save ({i}/{total}) — {len(pending_ids)} pending updates…")
            _flush_pending_updates(pending_ids)
            pending_ids.clear()

    # ── Final save of any remaining pending updates ──────────────────────────
    if not args.dry_run and pending_ids:
        print(f"\n💾 Final save — {len(pending_ids)} remaining updates…")
        _flush_pending_updates(pending_ids)

    bp.finish()

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
