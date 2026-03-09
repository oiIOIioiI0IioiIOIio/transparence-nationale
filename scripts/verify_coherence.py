#!/usr/bin/env python3
"""
Vérification et correction de cohérence des fichiers JSON individuels.

Agent minimaliste :
  1. Scanne chaque {id}.json dans public/data/elus/
  2. Détecte les incohérences (nb_* ≠ len(details_*), doublons, etc.)
  3. Corrige **uniquement** les erreurs avérées, ne reformate rien
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
      - fix: callable(hatvp) or None
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
        # (computed after dedup so we can fix both in one pass)
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

    # Pass 2: fix nb_* counts to match actual len(details_*)
    for nb_key, det_key in NB_TO_DETAILS.items():
        det_val = hatvp.get(det_key)
        if isinstance(det_val, list):
            actual_len = len(det_val)
            if hatvp.get(nb_key) != actual_len:
                hatvp[nb_key] = actual_len
                modified = True

    # Pass 3: count_without_details — cannot invent data, leave as-is
    # The count stays, details remain absent → logged as "work in progress"

    return modified


# ══════════════════════════════════════════════════════════════════════════════
# Re-verification
# ══════════════════════════════════════════════════════════════════════════════

def verify_after_fix(data: dict) -> list[dict]:
    """Re-check after fixes. Should return only unfixable issues."""
    return [i for i in check_elu(data) if i["type"] == "count_without_details"]


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

                fixable_count = len(issues) - len(
                    [i for i in issues if i["type"] == "count_without_details"]
                )
                total_fixed += fixable_count
                files_fixed += 1

                if remaining:
                    wip = ", ".join(i["message"] for i in remaining)
                    summary_lines.append(
                        f"  🔧 {fname}: {fixable_count} corrigé(s), "
                        f"reste {len(remaining)} work in progress ({wip})"
                    )
                else:
                    summary_lines.append(
                        f"  ✅ {fname}: {fixable_count} problème(s) corrigé(s)"
                    )
            else:
                # All issues are unfixable (count_without_details)
                remaining_issues += len(issues)
                for issue in issues:
                    summary_lines.append(
                        f"  ⏳ {fname}: {issue['message']}"
                    )
        else:
            for issue in issues:
                summary_lines.append(f"  {'⚠️ ' if issue['type'] != 'count_without_details' else '⏳'} {fname}: {issue['message']}")

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
        print(f"  Problèmes restants (work in progress) : {remaining_issues}")
    print()

    if summary_lines:
        # In CI, limit output to first 50 lines + summary
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
                fh.write(f"| Restants (work in progress) | {remaining_issues} |\n")
            fh.write("\n")

    # Exit code: 0 if no fixable issues remain, 1 if issues found (dry-run)
    if not args.fix and files_with_issues > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
