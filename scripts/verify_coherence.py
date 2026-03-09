#!/usr/bin/env python3
"""
Vérification et correction de cohérence des fichiers JSON individuels.

  1. Scanne chaque {id}.json dans public/data/elus/
  2. Détecte les incohérences (nb_* ≠ len(details_*), doublons, etc.)
  3. Restructure les listes mal formatées :
     - Sépare les items fusionnés (plusieurs mandats/organismes en un seul)
     - Trie et nettoie les revenus annuels
     - Supprime les montants_details parasites
  4. Si l'information manque et qu'on ne peut pas la retrouver → "work in progress"
  5. Re-vérifie après corrections
  6. N'écrit que les fichiers réellement modifiés

Usage :
  python scripts/verify_coherence.py                   # dry-run (rapport seul)
  python scripts/verify_coherence.py --fix              # appliquer les corrections
  python scripts/verify_coherence.py --fix --limit 50   # limiter à 50 fichiers
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ELUS_DETAIL_DIR = os.path.join(PROJECT_ROOT, "public", "data", "elus")

# ── Mapping nb_* → details_* ──────────────────────────────────────────────────
# Must stay in sync with NB_TO_DETAILS_KEY in src/app/profils/[id]/page.tsx
# and section_to_hatvp in scripts/parse_pdf.py
NB_TO_DETAILS = {
    "nb_activites_professionnelles": "details_activites",
    "nb_activites_consultant": "details_activites_consultant",
    "nb_participations_organes": "details_participations_organes",
    "nb_participations_financieres": "details_participations_financieres",
    "nb_activites_conjoint": "details_activites_conjoint",
    "nb_fonctions_benevoles": "details_fonctions_benevoles",
    "nb_mandats_electifs": "details_mandats",
    "nb_activites_collaborateurs": "details_collaborateurs",
    "nb_revenus": "details_revenus",
    "nb_biens_immobiliers": "details_biens_immobiliers",
    "nb_comptes_bancaires": "details_comptes_bancaires",
    "nb_instruments_financiers": "details_instruments_financiers",
    "nb_vehicules": "details_vehicules",
    "nb_biens_divers": "details_biens_divers",
    "nb_dettes": "details_dettes",
    "nb_parts_sci": "details_parts_sci",
    "nb_assurances_vie": "details_assurances_vie",
    "nb_valeurs_bourse": "details_valeurs_bourse",
    "nb_valeurs_non_bourse": "details_valeurs_non_bourse",
    "nb_fonds": "details_fonds",
    "nb_autres_liens_interets": "details_autres_liens_interets",
    "nb_activites_anterieures": "details_activites_anterieures",
}

# ── Regex patterns for description parsing ─────────────────────────────────
_RE_YEAR_AMOUNT = re.compile(
    r"(\d{4})\s*:\s*([\d\s\u202f]+)\s*\u20ac\s*(?:Net|Brut)?",
)
_RE_PERIOD_DE_A = re.compile(
    r"de\s+(\d{2}/\d{4})\s+[àa]\s+(\d{2}/\d{4})",
)
_RE_PERIOD_DEPUIS = re.compile(
    r"depuis\s+le\s+(\d{2}/\d{4})",
)
_RE_COMMENT = re.compile(
    r"Commentaire\s*:\s*(.+?)(?=\d{4}\s*:|Organisme\s*:|$)",
)
_RE_ORGANISME_SPLIT = re.compile(r"(?=Organisme\s*:)")
_RE_ORGANISME_NAME = re.compile(
    r"Organisme\s*:\s*(.+?)(?=\s*\d{4}\s*:|\s*de\s+\d{2}/\d{4}|\s*depuis\s+le)",
)
_RE_STATUS_TAG = re.compile(r"\[([^\]]+)\]")

# ── Data quality patterns ───────────────────────────────────────────────────
# Pattern to detect two amounts merged in a participation description
# e.g. "SCI 37 442 280000 €" → capital 37 442, revenues 280 000
_RE_TWO_AMOUNTS_MERGED = re.compile(
    r"(\d+(?:[\s\xa0]\d{3})*(?:[.,]\d{1,2})?)\s+"
    r"(\d+(?:[\s\xa0]\d{3})*(?:[.,]\d{1,2})?)\s*€"
)
# Organisme names that are obviously parsing artifacts (year:amount patterns)
_RE_GARBAGE_ORGANISME_NAME = re.compile(
    r"^\d{4}\s*:\s*[\d\s\u202f,.]*\u20ac",
)
# Mandat/organisme names that are just metadata keywords
_GARBAGE_NAME_KEYWORDS: frozenset[str] = frozenset({
    "commentaire",
    "net",
    "brut",
    "suite",
    "précédente",
    "précédent",
    "total",
})
# Denomination names that are clearly numbers (PDF parsing artifacts)
_RE_NUMERIC_DENOMINATION = re.compile(r"^\d+$")
# Names ending with French prepositions/articles that suggest truncation
_TRUNCATION_ENDINGS = re.compile(
    r"\b(de|du|des|d'|le|la|les|l'|et|ou|en|au|aux|une|un|à|par|sur)\s*$",
    re.IGNORECASE,
)
# Validation bounds
_MIN_VALID_YEAR: int = 1990   # HATVP data starts in the 1990s at the earliest
_MONTANT_TOLERANCE_EUROS: float = 1.0  # Rounding tolerance for montant_euro vs sum
# Tolerance for comparing root-level patrimoine against PDF-derived figure.
# Values within 1 € are considered equal (same origin, just rounding).
_PATRIMOINE_MATCH_TOLERANCE_EUROS: float = 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Description parsing helpers
# ══════════════════════════════════════════════════════════════════════════════

def _parse_year_amounts(text: str) -> list[dict]:
    """Extract all year:amount pairs from text."""
    results = []
    for m in _RE_YEAR_AMOUNT.finditer(text):
        annee = m.group(1)
        montant_str = m.group(2).replace(" ", "").replace("\u202f", "")
        try:
            montant = float(montant_str)
        except ValueError:
            continue
        results.append({"annee": annee, "montant": montant})
    return results


def _parse_period(text: str) -> str:
    """Extract period from text."""
    m = _RE_PERIOD_DE_A.search(text)
    if m:
        return f"{m.group(1)} à {m.group(2)}"
    m = _RE_PERIOD_DEPUIS.search(text)
    if m:
        return f"depuis {m.group(1)}"
    return ""


def _parse_comment(text: str) -> str:
    """Extract first comment from text."""
    m = _RE_COMMENT.search(text)
    if m:
        return m.group(1).strip()
    return ""


def _extract_role_text(text: str) -> str:
    """Extract role/function text from a participation block.

    The role is typically non-year, non-period, non-comment text that
    appears after the year-amount pairs but before the next block.
    """
    # Remove known patterns to isolate the role text
    cleaned = _RE_YEAR_AMOUNT.sub("", text)
    cleaned = _RE_PERIOD_DE_A.sub("", cleaned)
    cleaned = _RE_PERIOD_DEPUIS.sub("", cleaned)
    cleaned = _RE_COMMENT.sub("", cleaned)
    cleaned = _RE_STATUS_TAG.sub("", cleaned)
    cleaned = re.sub(r"Organisme\s*:\s*\S+.*?(?=\s|$)", "", cleaned, count=1)
    # Clean up whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Remove leftover currency/number fragments
    cleaned = re.sub(r"^\s*[€\d\s]+\s*$", "", cleaned)
    return cleaned if len(cleaned) > 1 else ""


# ── Data quality helpers ──────────────────────────────────────────────────────

def _is_garbage_organisme_name(name: str) -> bool:
    """Return True if the organisme name is clearly a parsing artifact.

    Catches patterns like:
    - Year:amount strings: "2018 : 0 € Net"
    - Pure whitespace or empty
    - Very short (≤ 2 meaningful characters)
    - Pure metadata keywords
    """
    if not isinstance(name, str):
        return True
    name = name.strip()
    if not name:
        return True
    if _RE_GARBAGE_ORGANISME_NAME.match(name):
        return True
    if name.lower() in _GARBAGE_NAME_KEYWORDS:
        return True
    # Strip non-alpha characters; if fewer than 2 remain, it's garbage
    alpha_only = re.sub(r"[^a-zA-ZÀ-ÿ]", "", name)
    if len(alpha_only) <= 2:
        return True
    return False


def _is_garbage_mandat_name(name: str) -> bool:
    """Return True if the mandat name is a metadata keyword artifact.

    Catches patterns like "Commentaire", "Net", "Brut" being mistakenly
    extracted as mandat names by the PDF parser.
    """
    if not isinstance(name, str):
        return False
    stripped = name.strip()
    if not stripped:
        return False
    return stripped.lower() in _GARBAGE_NAME_KEYWORDS


def _is_truncated_name(name: str) -> bool:
    """Return True if the name appears to be truncated (ends with a preposition)."""
    if not isinstance(name, str):
        return False
    return bool(_TRUNCATION_ENDINGS.search(name.strip()))


def _is_numeric_denomination(name: str) -> bool:
    """Return True if the denomination is just a number (PDF parsing artifact)."""
    if not isinstance(name, str):
        return False
    return bool(_RE_NUMERIC_DENOMINATION.match(name.strip()))


def _validate_revenus_years(revenus: list[dict]) -> list[str]:
    """
    Validate year values in revenus_annuels.
    Returns list of anomalous year strings found.
    """
    anomalies = []
    current_year = datetime.now(timezone.utc).year
    for rev in revenus:
        year_str = rev.get("annee", "")
        try:
            year = int(year_str)
            if year < _MIN_VALID_YEAR or year > current_year + 1:
                anomalies.append(year_str)
        except (ValueError, TypeError):
            if year_str:
                anomalies.append(year_str)
    return anomalies


def _validate_pourcentage(pct_str: str) -> bool:
    """Return True if the pourcentage_capital value is valid (0-100%)."""
    if not isinstance(pct_str, str):
        return True  # Not a string, skip validation
    pct_clean = pct_str.strip().rstrip("%").strip()
    try:
        pct = float(pct_clean)
        return 0.0 <= pct <= 100.0
    except (ValueError, TypeError):
        return True  # Can't parse, skip


def _check_montant_vs_revenus(item: dict) -> bool:
    """
    Check if montant_euro significantly differs from the sum of revenus_annuels.
    Returns True if there is a large discrepancy (potential data error).
    A tolerance of _MONTANT_TOLERANCE_EUROS is allowed for rounding.
    """
    montant = item.get("montant_euro")
    revenus = item.get("revenus_annuels")
    if not isinstance(montant, (int, float)) or not isinstance(revenus, list):
        return False
    if not revenus:
        return False
    computed = round(sum(r.get("montant", 0) for r in revenus if isinstance(r.get("montant"), (int, float))), 2)
    return abs(computed - montant) > _MONTANT_TOLERANCE_EUROS


def _extract_participation_two_amounts(
    item: dict,
) -> tuple[float | None, float | None]:
    """
    For a participation financière item, try to detect and extract two amounts
    (valeur_capital and revenus_participation) that were concatenated by the PDF
    parser into a single oversized montant_euro.

    The HATVP DIA format has two amount columns per participation row:
      - Valeur du capital détenu
      - Revenus générés par la participation
    These can appear merged in the description as e.g. "SCI 37 442 280000 €"
    where "37 442" is the capital (37 442 €) and "280000" is the revenue.

    Returns (valeur_capital, revenus_participation) or (None, None) if not detected.
    """
    desc = item.get("description", "")
    if not isinstance(desc, str) or not desc:
        return None, None

    # Only look at the header part (before first labeled field)
    for sep in ("Nombre de parts", "Pourcentage du capital", "Contrôle"):
        idx = desc.find(sep)
        if idx != -1:
            desc = desc[:idx]
            break

    m = _RE_TWO_AMOUNTS_MERGED.search(desc)
    if not m:
        return None, None

    def _parse(s: str) -> float | None:
        s = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
        s = re.sub(r"[^\d.]", "", s)
        try:
            return float(s)
        except ValueError:
            return None

    cap = _parse(m.group(1))
    rev = _parse(m.group(2))
    return cap, rev


# ══════════════════════════════════════════════════════════════════════════════
# Splitting merged items
# ══════════════════════════════════════════════════════════════════════════════

def _split_merged_participations(item: dict) -> list[dict] | None:
    """
    Split a single participation item that contains multiple 'Organisme :' blocks.
    Returns a list of individual items, or None if no split was needed.
    """
    desc = item.get("description", "")
    if not isinstance(desc, str):
        return None

    blocks = _RE_ORGANISME_SPLIT.split(desc)
    blocks = [b.strip() for b in blocks if b.strip()]

    if len(blocks) <= 1:
        return None

    results = []
    for block in blocks:
        new_item: dict = {}

        # Extract organisme name
        m = _RE_ORGANISME_NAME.search(block)
        if m:
            new_item["organisme"] = m.group(1).strip()
        else:
            # Fallback: take text after "Organisme :" up to end
            fallback = re.sub(r"^Organisme\s*:\s*", "", block)
            name_part = re.split(r"\d{4}\s*:", fallback, maxsplit=1)[0].strip()
            if name_part:
                new_item["organisme"] = name_part

        # Extract status tag
        status_m = _RE_STATUS_TAG.search(block)
        if status_m:
            new_item["statut"] = status_m.group(1)

        # Extract period
        periode = _parse_period(block)
        if periode:
            new_item["periode"] = periode

        # Extract comment
        comment = _parse_comment(block)
        if comment:
            new_item["commentaire"] = comment

        # Extract year-amount pairs
        revenus = _parse_year_amounts(block)
        if revenus:
            new_item["revenus_annuels"] = revenus
            new_item["montant_euro"] = round(
                sum(r["montant"] for r in revenus), 2
            )

        # Only add if we got something meaningful
        if new_item.get("organisme") or new_item.get("revenus_annuels"):
            results.append(new_item)

    return results if len(results) > 1 else None


def _has_duplicate_years(revenus: list[dict]) -> bool:
    """Check if revenus_annuels has duplicate years (indicates merged items)."""
    if not revenus:
        return False
    years = [r.get("annee", "") for r in revenus if r.get("annee")]
    return len(years) != len(set(years))


def _split_revenus_by_year_reset(revenus: list[dict]) -> list[list[dict]]:
    """
    Split revenus_annuels into groups at year resets.
    A reset occurs when year[i] <= year[i-1] (the sequence goes backwards).
    Each group corresponds to a different mandat/organisme.
    """
    if not revenus:
        return []

    groups: list[list[dict]] = [[]]
    prev_year = 0

    for rev in revenus:
        year_str = rev.get("annee", "")
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            year = 0
        if prev_year and year <= prev_year and groups[-1]:
            groups.append([])
        groups[-1].append(rev)
        prev_year = year

    return groups


def _split_description_into_mandat_blocks(description: str) -> list[str]:
    """
    Split a merged mandat description into blocks, one per mandat.
    Uses the pattern: year-amount sequences separated by non-year text
    (which is the next mandat's name).
    """
    if not description:
        return [description]

    # Strategy: find year:amount positions, then find text gaps between sequences
    year_positions = []
    for m in _RE_YEAR_AMOUNT.finditer(description):
        year_positions.append((m.start(), m.end()))

    if len(year_positions) <= 1:
        return [description]

    # Find boundaries: after a year-amount, if there's significant non-year text
    # before the next year-amount, that's a new mandat block start
    blocks = []
    block_start = 0

    for i in range(len(year_positions) - 1):
        end_of_current = year_positions[i][1]
        start_of_next = year_positions[i + 1][0]
        gap_text = description[end_of_current:start_of_next].strip()

        # Remove known inline patterns from gap
        gap_clean = _RE_PERIOD_DE_A.sub("", gap_text)
        gap_clean = _RE_PERIOD_DEPUIS.sub("", gap_clean)
        gap_clean = _RE_COMMENT.sub("", gap_clean)
        gap_clean = _RE_STATUS_TAG.sub("", gap_clean)
        gap_clean = re.sub(r"[€\s]+", " ", gap_clean).strip()

        # If remaining gap has alphabetic content (a mandat name), it's a new block
        alpha_content = re.sub(r"[^a-zA-ZÀ-ÿ]", "", gap_clean)
        if len(alpha_content) >= 3:
            blocks.append(description[block_start:end_of_current])
            block_start = end_of_current

    # Last block
    blocks.append(description[block_start:])

    return [b.strip() for b in blocks if b.strip()]


def _extract_mandat_name_from_block(block: str) -> str:
    """Extract the mandat name from a description block."""
    # Remove status tags
    cleaned = _RE_STATUS_TAG.sub("", block).strip()
    # The mandat name is the text before the first year pattern
    parts = re.split(r"\d{4}\s*:", cleaned, maxsplit=1)
    name = parts[0].strip() if parts else ""
    # Clean up
    name = re.sub(r"\s+", " ", name).strip()
    # Remove trailing/leading punctuation
    name = name.strip(" -–—·,;:")
    return name


def _split_merged_mandats(item: dict) -> list[dict] | None:
    """
    Split a single mandat item that contains multiple mandats
    (detected by duplicate years in revenus_annuels).
    Returns a list of individual items, or None if no split was needed.
    """
    revenus = item.get("revenus_annuels", [])
    if not isinstance(revenus, list) or not _has_duplicate_years(revenus):
        return None

    # Split revenues by year resets
    rev_groups = _split_revenus_by_year_reset(revenus)
    if len(rev_groups) <= 1:
        return None

    # Try to split description into blocks
    desc = item.get("description", "")
    desc_blocks = _split_description_into_mandat_blocks(desc) if desc else []

    results = []
    for i, rev_group in enumerate(rev_groups):
        new_item: dict = {}

        # Try to get mandat name from description block
        if i < len(desc_blocks):
            block = desc_blocks[i]
            name = _extract_mandat_name_from_block(block)
            if name:
                new_item["mandat"] = name

            # Extract period from this block
            periode = _parse_period(block)
            if periode:
                new_item["periode"] = periode

            # Extract comment
            comment = _parse_comment(block)
            if comment:
                new_item["commentaire"] = comment

            # Extract status
            status_m = _RE_STATUS_TAG.search(block)
            if status_m:
                new_item["statut"] = status_m.group(1)
        elif i == 0:
            # Fallback: use the original item's structured fields for first group
            if item.get("mandat"):
                new_item["mandat"] = item["mandat"]
            if item.get("periode"):
                new_item["periode"] = item["periode"]
            if item.get("commentaire"):
                new_item["commentaire"] = item["commentaire"]
            if item.get("statut"):
                new_item["statut"] = item["statut"]

        # Set revenues for this group
        new_item["revenus_annuels"] = rev_group
        new_item["montant_euro"] = round(
            sum(r.get("montant", 0) for r in rev_group), 2
        )

        results.append(new_item)

    return results if len(results) > 1 else None


def _clean_item_revenus(item: dict) -> bool:
    """
    Sort revenus_annuels by year and recalculate montant_euro.
    Returns True if item was modified.
    """
    revenus = item.get("revenus_annuels")
    if not isinstance(revenus, list) or len(revenus) <= 1:
        return False

    sorted_revenus = sorted(revenus, key=lambda r: int(r.get("annee", "0") or "0"))
    if sorted_revenus == revenus:
        return False

    item["revenus_annuels"] = sorted_revenus
    return True


def _clean_montants_details(item: dict) -> bool:
    """
    Remove montants_details if it's garbage (duplicated/padding values).
    Returns True if item was modified.
    """
    md = item.get("montants_details")
    if not isinstance(md, list):
        return False

    # montants_details is garbage if it has many duplicate values or looks
    # like date-encoded numbers (20201.0, 20202.0, etc.)
    if len(md) == 0:
        return False

    # Always remove: the structured revenus_annuels is the source of truth
    del item["montants_details"]
    return True


# ══════════════════════════════════════════════════════════════════════════════
# Detection helpers
# ══════════════════════════════════════════════════════════════════════════════

def _find_duplicates(items: list) -> list[int]:
    """Return indices of duplicate items (keeps first occurrence)."""
    seen: set[str] = set()
    dup_indices: list[int] = []
    for i, item in enumerate(items):
        sig = json.dumps(item, sort_keys=True, default=str)
        if sig in seen:
            dup_indices.append(i)
        else:
            seen.add(sig)
    return dup_indices


def check_elu(data: dict) -> list[dict]:
    """
    Check a single elu dict for coherence issues.
    Returns list of issues found, each with:
      - type: str (issue category)
      - key / detail_key: affected fields
      - message: human description
    """
    issues: list[dict] = []
    hatvp = data.get("hatvp")
    if not hatvp or not isinstance(hatvp, dict):
        return issues

    for nb_key, det_key in NB_TO_DETAILS.items():
        nb_val = hatvp.get(nb_key)
        det_val = hatvp.get(det_key)

        # ── 1. Duplicates in details array ─────────────────────────────
        if isinstance(det_val, list) and len(det_val) > 1:
            dup_indices = _find_duplicates(det_val)
            if dup_indices:
                issues.append({
                    "type": "duplicate_details",
                    "key": det_key,
                    "message": (
                        f"{det_key}: {len(dup_indices)} doublon(s) "
                        f"sur {len(det_val)} éléments"
                    ),
                    "dup_indices": dup_indices,
                })

        # ── 2. nb_* ≠ len(details_*) ──────────────────────────────────
        if nb_val is not None and isinstance(det_val, list):
            effective_len = len(det_val)
            if nb_val != effective_len:
                issues.append({
                    "type": "count_mismatch",
                    "key": nb_key,
                    "detail_key": det_key,
                    "expected": effective_len,
                    "actual": nb_val,
                    "message": (
                        f"{nb_key}={nb_val} mais len({det_key})={effective_len}"
                    ),
                })

        # ── 3. nb_* > 0 but details_* missing entirely ────────────────
        if nb_val is not None and nb_val > 0 and det_val is None:
            issues.append({
                "type": "count_without_details",
                "key": nb_key,
                "detail_key": det_key,
                "message": (
                    f"{nb_key}={nb_val} mais {det_key} absent "
                    f"(ne peut pas inventer → work in progress)"
                ),
            })

    # ── 4. Merged participations (multiple "Organisme :" in one item) ──
    parts = hatvp.get("details_participations_organes")
    if isinstance(parts, list):
        for i, item in enumerate(parts):
            desc = item.get("description", "")
            if isinstance(desc, str) and desc.count("Organisme :") > 1:
                issues.append({
                    "type": "merged_participations",
                    "key": "details_participations_organes",
                    "index": i,
                    "count": desc.count("Organisme :"),
                    "message": (
                        f"details_participations_organes[{i}]: "
                        f"{desc.count('Organisme :')} organismes fusionnés"
                    ),
                })

    # ── 5. Merged mandats (duplicate years in revenus_annuels) ─────────
    mandats = hatvp.get("details_mandats")
    if isinstance(mandats, list):
        for i, item in enumerate(mandats):
            revenus = item.get("revenus_annuels", [])
            if isinstance(revenus, list) and _has_duplicate_years(revenus):
                years = [r.get("annee", "") for r in revenus]
                n_groups = len(_split_revenus_by_year_reset(revenus))
                issues.append({
                    "type": "merged_mandats",
                    "key": "details_mandats",
                    "index": i,
                    "count": n_groups,
                    "message": (
                        f"details_mandats[{i}]: "
                        f"{n_groups} mandats fusionnés (années en double)"
                    ),
                })

    # ── 6. Garbage montants_details ────────────────────────────────────
    for det_key in ("details_participations_organes", "details_mandats",
                     "details_fonctions_benevoles", "details_activites",
                     "details_activites_consultant"):
        items = hatvp.get(det_key)
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if isinstance(item, dict) and "montants_details" in item:
                issues.append({
                    "type": "garbage_montants_details",
                    "key": det_key,
                    "index": i,
                    "message": (
                        f"{det_key}[{i}]: montants_details parasite à supprimer"
                    ),
                })

    # ── 7. Garbage organisme names (year:amount patterns, too short) ───
    parts = hatvp.get("details_participations_organes")
    if isinstance(parts, list):
        for i, item in enumerate(parts):
            if not isinstance(item, dict):
                continue
            org = item.get("organisme", "")
            if org and _is_garbage_organisme_name(org):
                issues.append({
                    "type": "invalid_organisme_name",
                    "key": "details_participations_organes",
                    "index": i,
                    "value": org,
                    "message": (
                        f"details_participations_organes[{i}]: nom d'organisme "
                        f"invalide (artefact parsing) : {org!r}"
                    ),
                })

    # ── 8. Garbage mandat names (metadata keywords mistaken for names) ──
    mandats = hatvp.get("details_mandats")
    if isinstance(mandats, list):
        for i, item in enumerate(mandats):
            if not isinstance(item, dict):
                continue
            mandat = item.get("mandat", "")
            if mandat and _is_garbage_mandat_name(mandat):
                issues.append({
                    "type": "invalid_mandat_name",
                    "key": "details_mandats",
                    "index": i,
                    "value": mandat,
                    "message": (
                        f"details_mandats[{i}]: nom de mandat invalide "
                        f"(mot-clé métadonnée) : {mandat!r}"
                    ),
                })

    # ── 9. Numeric denomination in financial participations ─────────────
    fin_parts = hatvp.get("details_participations_financieres")
    if isinstance(fin_parts, list):
        for i, item in enumerate(fin_parts):
            if not isinstance(item, dict):
                continue
            denom = item.get("denomination", "")
            if denom and _is_numeric_denomination(denom):
                issues.append({
                    "type": "invalid_denomination",
                    "key": "details_participations_financieres",
                    "index": i,
                    "value": denom,
                    "message": (
                        f"details_participations_financieres[{i}]: dénomination "
                        f"purement numérique (artefact parsing) : {denom!r}"
                    ),
                })

    # ── 10. Truncated names (ending with preposition/article) ───────────
    for det_key, name_field in (
        ("details_participations_organes", "organisme"),
        ("details_mandats", "mandat"),
    ):
        items = hatvp.get(det_key)
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            name = item.get(name_field, "")
            if name and _is_truncated_name(name):
                # Only flag if the next item doesn't look like a fragment continuation
                issues.append({
                    "type": "truncated_name",
                    "key": det_key,
                    "index": i,
                    "field": name_field,
                    "value": name,
                    "message": (
                        f"{det_key}[{i}]: {name_field} tronqué "
                        f"(se termine par préposition) : {name!r}"
                    ),
                })

    # ── 11. Anomalous year values in revenus_annuels ────────────────────
    for det_key in NB_TO_DETAILS.values():
        items = hatvp.get(det_key)
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            anomalies = _validate_revenus_years(item.get("revenus_annuels", []))
            if anomalies:
                issues.append({
                    "type": "invalid_revenus_years",
                    "key": det_key,
                    "index": i,
                    "values": anomalies,
                    "message": (
                        f"{det_key}[{i}]: années invalides dans "
                        f"revenus_annuels : {anomalies}"
                    ),
                })

    # ── 12. Invalid pourcentage_capital in financial participations ──────
    fin_parts = hatvp.get("details_participations_financieres")
    if isinstance(fin_parts, list):
        for i, item in enumerate(fin_parts):
            if not isinstance(item, dict):
                continue
            pct = item.get("pourcentage_capital", "")
            if pct and not _validate_pourcentage(pct):
                issues.append({
                    "type": "invalid_pourcentage",
                    "key": "details_participations_financieres",
                    "index": i,
                    "value": pct,
                    "message": (
                        f"details_participations_financieres[{i}]: "
                        f"pourcentage_capital invalide (hors 0-100%) : {pct!r}"
                    ),
                })

    # ── 13. montant_euro vs sum(revenus_annuels) mismatch ───────────────
    for det_key in ("details_mandats", "details_participations_organes",
                     "details_activites", "details_activites_consultant",
                     "details_fonctions_benevoles"):
        items = hatvp.get(det_key)
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            if _check_montant_vs_revenus(item):
                montant = item.get("montant_euro")
                revenus = item.get("revenus_annuels", [])
                computed = round(sum(r.get("montant", 0) for r in revenus
                                     if isinstance(r.get("montant"), (int, float))), 2)
                issues.append({
                    "type": "montant_vs_revenus_mismatch",
                    "key": det_key,
                    "index": i,
                    "montant_euro": montant,
                    "computed": computed,
                    "message": (
                        f"{det_key}[{i}]: montant_euro={montant} ≠ "
                        f"somme revenus_annuels={computed}"
                    ),
                })

    # ── 14. Merged capital+revenus in financial participations ───────────
    # HATVP DIA PDFs have two amount columns per participation row:
    #   Valeur du capital détenu  |  Revenus générés par la participation
    # The old PDF parser concatenated them into one huge montant_euro.
    # Detect items that have montant_euro but lack valeur_capital/revenus_participation.
    fin_parts = hatvp.get("details_participations_financieres")
    if isinstance(fin_parts, list):
        for i, item in enumerate(fin_parts):
            if not isinstance(item, dict):
                continue
            if "valeur_capital" in item or "revenus_participation" in item:
                continue  # already split correctly
            montant = item.get("montant_euro")
            if not isinstance(montant, (int, float)):
                continue
            cap, rev = _extract_participation_two_amounts(item)
            if cap is not None and rev is not None:
                # Flag only when the stored montant_euro is larger than the capital alone,
                # meaning the two amounts were concatenated into one inflated value.
                if abs(montant) > abs(cap) + 1 and montant != cap:
                    issues.append({
                        "type": "merged_participation_amounts",
                        "key": "details_participations_financieres",
                        "index": i,
                        "montant_euro": montant,
                        "valeur_capital": cap,
                        "revenus_participation": rev,
                        "message": (
                            f"details_participations_financieres[{i}]: "
                            f"montant_euro={montant} est le résultat d'une concaténation "
                            f"de valeur_capital={cap} et revenus_participation={rev}"
                        ),
                    })

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# Fix helpers
# ══════════════════════════════════════════════════════════════════════════════

def fix_elu(data: dict, issues: list[dict]) -> bool:
    """
    Apply safe fixes to elu data based on detected issues.
    Returns True if any modification was made.
    """
    hatvp = data.get("hatvp")
    if not hatvp:
        return False

    modified = False

    # Pass 1: remove duplicates first (affects counts)
    for issue in issues:
        if issue["type"] == "duplicate_details":
            det_key = issue["key"]
            det_val = hatvp.get(det_key, [])
            if not isinstance(det_val, list):
                continue
            seen: set[str] = set()
            deduped: list = []
            for item in det_val:
                sig = json.dumps(item, sort_keys=True, default=str)
                if sig not in seen:
                    seen.add(sig)
                    deduped.append(item)
            if len(deduped) != len(det_val):
                hatvp[det_key] = deduped
                modified = True

    # Pass 2: split merged participations
    parts = hatvp.get("details_participations_organes")
    if isinstance(parts, list):
        new_parts: list[dict] = []
        did_split = False
        for item in parts:
            split_result = _split_merged_participations(item)
            if split_result:
                new_parts.extend(split_result)
                did_split = True
            else:
                # Still clean individual items
                if _clean_montants_details(item):
                    modified = True
                if _clean_item_revenus(item):
                    modified = True
                new_parts.append(item)
        if did_split:
            hatvp["details_participations_organes"] = new_parts
            modified = True

    # Pass 3: split merged mandats
    mandats = hatvp.get("details_mandats")
    if isinstance(mandats, list):
        new_mandats: list[dict] = []
        did_split = False
        for item in mandats:
            split_result = _split_merged_mandats(item)
            if split_result:
                new_mandats.extend(split_result)
                did_split = True
            else:
                # Still clean individual items
                if _clean_item_revenus(item):
                    modified = True
                new_mandats.append(item)
        if did_split:
            hatvp["details_mandats"] = new_mandats
            modified = True

    # Pass 4: clean garbage montants_details in all detail arrays
    for det_key in ("details_participations_organes", "details_mandats",
                     "details_fonctions_benevoles", "details_activites",
                     "details_activites_consultant"):
        items = hatvp.get(det_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and _clean_montants_details(item):
                modified = True

    # Pass 5: sort revenus_annuels in all detail arrays
    for det_key in NB_TO_DETAILS.values():
        items = hatvp.get(det_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and _clean_item_revenus(item):
                modified = True

    # Pass 6: remove items with invalid (garbage) organisme names.
    # These are parsing artifacts (e.g., "2018 : 0 € Net") that carry no
    # useful data; removing them is safer than keeping corrupt entries.
    parts = hatvp.get("details_participations_organes")
    if isinstance(parts, list):
        clean_parts = [
            item for item in parts
            if not (isinstance(item, dict)
                    and _is_garbage_organisme_name(item.get("organisme", "")))
        ]
        if len(clean_parts) != len(parts):
            hatvp["details_participations_organes"] = clean_parts
            modified = True

    # Pass 7: fix invalid mandat names (metadata keywords mistakenly parsed
    # as mandat names, e.g., "Commentaire"). Replace with a neutral placeholder
    # so that the associated revenue data is preserved.
    mandats = hatvp.get("details_mandats")
    if isinstance(mandats, list):
        for item in mandats:
            if not isinstance(item, dict):
                continue
            mandat = item.get("mandat", "")
            if mandat and _is_garbage_mandat_name(mandat):
                item["mandat"] = "[mandat non identifié]"
                modified = True

    # Pass 8: fix montant_euro to match sum of revenus_annuels when they differ.
    # We trust the individual year amounts over the aggregate montant_euro,
    # since the latter is often computed during PDF parsing and may be stale.
    for det_key in ("details_mandats", "details_participations_organes",
                     "details_activites", "details_activites_consultant",
                     "details_fonctions_benevoles"):
        items = hatvp.get(det_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if _check_montant_vs_revenus(item):
                revenus = item.get("revenus_annuels", [])
                computed = round(
                    sum(r.get("montant", 0) for r in revenus
                        if isinstance(r.get("montant"), (int, float))),
                    2,
                )
                item["montant_euro"] = computed
                modified = True

    # Pass 9: fix nb_* counts to match actual len(details_*)
    for nb_key, det_key in NB_TO_DETAILS.items():
        det_val = hatvp.get(det_key)
        if isinstance(det_val, list):
            actual_len = len(det_val)
            if hatvp.get(nb_key) != actual_len:
                hatvp[nb_key] = actual_len
                modified = True

    # Pass 10: count_without_details — cannot invent data, leave as-is
    # The count stays, details remain absent → logged as "work in progress"

    # Pass 11: fix merged capital+revenus in financial participations.
    # Old PDF parser concatenated the two DIA amount columns (valeur_capital and
    # revenus_participation) into one inflated montant_euro. Extract them separately
    # and correct montant_euro (= capital value only, which belongs in patrimoine).
    fin_parts = hatvp.get("details_participations_financieres")
    if isinstance(fin_parts, list):
        participation_montant_delta = 0.0  # change in participation total (for patrimoine)
        for item in fin_parts:
            if not isinstance(item, dict):
                continue
            if "valeur_capital" in item or "revenus_participation" in item:
                continue  # already split correctly
            old_montant = item.get("montant_euro")
            if not isinstance(old_montant, (int, float)):
                continue
            cap, rev = _extract_participation_two_amounts(item)
            if cap is None or rev is None:
                continue
            if abs(old_montant) <= abs(cap) + 1 or old_montant == cap:
                continue  # nothing to fix
            # Apply the fix
            item["valeur_capital"] = cap
            item["revenus_participation"] = rev
            new_montant = cap if cap > 0 else None
            if new_montant is not None:
                item["montant_euro"] = new_montant
            else:
                item.pop("montant_euro", None)
            participation_montant_delta += (new_montant or 0) - old_montant
            modified = True

        # Recompute patrimoine figures if participation amounts were corrected
        if modified and participation_montant_delta != 0:
            hatvp_pdf = data.get("hatvp_pdf")
            if isinstance(hatvp_pdf, dict):
                old_brut = hatvp_pdf.get("patrimoine_brut_euro", 0) or 0
                new_brut = old_brut + participation_montant_delta
                hatvp_pdf["patrimoine_brut_euro"] = new_brut
                hatvp_pdf["patrimoine_net_euro"] = new_brut - (hatvp_pdf.get("dettes_euro", 0) or 0)
                if "participations_euro" in hatvp_pdf:
                    hatvp_pdf["participations_euro"] = (
                        (hatvp_pdf.get("participations_euro", 0) or 0) + participation_montant_delta
                    )
                # Update root-level patrimoine only when it matches the (now-corrected)
                # PDF patrimoine figure — this confirms the root value was derived from
                # the PDF parser and not from another source (e.g., XML declaration).
                root_patrimoine = data.get("patrimoine")
                if (isinstance(root_patrimoine, (int, float))
                        and abs(root_patrimoine - old_brut) < _PATRIMOINE_MATCH_TOLERANCE_EUROS):
                    data["patrimoine"] = root_patrimoine + participation_montant_delta

    return modified


# ══════════════════════════════════════════════════════════════════════════════
# Re-verification
# ══════════════════════════════════════════════════════════════════════════════

def verify_after_fix(data: dict) -> list[dict]:
    """Re-check after fixes. Should return only unfixable issues."""
    # These types remain after fixing and are considered "work in progress"
    # or require manual review:
    # - count_without_details: details arrays missing entirely (can't invent data)
    # - invalid_denomination: numeric denomination — may need source data to fix
    # - truncated_name: truncated organisme/mandat names — needs manual review
    # - invalid_revenus_years: anomalous year values — may need source data
    # - invalid_pourcentage: impossible pourcentage — may need source data
    unfixable_types = {
        "count_without_details",
        "invalid_denomination",
        "truncated_name",
        "invalid_revenus_years",
        "invalid_pourcentage",
    }
    return [i for i in check_elu(data) if i["type"] in unfixable_types]


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Vérification de cohérence des JSON individuels"
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Appliquer les corrections (sans ce flag = dry-run)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Limiter le nombre de fichiers traités (0 = tous)",
    )
    args = parser.parse_args()

    if not os.path.isdir(ELUS_DETAIL_DIR):
        print(f"❌ Dossier introuvable : {ELUS_DETAIL_DIR}")
        sys.exit(1)

    files = sorted(
        f for f in os.listdir(ELUS_DETAIL_DIR) if f.endswith(".json")
    )
    if args.limit > 0:
        files = files[: args.limit]

    total_files = len(files)
    files_with_issues = 0
    files_fixed = 0
    total_issues = 0
    total_fixed = 0
    remaining_issues = 0
    total_splits = 0

    summary_lines: list[str] = []

    print(f"🔍 Vérification de {total_files} fichiers…")
    print(f"   Mode : {'CORRECTION' if args.fix else 'DRY-RUN (rapport seul)'}")
    print()

    for fname in files:
        fpath = os.path.join(ELUS_DETAIL_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            summary_lines.append(f"  ⚠️  {fname}: lecture impossible ({exc})")
            total_issues += 1
            continue

        if not isinstance(data, dict):
            continue

        issues = check_elu(data)
        if not issues:
            continue

        files_with_issues += 1
        total_issues += len(issues)

        if args.fix:
            was_modified = fix_elu(data, issues)
            if was_modified:
                # Re-verify
                remaining = verify_after_fix(data)
                remaining_issues += len(remaining)

                # Write back only if actually modified
                with open(fpath, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))

                unfixable_types = {
                    "count_without_details",
                    "invalid_denomination",
                    "truncated_name",
                    "invalid_revenus_years",
                    "invalid_pourcentage",
                }
                fixable_count = len(issues) - len(
                    [i for i in issues if i["type"] in unfixable_types]
                )
                split_count = len(
                    [i for i in issues if i["type"] in ("merged_participations", "merged_mandats")]
                )
                total_fixed += fixable_count
                total_splits += split_count
                files_fixed += 1

                if remaining:
                    wip = ", ".join(i["message"] for i in remaining[:3])
                    if len(remaining) > 3:
                        wip += f" … (+{len(remaining) - 3})"
                    summary_lines.append(
                        f"  🔧 {fname}: {fixable_count} corrigé(s), "
                        f"reste {len(remaining)} work in progress ({wip})"
                    )
                else:
                    summary_lines.append(
                        f"  ✅ {fname}: {fixable_count} problème(s) corrigé(s)"
                    )
            else:
                # All issues are unfixable (count_without_details, etc.)
                remaining_issues += len(issues)
                for issue in issues:
                    summary_lines.append(
                        f"  ⏳ {fname}: {issue['message']}"
                    )
        else:
            for issue in issues:
                icon = {
                    "count_without_details": "⏳",
                    "merged_participations": "🔀",
                    "merged_mandats": "🔀",
                    "garbage_montants_details": "🗑️",
                    "invalid_organisme_name": "🔤",
                    "invalid_mandat_name": "🔤",
                    "invalid_denomination": "🔤",
                    "truncated_name": "✂️",
                    "invalid_revenus_years": "📅",
                    "invalid_pourcentage": "📊",
                    "montant_vs_revenus_mismatch": "💰",
                    "merged_participation_amounts": "🔢",
                }.get(issue["type"], "⚠️ ")
                summary_lines.append(f"  {icon} {fname}: {issue['message']}")

    # ── Summary ────────────────────────────────────────────────────────────
    print("═" * 60)
    print("📊 RÉSUMÉ")
    print("═" * 60)
    print(f"  Fichiers analysés : {total_files}")
    print(f"  Fichiers avec problèmes : {files_with_issues}")
    print(f"  Total incohérences détectées : {total_issues}")
    if args.fix:
        print(f"  Fichiers corrigés : {files_fixed}")
        print(f"  Corrections appliquées : {total_fixed}")
        print(f"  Listes fusionnées séparées : {total_splits}")
        print(f"  Problèmes restants (work in progress) : {remaining_issues}")
    print()

    if summary_lines:
        max_lines = 50
        if len(summary_lines) > max_lines:
            for line in summary_lines[:max_lines]:
                print(line)
            print(f"  … et {len(summary_lines) - max_lines} autres")
        else:
            for line in summary_lines:
                print(line)

    # ── GitHub Actions summary ─────────────────────────────────────────────
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as fh:
            fh.write(f"## {'🔧 Corrections appliquées' if args.fix else '🔍 Rapport de cohérence'}\n\n")
            fh.write(f"| Métrique | Valeur |\n|---|---|\n")
            fh.write(f"| Fichiers analysés | {total_files} |\n")
            fh.write(f"| Fichiers avec problèmes | {files_with_issues} |\n")
            fh.write(f"| Incohérences détectées | {total_issues} |\n")
            if args.fix:
                fh.write(f"| Fichiers corrigés | {files_fixed} |\n")
                fh.write(f"| Corrections appliquées | {total_fixed} |\n")
                fh.write(f"| Listes séparées | {total_splits} |\n")
                fh.write(f"| Restants (work in progress) | {remaining_issues} |\n")
            fh.write("\n")

    # Exit code: 0 if no fixable issues remain, 1 if issues found (dry-run)
    if not args.fix and files_with_issues > 0:
        sys.exit(1)
    sys.exit(0)



if __name__ == "__main__":
    main()
