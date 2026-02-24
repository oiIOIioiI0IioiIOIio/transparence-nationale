#!/usr/bin/env python3
"""
Script d'extraction COMPLÈTE des données HATVP des élus français.
Optimisé pour GitHub Actions et déploiement Vercel.

Extrait l'INTÉGRALITÉ des informations disponibles dans les déclarations HATVP :
  ✓ Instruments financiers (actions, obligations, ETF, PEA, assurance-vie)
  ✓ Participations financières (sociétés non cotées, SARL, SCI)
  ✓ Biens immobiliers (résidences, terrains, locaux commerciaux)
  ✓ Revenus et activités rémunérées
  ✓ Mandats électifs et fonctions
  ✓ Prêts bancaires et emprunts
  ✓ Autres biens (véhicules, œuvres d'art, bijoux)
  ✓ Informations familiales (conjoint, enfants)
  ✓ Observations et commentaires

Fonctionnalités :
  - Sauvegardes incrémentales tous les 100 élus
  - Évite les doublons (skip si déjà scraped, sauf --force)
  - Logs compatibles GitHub Actions
  - Structure optimisée pour Vercel (résumés séparés des détails)

Sources :
  Index CSV  : https://www.hatvp.fr/livraison/opendata/liste.csv
  XMLs       : https://www.hatvp.fr/livraison/dossiers/{fichier}.xml
  Doc        : https://www.data.gouv.fr/fr/datasets/declarations-des-elus/

Utilisation :
  python generate-elus-hatvp-complete.py --dry-run
  python generate-elus-hatvp-complete.py --limit 50
  python generate-elus-hatvp-complete.py --test-elu "Yaël Braun-Pivet"
  python generate-elus-hatvp-complete.py --force
  python generate-elus-hatvp-complete.py --skip-existing  # Skip élus déjà scrapés
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
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

# ── Chemins ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Pour GitHub Actions, détecter si on est dans un workflow
IS_GITHUB_ACTION = os.getenv("GITHUB_ACTIONS") == "true"

# Chemins adaptés pour GitHub Actions et Vercel
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")
CACHE_DIR = os.path.join(PROJECT_ROOT, "public", "data", "hatvp_cache")
DETAILS_DIR = os.path.join(CACHE_DIR, "details")  # Détails complets séparés
INDEX_CACHE = os.path.join(CACHE_DIR, "liste.csv")
PROGRESS_FILE = os.path.join(CACHE_DIR, "progress.json")  # Progression pour reprise

# Sauvegarde tous les N élus
SAVE_INTERVAL = 100

# ── URLs HATVP ─────────────────────────────────────────────────────────────────
HATVP_INDEX_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"
HATVP_XML_BASE = "https://www.hatvp.fr/livraison/dossiers/"

# ── Types de déclaration ───────────────────────────────────────────────────────
WANTED_TYPES = {"DSP", "DSPM", "DI", "DIM"}  # Situation Patrimoniale + Intérêts
DSP_TYPES = {"DSP", "DSPM"}  # Contiennent patrimoine et finances
DI_TYPES = {"DI", "DIM"}     # Contiennent intérêts et mandats

# ── Headers HTTP ───────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "TransparenceNationale/2.0 (github.com/oiIOIioiI0IioiIOIio/transparence-nationale)",
    "Accept": "text/csv, application/xml, text/xml, */*",
}


# ══════════════════════════════════════════════════════════════════════════════
# Arguments
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Extraction COMPLÈTE des données HATVP (patrimoine, revenus, mandats, famille)."
    )
    p.add_argument("--dry-run", action="store_true", help="Simulation sans écriture")
    p.add_argument("--force", action="store_true", help="Re-télécharger les XMLs même si en cache")
    p.add_argument("--skip-existing", action="store_true", help="Skip élus déjà scrapés (accélère le traitement)")
    p.add_argument("--limit", type=int, help="Limiter le nombre d'élus traités")
    p.add_argument("--delay", type=float, default=0.5, help="Délai entre requêtes (secondes)")
    p.add_argument("--test-elu", type=str, help="Tester un élu spécifique (ex: 'Yaël Braun-Pivet')")
    p.add_argument("--refresh-index", action="store_true", help="Re-télécharger l'index CSV")
    p.add_argument("--verbose", action="store_true", help="Affichage détaillé")
    return p.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
# Réseau
# ══════════════════════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 30) -> bytes | None:
    """Télécharger une URL avec gestion d'erreurs."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 403, 410):
            print(f"  ⚠ HTTP {exc.code} → {url}")
    except Exception as exc:
        print(f"  ⚠ Erreur réseau : {exc}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Logs GitHub Actions
# ══════════════════════════════════════════════════════════════════════════════

def github_log(message: str, level: str = "notice"):
    """Logger pour GitHub Actions."""
    if IS_GITHUB_ACTION:
        print(f"::{level}::{message}")
    else:
        print(message)


def github_group_start(title: str):
    """Démarrer un groupe collapsible dans GitHub Actions."""
    if IS_GITHUB_ACTION:
        print(f"::group::{title}")
    else:
        print(f"\n{'=' * 80}")
        print(title)
        print('=' * 80)


def github_group_end():
    """Terminer un groupe dans GitHub Actions."""
    if IS_GITHUB_ACTION:
        print("::endgroup::")


def github_set_output(name: str, value: Any):
    """Définir une output pour GitHub Actions."""
    if IS_GITHUB_ACTION:
        # GitHub Actions moderne (GITHUB_OUTPUT)
        github_output = os.getenv("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"{name}={value}\n")


# ══════════════════════════════════════════════════════════════════════════════
# Gestion de la progression (pour reprise en cas d'interruption)
# ══════════════════════════════════════════════════════════════════════════════

def load_progress() -> dict:
    """Charger la progression sauvegardée."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"processed": [], "last_save": None, "total_processed": 0}


def save_progress(progress: dict):
    """Sauvegarder la progression."""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def is_already_processed(elu_id: str, progress: dict) -> bool:
    """Vérifier si un élu a déjà été traité."""
    return elu_id in progress.get("processed", [])


# ══════════════════════════════════════════════════════════════════════════════
# Chargement index CSV
# ══════════════════════════════════════════════════════════════════════════════

def load_hatvp_index(force_refresh: bool = False, delay: float = 0.5) -> list[dict]:
    """Télécharger et parser le CSV index HATVP."""
    os.makedirs(CACHE_DIR, exist_ok=True)

    if not force_refresh and os.path.exists(INDEX_CACHE):
        age_h = (time.time() - os.path.getmtime(INDEX_CACHE)) / 3600
        if age_h < 24:
            print(f"  ✓ Index CSV en cache ({age_h:.1f}h)")
            with open(INDEX_CACHE, "rb") as f:
                raw = f.read()
        else:
            print(f"  ↻ Cache expiré ({age_h:.1f}h), re-téléchargement...")
            raw = None
    else:
        raw = None

    if raw is None:
        print(f"  🔄 Téléchargement : {HATVP_INDEX_URL}")
        time.sleep(delay)
        raw = http_get(HATVP_INDEX_URL)
        if not raw:
            raise RuntimeError(f"Impossible de télécharger l'index : {HATVP_INDEX_URL}")
        with open(INDEX_CACHE, "wb") as f:
            f.write(raw)
        print(f"  ✓ Index téléchargé ({len(raw):,} octets)")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    print(f"  ✓ {len(rows):,} déclarations dans l'index")
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# Correspondance élu ↔ déclarations
# ══════════════════════════════════════════════════════════════════════════════

def normalize_name(s: str) -> str:
    """Normaliser un nom : minuscules, sans accents, sans tirets."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[-\s]+", " ", s).strip()
    return s


def find_declarations_for_elu(index: list[dict], prenom: str, nom: str) -> list[dict]:
    """Retrouver toutes les déclarations d'un élu dans l'index."""
    norm_prenom = normalize_name(prenom)
    norm_nom = normalize_name(nom)

    matched = []
    for row in index:
        row_nom = (row.get("nom") or row.get("Nom") or row.get("nomDeclarant") or "").strip()
        row_prenom = (row.get("prenom") or row.get("Prenom") or row.get("prenomDeclarant") or "").strip()

        if not row_nom:
            continue

        if normalize_name(row_nom) == norm_nom and normalize_name(row_prenom) == norm_prenom:
            matched.append(row)

    # Tri par date décroissante
    def parse_date(row):
        date_str = (row.get("dateDepot") or row.get("DateDepot") or row.get("date_depot") or "")
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        return datetime.min

    matched.sort(key=parse_date, reverse=True)
    return matched


def get_xml_url(row: dict) -> str | None:
    """Extraire l'URL du XML depuis une ligne CSV."""
    url = (row.get("url") or row.get("Url") or row.get("urlFichier") or "").strip()
    if url.startswith("http"):
        return url

    fichier = (row.get("fichier") or row.get("Fichier") or row.get("nomFichier") or url).strip()
    if fichier:
        if not fichier.endswith(".xml"):
            fichier += ".xml"
        return HATVP_XML_BASE + fichier

    return None


def get_declaration_type(row: dict) -> str:
    """Extraire le type de déclaration."""
    return (row.get("typeDeclaration") or row.get("TypeDeclaration") or row.get("type") or "").strip().upper()


# ══════════════════════════════════════════════════════════════════════════════
# Téléchargement XML
# ══════════════════════════════════════════════════════════════════════════════

def download_xml(url: str, cache_path: str, force: bool = False, delay: float = 0.5) -> bytes | None:
    """Télécharger un XML avec cache."""
    if not force and os.path.exists(cache_path):
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
# Utilitaires XML
# ══════════════════════════════════════════════════════════════════════════════

def xml_text(element, path: str, default: str = "") -> str:
    """Extraire le texte d'un nœud XML."""
    if element is None:
        return default
    node = element.find(path)
    if node is not None and node.text:
        t = node.text.strip()
        if t and t != "[Données non publiées]":
            return t
    return default


def xml_bool(element, path: str) -> bool:
    """Extraire un booléen d'un nœud XML."""
    return xml_text(element, path).lower() == "true"


def parse_montant(s: str) -> float | None:
    """Convertir une chaîne montant en float."""
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def is_section_empty(element) -> bool:
    """Vérifier si une section est vide ou marquée 'neant'."""
    if element is None:
        return True
    neant = xml_text(element, "neant").lower()
    return neant == "true"


# ══════════════════════════════════════════════════════════════════════════════
# Parsers par section
# ══════════════════════════════════════════════════════════════════════════════

def parse_instruments_financiers(root: ET.Element) -> list[dict]:
    """
    Parser <instrumentsFinanciersDto> : actions cotées, obligations, ETF, PEA, assurance-vie.
    """
    section = root.find(".//instrumentsFinanciersDto")
    if is_section_empty(section):
        return []

    instruments = []
    for item in section.findall(".//items/items") or section.findall(".//items"):
        if not any(child.text for child in item):
            continue

        nature_id = xml_text(item, "nature/id") or xml_text(item, "typeInstrument/id") or ""
        nature_label = xml_text(item, "nature/label") or xml_text(item, "typeInstrument/label") or nature_id
        
        valeur_str = (
            xml_text(item, "valeur") or
            xml_text(item, "valeurEstimee") or
            xml_text(item, "montant") or
            xml_text(item, "valeurTotale") or ""
        )

        instrument = {
            "type": "instrument_financier",
            "nature": nature_label,
            "nature_code": nature_id,
            "description": (
                xml_text(item, "description") or
                xml_text(item, "denomination") or
                xml_text(item, "libelle") or
                xml_text(item, "nomEmetteur") or ""
            ),
            "valeur_euro": parse_montant(valeur_str),
            "mode_detention": (
                xml_text(item, "modeDetention/label") or
                xml_text(item, "modeDetention/id") or ""
            ),
            "nombre_titres": xml_text(item, "nombreTitres") or xml_text(item, "nbTitres") or "",
            "valeur_unitaire_euro": parse_montant(xml_text(item, "valeurUnitaire")),
            "isin": xml_text(item, "codeISIN") or xml_text(item, "isin") or "",
            "devise": xml_text(item, "devise") or xml_text(item, "devise/id") or "",
            "date_acquisition": xml_text(item, "dateAcquisition") or xml_text(item, "dateOuverture") or "",
            "etablissement": xml_text(item, "etablissement") or xml_text(item, "nomEtablissement") or "",
            "commentaire": xml_text(item, "commentaire") or xml_text(item, "observation") or "",
        }

        # Filtrer les entrées totalement vides
        if not instrument["nature"] and not instrument["description"] and instrument["valeur_euro"] is None:
            continue

        instruments.append(instrument)

    return instruments


def parse_participation_financiere(root: ET.Element) -> list[dict]:
    """
    Parser <participationFinanciereDto> : participations dans sociétés non cotées, SARL, SCI.
    """
    section = root.find(".//participationFinanciereDto")
    if is_section_empty(section):
        return []

    participations = []
    for item in section.findall(".//items/items") or section.findall(".//items"):
        if not any(child.text for child in item):
            continue

        nom_societe = (
            xml_text(item, "nomSociete") or
            xml_text(item, "denomination") or
            xml_text(item, "raisonSociale") or ""
        )
        
        valeur_str = (
            xml_text(item, "valeurParts") or
            xml_text(item, "valeur") or
            xml_text(item, "montant") or
            xml_text(item, "valeurEstimee") or ""
        )

        participation = {
            "type": "participation_financiere",
            "nom_societe": nom_societe,
            "forme_juridique": xml_text(item, "formeJuridique") or xml_text(item, "typeStructure/label") or "",
            "nb_parts": xml_text(item, "nbParts") or xml_text(item, "nombreParts") or "",
            "valeur_euro": parse_montant(valeur_str),
            "pourcentage_detention": xml_text(item, "pourcentage") or xml_text(item, "tauxDetention") or "",
            "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id") or "",
            "objet_social": xml_text(item, "objetSocial") or xml_text(item, "activite") or xml_text(item, "secteurActivite") or "",
            "adresse": xml_text(item, "adresse") or xml_text(item, "siege") or "",
            "siren": xml_text(item, "siren") or xml_text(item, "numeroSIREN") or "",
            "date_acquisition": xml_text(item, "dateAcquisition") or xml_text(item, "dateEntree") or "",
            "commentaire": xml_text(item, "commentaire") or xml_text(item, "observation") or "",
        }

        if not participation["nom_societe"] and participation["valeur_euro"] is None:
            continue

        participations.append(participation)

    return participations


def parse_biens_immobiliers(root: ET.Element) -> list[dict]:
    """
    Parser <biensImmobiliersDto> : résidences, terrains, locaux commerciaux.
    """
    section = root.find(".//biensImmobiliersDto")
    if is_section_empty(section):
        return []

    biens = []
    for item in section.findall(".//items/items") or section.findall(".//items"):
        if not any(child.text for child in item):
            continue

        nature = (
            xml_text(item, "nature/label") or
            xml_text(item, "nature/id") or
            xml_text(item, "typeBien/label") or ""
        )

        valeur_str = (
            xml_text(item, "valeur") or
            xml_text(item, "valeurEstimee") or
            xml_text(item, "montant") or ""
        )

        bien = {
            "type": "bien_immobilier",
            "nature": nature,
            "nature_code": xml_text(item, "nature/id") or xml_text(item, "typeBien/id") or "",
            "adresse": (
                xml_text(item, "adresse") or
                xml_text(item, "localisation") or
                xml_text(item, "commune") or ""
            ),
            "surface_m2": xml_text(item, "surface") or xml_text(item, "superficieM2") or "",
            "valeur_euro": parse_montant(valeur_str),
            "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id") or "",
            "date_acquisition": xml_text(item, "dateAcquisition") or xml_text(item, "dateAchat") or "",
            "mode_acquisition": (
                xml_text(item, "modeAcquisition/label") or
                xml_text(item, "modeAcquisition/id") or
                xml_text(item, "origine") or ""
            ),
            "usage": xml_text(item, "usage") or xml_text(item, "affectation") or "",
            "commentaire": xml_text(item, "commentaire") or xml_text(item, "observation") or "",
        }

        if not bien["nature"] and not bien["adresse"] and bien["valeur_euro"] is None:
            continue

        biens.append(bien)

    return biens


def parse_prets_bancaires(root: ET.Element) -> list[dict]:
    """
    Parser <pretsBancairesDto> : emprunts immobiliers et autres prêts.
    """
    section = root.find(".//pretsBancairesDto")
    if is_section_empty(section):
        return []

    prets = []
    for item in section.findall(".//items/items") or section.findall(".//items"):
        if not any(child.text for child in item):
            continue

        montant_str = (
            xml_text(item, "montant") or
            xml_text(item, "montantEmprunte") or
            xml_text(item, "capitalEmprunte") or ""
        )

        capital_restant_str = (
            xml_text(item, "capitalRestantDu") or
            xml_text(item, "montantRestant") or
            xml_text(item, "solde") or ""
        )

        pret = {
            "type": "pret_bancaire",
            "nature": (
                xml_text(item, "nature/label") or
                xml_text(item, "nature/id") or
                xml_text(item, "typeCredit/label") or ""
            ),
            "etablissement": (
                xml_text(item, "etablissement") or
                xml_text(item, "organisme") or
                xml_text(item, "preteur") or ""
            ),
            "montant_emprunte_euro": parse_montant(montant_str),
            "capital_restant_du_euro": parse_montant(capital_restant_str),
            "date_souscription": (
                xml_text(item, "dateSouscription") or
                xml_text(item, "dateEmprunt") or
                xml_text(item, "dateOuverture") or ""
            ),
            "duree_annees": xml_text(item, "duree") or xml_text(item, "dureeAnnees") or "",
            "taux_interet": xml_text(item, "tauxInteret") or xml_text(item, "taux") or "",
            "objet": (
                xml_text(item, "objet") or
                xml_text(item, "finalite") or
                xml_text(item, "motif") or ""
            ),
            "commentaire": xml_text(item, "commentaire") or xml_text(item, "observation") or "",
        }

        if pret["montant_emprunte_euro"] is None and pret["capital_restant_du_euro"] is None:
            continue

        prets.append(pret)

    return prets


def parse_autres_biens(root: ET.Element) -> list[dict]:
    """
    Parser <autresBiensDto> : véhicules, œuvres d'art, bijoux, meubles de valeur.
    """
    section = root.find(".//autresBiensDto")
    if is_section_empty(section):
        return []

    biens = []
    for item in section.findall(".//items/items") or section.findall(".//items"):
        if not any(child.text for child in item):
            continue

        valeur_str = (
            xml_text(item, "valeur") or
            xml_text(item, "valeurEstimee") or
            xml_text(item, "montant") or ""
        )

        bien = {
            "type": "autre_bien",
            "nature": (
                xml_text(item, "nature/label") or
                xml_text(item, "nature/id") or
                xml_text(item, "categorie/label") or ""
            ),
            "description": (
                xml_text(item, "description") or
                xml_text(item, "designation") or
                xml_text(item, "libelle") or ""
            ),
            "valeur_euro": parse_montant(valeur_str),
            "date_acquisition": xml_text(item, "dateAcquisition") or xml_text(item, "dateAchat") or "",
            "commentaire": xml_text(item, "commentaire") or xml_text(item, "observation") or "",
        }

        if not bien["nature"] and not bien["description"] and bien["valeur_euro"] is None:
            continue

        biens.append(bien)

    return biens


def parse_revenus_activites(root: ET.Element) -> list[dict]:
    """
    Parser revenus et activités rémunérées : <revenusDto>, <activitesRemunerees>.
    """
    revenus = []

    # Section revenusDto (revenus déclarés dans DSP)
    section_revenus = root.find(".//revenusDto")
    if not is_section_empty(section_revenus):
        for item in section_revenus.findall(".//items/items") or section_revenus.findall(".//items"):
            if not any(child.text for child in item):
                continue

            montant_str = (
                xml_text(item, "montant") or
                xml_text(item, "montantAnnuel") or
                xml_text(item, "revenusAnnuels") or ""
            )

            revenu = {
                "type": "revenu",
                "nature": (
                    xml_text(item, "nature/label") or
                    xml_text(item, "nature/id") or
                    xml_text(item, "typeRevenu/label") or ""
                ),
                "employeur": (
                    xml_text(item, "employeur") or
                    xml_text(item, "source") or
                    xml_text(item, "organisme") or ""
                ),
                "montant_annuel_euro": parse_montant(montant_str),
                "activite": xml_text(item, "activite") or xml_text(item, "fonction") or "",
                "date_debut": xml_text(item, "dateDebut") or xml_text(item, "depuis") or "",
                "date_fin": xml_text(item, "dateFin") or xml_text(item, "jusqua") or "",
                "commentaire": xml_text(item, "commentaire") or xml_text(item, "observation") or "",
            }

            if not revenu["nature"] and revenu["montant_annuel_euro"] is None:
                continue

            revenus.append(revenu)

    # Section activitesRemunerees (activités professionnelles dans DI)
    section_activites = root.find(".//activitesRemunerees")
    if not is_section_empty(section_activites):
        for item in section_activites.findall(".//items/items") or section_activites.findall(".//items"):
            if not any(child.text for child in item):
                continue

            montant_str = (
                xml_text(item, "montant") or
                xml_text(item, "remunerationAnnuelle") or
                xml_text(item, "revenuAnnuel") or ""
            )

            activite = {
                "type": "activite_remuneree",
                "nature": (
                    xml_text(item, "nature/label") or
                    xml_text(item, "nature/id") or
                    xml_text(item, "typeActivite/label") or ""
                ),
                "employeur": (
                    xml_text(item, "employeur") or
                    xml_text(item, "nomEmployeur") or
                    xml_text(item, "organisme") or ""
                ),
                "fonction": (
                    xml_text(item, "fonction") or
                    xml_text(item, "intitulePoste") or
                    xml_text(item, "activite") or ""
                ),
                "montant_annuel_euro": parse_montant(montant_str),
                "secteur_activite": xml_text(item, "secteurActivite") or xml_text(item, "domaine") or "",
                "date_debut": xml_text(item, "dateDebut") or xml_text(item, "depuis") or "",
                "date_fin": xml_text(item, "dateFin") or xml_text(item, "jusqua") or "",
                "commentaire": xml_text(item, "commentaire") or xml_text(item, "observation") or "",
            }

            if not activite["employeur"] and not activite["fonction"]:
                continue

            revenus.append(activite)

    return revenus


def parse_mandats_electifs(root: ET.Element) -> list[dict]:
    """
    Parser <mandatsElectifsDto> : mandats électifs exercés.
    """
    section = root.find(".//mandatsElectifsDto")
    if is_section_empty(section):
        return []

    mandats = []
    for item in section.findall(".//items/items") or section.findall(".//items"):
        if not any(child.text for child in item):
            continue

        mandat = {
            "type": "mandat_electif",
            "nature": (
                xml_text(item, "nature/label") or
                xml_text(item, "nature/id") or
                xml_text(item, "typeMandat/label") or ""
            ),
            "fonction": (
                xml_text(item, "fonction") or
                xml_text(item, "intituleFonction") or
                xml_text(item, "qualite") or ""
            ),
            "collectivite": (
                xml_text(item, "collectivite") or
                xml_text(item, "organe") or
                xml_text(item, "assemblee") or ""
            ),
            "circonscription": (
                xml_text(item, "circonscription") or
                xml_text(item, "territoire") or
                xml_text(item, "zone") or ""
            ),
            "date_debut": xml_text(item, "dateDebut") or xml_text(item, "depuis") or "",
            "date_fin": xml_text(item, "dateFin") or xml_text(item, "jusqua") or "",
            "en_cours": xml_bool(item, "enCours"),
            "commentaire": xml_text(item, "commentaire") or xml_text(item, "observation") or "",
        }

        if not mandat["nature"] and not mandat["fonction"]:
            continue

        mandats.append(mandat)

    return mandats


def parse_fonctions_dirigeantes(root: ET.Element) -> list[dict]:
    """
    Parser <fonctionsDto> ou <fonctionsDirigeantes> : fonctions de direction dans organismes publics/privés.
    """
    fonctions = []

    for section_name in [".//fonctionsDto", ".//fonctionsDirigeantes", ".//fonctionsBenevoles"]:
        section = root.find(section_name)
        if is_section_empty(section):
            continue

        for item in section.findall(".//items/items") or section.findall(".//items"):
            if not any(child.text for child in item):
                continue

            fonction = {
                "type": "fonction_dirigeante",
                "fonction": (
                    xml_text(item, "fonction") or
                    xml_text(item, "intituleFonction") or
                    xml_text(item, "titre") or ""
                ),
                "organisme": (
                    xml_text(item, "organisme") or
                    xml_text(item, "nomOrganisme") or
                    xml_text(item, "structure") or ""
                ),
                "nature_organisme": (
                    xml_text(item, "natureOrganisme/label") or
                    xml_text(item, "natureOrganisme/id") or
                    xml_text(item, "typeStructure/label") or ""
                ),
                "secteur_activite": (
                    xml_text(item, "secteurActivite") or
                    xml_text(item, "domaine") or
                    xml_text(item, "objet") or ""
                ),
                "remuneree": xml_bool(item, "remuneree"),
                "montant_annuel_euro": parse_montant(xml_text(item, "montant") or xml_text(item, "remuneration")),
                "date_debut": xml_text(item, "dateDebut") or xml_text(item, "depuis") or "",
                "date_fin": xml_text(item, "dateFin") or xml_text(item, "jusqua") or "",
                "en_cours": xml_bool(item, "enCours"),
                "commentaire": xml_text(item, "commentaire") or xml_text(item, "observation") or "",
            }

            if not fonction["fonction"] and not fonction["organisme"]:
                continue

            fonctions.append(fonction)

    return fonctions


def parse_informations_familiales(root: ET.Element) -> dict:
    """
    Parser informations familiales : conjoint, enfants.
    """
    famille = {
        "situation_familiale": "",
        "conjoint": {},
        "enfants": [],
    }

    # Situation familiale générale
    situation = xml_text(root, ".//situationFamiliale/label") or xml_text(root, ".//situationFamiliale/id")
    if situation:
        famille["situation_familiale"] = situation

    # Informations conjoint
    conjoint_section = root.find(".//conjoint")
    if conjoint_section is not None:
        famille["conjoint"] = {
            "nom": xml_text(conjoint_section, "nom"),
            "prenom": xml_text(conjoint_section, "prenom"),
            "profession": (
                xml_text(conjoint_section, "profession") or
                xml_text(conjoint_section, "activiteProfessionnelle") or ""
            ),
            "employeur": (
                xml_text(conjoint_section, "employeur") or
                xml_text(conjoint_section, "nomEmployeur") or ""
            ),
            "secteur_activite": xml_text(conjoint_section, "secteurActivite") or "",
        }

    # Enfants
    enfants_section = root.find(".//enfantsDto")
    if not is_section_empty(enfants_section):
        for item in enfants_section.findall(".//items/items") or enfants_section.findall(".//items"):
            if not any(child.text for child in item):
                continue

            enfant = {
                "date_naissance": xml_text(item, "dateNaissance") or xml_text(item, "anneeNaissance") or "",
                "a_charge": xml_bool(item, "aCharge"),
            }

            if enfant["date_naissance"]:
                famille["enfants"].append(enfant)

    return famille


def parse_observations(root: ET.Element) -> str:
    """
    Parser les observations générales de la déclaration.
    """
    observations = []
    
    for field in ["observations", "observationsGenerales", "commentaire", "precisions"]:
        obs = xml_text(root, f".//{field}")
        if obs:
            observations.append(obs)

    return " | ".join(observations) if observations else ""


# ══════════════════════════════════════════════════════════════════════════════
# Parser principal XML
# ══════════════════════════════════════════════════════════════════════════════

def parse_declaration_xml(xml_bytes: bytes, url: str, verbose: bool = False) -> dict:
    """
    Parser complet d'un XML HATVP.
    Extrait TOUTES les sections disponibles.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        print(f"    ⚠ XML invalide ({exc})")
        return {}

    # ── Métadonnées ────────────────────────────────────────────────────────────
    type_decl_id = xml_text(root, "general/typeDeclaration/id") or ""
    type_decl_label = xml_text(root, "general/typeDeclaration/label") or type_decl_id

    result = {
        "uuid": xml_text(root, "uuid"),
        "url_xml": url,
        "type_declaration": type_decl_id,
        "type_declaration_label": type_decl_label,
        "date_depot": xml_text(root, "dateDepot"),
        "declarant": {
            "nom": xml_text(root, "general/declarant/nom"),
            "prenom": xml_text(root, "general/declarant/prenom"),
            "qualite": xml_text(root, "general/qualiteDeclarant"),
            "organe": xml_text(root, "general/organe/labelOrgane"),
            "mandat": xml_text(root, "general/qualiteMandat/labelTypeMandat"),
        },
        # ── Données financières et patrimoniales ───────────────────────────────
        "instruments_financiers": parse_instruments_financiers(root),
        "participations_financieres": parse_participation_financiere(root),
        "biens_immobiliers": parse_biens_immobiliers(root),
        "prets_bancaires": parse_prets_bancaires(root),
        "autres_biens": parse_autres_biens(root),
        # ── Revenus et activités ───────────────────────────────────────────────
        "revenus_activites": parse_revenus_activites(root),
        # ── Mandats et fonctions ───────────────────────────────────────────────
        "mandats_electifs": parse_mandats_electifs(root),
        "fonctions_dirigeantes": parse_fonctions_dirigeantes(root),
        # ── Famille ────────────────────────────────────────────────────────────
        "famille": parse_informations_familiales(root),
        # ── Observations ───────────────────────────────────────────────────────
        "observations": parse_observations(root),
    }

    if verbose:
        print(f"    ✓ {len(result['instruments_financiers'])} instruments financiers")
        print(f"    ✓ {len(result['participations_financieres'])} participations")
        print(f"    ✓ {len(result['biens_immobiliers'])} biens immobiliers")
        print(f"    ✓ {len(result['prets_bancaires'])} prêts bancaires")
        print(f"    ✓ {len(result['autres_biens'])} autres biens")
        print(f"    ✓ {len(result['revenus_activites'])} revenus/activités")
        print(f"    ✓ {len(result['mandats_electifs'])} mandats électifs")
        print(f"    ✓ {len(result['fonctions_dirigeantes'])} fonctions dirigeantes")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Orchestration par élu
# ══════════════════════════════════════════════════════════════════════════════

def fetch_hatvp_complete_for_elu(
    elu: dict,
    index: list[dict],
    force: bool,
    dry_run: bool,
    delay: float,
    verbose: bool,
) -> dict | None:
    """
    Récupérer TOUTES les données HATVP pour un élu.
    """
    prenom = elu.get("prenom", "").strip()
    nom = elu.get("nom", "").strip()

    if not prenom or not nom:
        return None

    declarations_rows = find_declarations_for_elu(index, prenom, nom)
    if not declarations_rows:
        print(f"    ✗ Aucune déclaration trouvée")
        return None

    print(f"    ✓ {len(declarations_rows)} déclaration(s) trouvée(s)")

    # Prendre la DSP et DI les plus récentes
    dsp_row = next((r for r in declarations_rows if get_declaration_type(r) in DSP_TYPES), None)
    di_row = next((r for r in declarations_rows if get_declaration_type(r) in DI_TYPES), None)

    result = {
        "prenom": prenom,
        "nom": nom,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "declarations_trouvees": len(declarations_rows),
        # Consolidation de toutes les données
        "instruments_financiers": [],
        "participations_financieres": [],
        "biens_immobiliers": [],
        "prets_bancaires": [],
        "autres_biens": [],
        "revenus_activites": [],
        "mandats_electifs": [],
        "fonctions_dirigeantes": [],
        "famille": {},
        "observations": [],
        "declarations": [],
    }

    # Parser DSP et DI
    for row, label in [(dsp_row, "DSP"), (di_row, "DI")]:
        if row is None:
            continue

        xml_url = get_xml_url(row)
        if not xml_url:
            print(f"    ⚠ URL XML introuvable pour {label}")
            continue

        decl_type = get_declaration_type(row)
        date_depot = row.get("dateDepot") or "?"
        print(f"    🔄 {label} ({decl_type}, {date_depot})")

        if dry_run:
            print(f"    [dry-run] Simulation : {xml_url}")
            result["declarations"].append({"type": decl_type, "url": xml_url, "dry_run": True})
            continue

        filename = xml_url.split("/")[-1]
        cache_path = os.path.join(CACHE_DIR, "xmls", filename)

        xml_bytes = download_xml(xml_url, cache_path, force=force, delay=delay)
        if not xml_bytes:
            print(f"    ✗ Téléchargement échoué")
            continue

        parsed = parse_declaration_xml(xml_bytes, xml_url, verbose=verbose)
        if not parsed:
            continue

        # Consolider toutes les sections
        result["instruments_financiers"].extend(parsed.get("instruments_financiers", []))
        result["participations_financieres"].extend(parsed.get("participations_financieres", []))
        result["biens_immobiliers"].extend(parsed.get("biens_immobiliers", []))
        result["prets_bancaires"].extend(parsed.get("prets_bancaires", []))
        result["autres_biens"].extend(parsed.get("autres_biens", []))
        result["revenus_activites"].extend(parsed.get("revenus_activites", []))
        result["mandats_electifs"].extend(parsed.get("mandats_electifs", []))
        result["fonctions_dirigeantes"].extend(parsed.get("fonctions_dirigeantes", []))

        # Fusionner famille (DI peut avoir plus d'infos)
        if parsed.get("famille"):
            if not result["famille"]:
                result["famille"] = parsed["famille"]
            else:
                # Fusionner les infos conjoint et enfants
                if parsed["famille"].get("conjoint"):
                    result["famille"]["conjoint"] = parsed["famille"]["conjoint"]
                if parsed["famille"].get("enfants"):
                    result["famille"]["enfants"].extend(parsed["famille"]["enfants"])

        # Observations
        if parsed.get("observations"):
            result["observations"].append(parsed["observations"])

        # Métadonnées de la déclaration
        result["declarations"].append({
            "type": parsed["type_declaration"],
            "label": parsed["type_declaration_label"],
            "date_depot": parsed["date_depot"],
            "uuid": parsed["uuid"],
            "url": xml_url,
            "declarant": parsed["declarant"],
        })

    return result


def build_resume_complet(data: dict) -> dict:
    """Construire un résumé statistique complet."""
    instruments = data.get("instruments_financiers", [])
    participations = data.get("participations_financieres", [])
    immobilier = data.get("biens_immobiliers", [])
    prets = data.get("prets_bancaires", [])
    autres_biens = data.get("autres_biens", [])
    revenus = data.get("revenus_activites", [])

    # Calculs valeurs totales
    valeur_instruments = sum(i.get("valeur_euro", 0) or 0 for i in instruments)
    valeur_participations = sum(p.get("valeur_euro", 0) or 0 for p in participations)
    valeur_immobilier = sum(b.get("valeur_euro", 0) or 0 for b in immobilier)
    valeur_autres_biens = sum(b.get("valeur_euro", 0) or 0 for b in autres_biens)
    
    total_dettes = sum(p.get("capital_restant_du_euro", 0) or 0 for p in prets)
    
    revenus_annuels = sum(r.get("montant_annuel_euro", 0) or 0 for r in revenus)

    patrimoine_brut = valeur_instruments + valeur_participations + valeur_immobilier + valeur_autres_biens
    patrimoine_net = patrimoine_brut - total_dettes

    return {
        # Comptages
        "nb_instruments_financiers": len(instruments),
        "nb_participations_societes": len(participations),
        "nb_biens_immobiliers": len(immobilier),
        "nb_prets_bancaires": len(prets),
        "nb_autres_biens": len(autres_biens),
        "nb_revenus_activites": len(revenus),
        "nb_mandats_electifs": len(data.get("mandats_electifs", [])),
        "nb_fonctions_dirigeantes": len(data.get("fonctions_dirigeantes", [])),
        # Valeurs financières
        "patrimoine_brut_euro": round(patrimoine_brut, 2),
        "patrimoine_net_euro": round(patrimoine_net, 2),
        "valeur_instruments_euro": round(valeur_instruments, 2),
        "valeur_participations_euro": round(valeur_participations, 2),
        "valeur_immobilier_euro": round(valeur_immobilier, 2),
        "valeur_autres_biens_euro": round(valeur_autres_biens, 2),
        "total_dettes_euro": round(total_dettes, 2),
        "revenus_annuels_euro": round(revenus_annuels, 2),
        # Métadonnées
        "nb_declarations_hatvp": data.get("declarations_trouvees", 0),
        "hatvp_scraped_at": data.get("scraped_at", ""),
        "a_conjoint": bool(data.get("famille", {}).get("conjoint", {}).get("nom")),
        "nb_enfants": len(data.get("famille", {}).get("enfants", [])),
    }


# ══════════════════════════════════════════════════════════════════════════════
# I/O elus.json avec gestion incrémentale
# ══════════════════════════════════════════════════════════════════════════════

def load_elus() -> list[dict]:
    """Charger elus.json."""
    if not os.path.exists(OUTPUT_JSON):
        print(f"⚠ {OUTPUT_JSON} introuvable")
        return []
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def save_elus(elus: list[dict], backup: bool = True) -> None:
    """
    Sauvegarder elus.json avec backup optionnel.
    
    Args:
        elus: Liste des élus à sauvegarder
        backup: Si True, crée une backup avant d'écraser
    """
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    
    # Backup de l'ancien fichier
    if backup and os.path.exists(OUTPUT_JSON):
        backup_path = OUTPUT_JSON + ".backup"
        try:
            with open(OUTPUT_JSON, "r") as src:
                with open(backup_path, "w") as dst:
                    dst.write(src.read())
        except Exception as e:
            print(f"⚠ Impossible de créer le backup : {e}")
    
    # Sauvegarder le nouveau fichier
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(elus, f, ensure_ascii=False, indent=2)
    
    github_log(f"✓ {OUTPUT_JSON} mis à jour ({len(elus)} élus)")


def update_elu_in_list(elus: list[dict], elu_id: str, hatvp_data: dict) -> list[dict]:
    """
    Mettre à jour un élu dans la liste avec ses données HATVP.
    Évite les doublons en mettant à jour l'élu existant.
    
    Args:
        elus: Liste des élus
        elu_id: ID de l'élu à mettre à jour
        hatvp_data: Données HATVP à ajouter (résumé)
    
    Returns:
        Liste des élus mise à jour
    """
    for elu in elus:
        if elu.get("id") == elu_id:
            elu["hatvp_complete"] = hatvp_data
            return elus
    
    # Si l'élu n'existe pas encore (ne devrait pas arriver en temps normal)
    print(f"⚠ Élu {elu_id} non trouvé dans elus.json")
    return elus


def save_incremental(elus: list[dict], count: int, total: int):
    """
    Sauvegarde incrémentale tous les SAVE_INTERVAL élus.
    
    Args:
        elus: Liste des élus
        count: Nombre d'élus traités
        total: Nombre total d'élus
    """
    if count % SAVE_INTERVAL == 0:
        github_group_start(f"💾 Sauvegarde incrémentale ({count}/{total})")
        save_elus(elus, backup=False)  # Pas de backup pour les sauvegardes incrémentales
        github_log(f"Progression : {count}/{total} élus traités ({count*100//total}%)")
        github_group_end()


def has_hatvp_data(elu: dict, skip_existing: bool) -> bool:
    """
    Vérifier si un élu a déjà des données HATVP.
    
    Args:
        elu: Dictionnaire de l'élu
        skip_existing: Si True, retourne True pour les élus déjà scrapés
    
    Returns:
        True si l'élu a déjà des données HATVP et qu'on doit le skip
    """
    if not skip_existing:
        return False
    
    hatvp = elu.get("hatvp_complete")
    if not hatvp:
        return False
    
    # Vérifier que les données ne sont pas vides
    scraped_at = hatvp.get("hatvp_scraped_at")
    if not scraped_at:
        return False
    
    # Vérifier que ce n'est pas trop ancien (plus de 90 jours)
    try:
        scraped_date = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        age_days = (datetime.now(scraped_date.tzinfo) - scraped_date).days
        if age_days > 90:
            return False  # Re-scraper si trop ancien
    except Exception:
        pass
    
    return True


def find_elu_by_name(elus: list[dict], query: str) -> dict | None:
    """Trouver un élu par son nom."""
    q = query.lower()
    for e in elus:
        full = f"{e.get('prenom', '')} {e.get('nom', '')}".lower()
        if q in full:
            return e
    return None


def save_detailed_data(elu_id: str, data: dict, dry_run: bool = False):
    """
    Sauvegarder les données détaillées d'un élu dans un fichier séparé.
    Optimisation pour Vercel : séparer les gros fichiers des résumés.
    
    Args:
        elu_id: ID de l'élu
        data: Données complètes à sauvegarder
        dry_run: Si True, ne sauvegarde pas
    """
    if dry_run:
        return
    
    os.makedirs(DETAILS_DIR, exist_ok=True)
    detail_path = os.path.join(DETAILS_DIR, f"{elu_id}.json")
    
    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    # ── Header ─────────────────────────────────────────────────────────────────
    if not IS_GITHUB_ACTION:
        print("=" * 80)
        print("💰 EXTRACTION COMPLÈTE HATVP — PATRIMOINE, REVENUS, MANDATS, FAMILLE")
        print("   Source : https://www.hatvp.fr/livraison/opendata/")
        if args.dry_run:
            print("   ⚠ MODE DRY-RUN — aucune écriture de fichiers")
        if args.verbose:
            print("   📢 MODE VERBOSE activé")
        if args.skip_existing:
            print("   ⏭️  SKIP EXISTING activé — élus déjà scrapés ignorés")
        print("=" * 80)

    # Créer les répertoires nécessaires
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.join(CACHE_DIR, "xmls"), exist_ok=True)
    os.makedirs(DETAILS_DIR, exist_ok=True)

    # ── Charger index ──────────────────────────────────────────────────────────
    github_group_start("📥 Chargement index HATVP")
    try:
        index = load_hatvp_index(force_refresh=args.refresh_index, delay=args.delay)
    except RuntimeError as exc:
        github_log(f"❌ {exc}", "error")
        github_group_end()
        sys.exit(1)
    github_group_end()

    # ── Mode test ──────────────────────────────────────────────────────────────
    if args.test_elu:
        github_group_start(f"🧪 MODE TEST — Élu : {args.test_elu}")

        elus = load_elus()
        elu = find_elu_by_name(elus, args.test_elu)
        if not elu:
            parts = args.test_elu.strip().split()
            elu = {"id": "test", "prenom": parts[0], "nom": " ".join(parts[1:])}

        print(f"  Profil : {elu.get('prenom')} {elu.get('nom')}")

        result = fetch_hatvp_complete_for_elu(
            elu, index,
            force=True,
            dry_run=args.dry_run,
            delay=args.delay,
            verbose=args.verbose,
        )

        if result:
            print(f"\n{'=' * 80}")
            print("✅ RÉSULTAT COMPLET")
            print(f"{'=' * 80}")

            # Afficher résumé
            resume = build_resume_complet(result)
            print(f"\n📊 RÉSUMÉ :")
            print(f"  Patrimoine brut    : {resume['patrimoine_brut_euro']:>15,.0f} €")
            print(f"  Dettes             : {resume['total_dettes_euro']:>15,.0f} €")
            print(f"  Patrimoine net     : {resume['patrimoine_net_euro']:>15,.0f} €")
            print(f"  Revenus annuels    : {resume['revenus_annuels_euro']:>15,.0f} €")
            print(f"\n  📈 Instruments financiers  : {resume['nb_instruments_financiers']}")
            print(f"  🏢 Participations sociétés : {resume['nb_participations_societes']}")
            print(f"  🏠 Biens immobiliers       : {resume['nb_biens_immobiliers']}")
            print(f"  💳 Prêts bancaires         : {resume['nb_prets_bancaires']}")
            print(f"  🎨 Autres biens            : {resume['nb_autres_biens']}")
            print(f"  💼 Revenus/Activités       : {resume['nb_revenus_activites']}")
            print(f"  🗳️  Mandats électifs        : {resume['nb_mandats_electifs']}")
            print(f"  👔 Fonctions dirigeantes   : {resume['nb_fonctions_dirigeantes']}")
            
            if resume['a_conjoint']:
                print(f"  👫 Conjoint                : Oui")
            if resume['nb_enfants']:
                print(f"  👶 Enfants                 : {resume['nb_enfants']}")

            # Sauvegarder les détails
            if not args.dry_run:
                save_detailed_data(elu.get('id', 'test'), result, dry_run=False)
                detail_path = os.path.join(DETAILS_DIR, f"{elu.get('id', 'test')}.json")
                print(f"\n  💾 Détails sauvegardés : {detail_path}")

            # Exemples de données
            if result["instruments_financiers"] and args.verbose:
                print(f"\n  📈 INSTRUMENTS FINANCIERS (extrait) :")
                for i in result["instruments_financiers"][:3]:
                    val = f"{i['valeur_euro']:,.0f} €" if i.get("valeur_euro") else "?"
                    print(f"    • {i.get('nature', '?'):20s} | {i.get('description', '?')[:40]:40s} | {val}")

            if result["biens_immobiliers"] and args.verbose:
                print(f"\n  🏠 BIENS IMMOBILIERS (extrait) :")
                for b in result["biens_immobiliers"][:3]:
                    val = f"{b['valeur_euro']:,.0f} €" if b.get("valeur_euro") else "?"
                    print(f"    • {b.get('nature', '?'):20s} | {b.get('adresse', '?')[:40]:40s} | {val}")

            if result["revenus_activites"] and args.verbose:
                print(f"\n  💼 REVENUS & ACTIVITÉS (extrait) :")
                for r in result["revenus_activites"][:3]:
                    val = f"{r['montant_annuel_euro']:,.0f} €/an" if r.get("montant_annuel_euro") else "?"
                    print(f"    • {r.get('employeur', '?')[:30]:30s} | {r.get('nature', '?'):20s} | {val}")

        else:
            print("  ✗ Aucune donnée récupérée")
        
        github_group_end()
        return

    # ── Mode batch ─────────────────────────────────────────────────────────────
    github_group_start("📋 Chargement des élus")
    elus = load_elus()
    if not elus:
        github_log("⚠ elus.json vide. Utilisez --test-elu pour tester.", "warning")
        github_group_end()
        return

    if args.limit:
        elus = elus[:args.limit]
        github_log(f"Limite appliquée : {args.limit} élus")
    
    github_log(f"Total à traiter : {len(elus)} élus")
    github_group_end()

    # Charger la progression
    progress = load_progress()
    
    # Compteurs
    total = len(elus)
    processed = 0
    skipped = 0
    not_found = 0
    updated = 0
    errors = 0

    # ── Traitement batch ───────────────────────────────────────────────────────
    github_group_start(f"🔄 Traitement des {total} élus")
    
    start_time = time.time()
    
    for i, elu in enumerate(elus, 1):
        prenom = elu.get("prenom", "")
        nom = elu.get("nom", "")
        elu_id = elu.get("id", f"elu-{i}")
        
        # Affichage avec pourcentage
        pct = (i * 100) // total
        prefix = f"[{i}/{total}] ({pct}%)"
        
        if not IS_GITHUB_ACTION:
            print(f"\n{prefix} {prenom} {nom}")
        
        # ── Skip si déjà traité ────────────────────────────────────────────────
        if has_hatvp_data(elu, args.skip_existing):
            skipped += 1
            if args.verbose:
                github_log(f"{prefix} {prenom} {nom} — ⏭️  Déjà scraped, skip")
            continue
        
        # ── Traitement ─────────────────────────────────────────────────────────
        try:
            result = fetch_hatvp_complete_for_elu(
                elu, index,
                force=args.force,
                dry_run=args.dry_run,
                delay=args.delay,
                verbose=args.verbose,
            )

            if result is None:
                not_found += 1
                if args.verbose:
                    github_log(f"{prefix} {prenom} {nom} — ✗ Non trouvé dans HATVP")
                continue

            # Construire le résumé
            resume = build_resume_complet(result)
            
            # Mettre à jour l'élu dans la liste (sans doublons)
            elus = update_elu_in_list(elus, elu_id, resume)
            
            # Sauvegarder les détails complets séparément
            save_detailed_data(elu_id, result, args.dry_run)
            
            updated += 1
            processed += 1
            
            # Log de progression
            if not args.dry_run:
                patrimoine = resume.get('patrimoine_net_euro', 0)
                revenus = resume.get('revenus_annuels_euro', 0)
                github_log(
                    f"{prefix} {prenom} {nom} — ✓ "
                    f"Patrimoine: {patrimoine:,.0f}€ | Revenus: {revenus:,.0f}€/an"
                )
            
            # ── Sauvegarde incrémentale tous les SAVE_INTERVAL ────────────────
            if not args.dry_run and processed % SAVE_INTERVAL == 0:
                save_incremental(elus, processed, total)
                
                # Mettre à jour la progression
                progress["total_processed"] = processed
                progress["last_save"] = datetime.utcnow().isoformat() + "Z"
                save_progress(progress)
        
        except Exception as e:
            errors += 1
            github_log(f"{prefix} {prenom} {nom} — ❌ Erreur : {e}", "error")
            if args.verbose:
                import traceback
                traceback.print_exc()
            continue

    github_group_end()

    # ── Sauvegarde finale ──────────────────────────────────────────────────────
    if not args.dry_run and updated > 0:
        github_group_start("💾 Sauvegarde finale")
        save_elus(elus, backup=True)  # Sauvegarde finale avec backup
        
        # Mettre à jour la progression
        progress["total_processed"] = processed
        progress["last_save"] = datetime.utcnow().isoformat() + "Z"
        save_progress(progress)
        
        github_group_end()

    # ── Rapport final ──────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    elapsed_min = int(elapsed / 60)
    elapsed_sec = int(elapsed % 60)
    
    github_group_start("📊 RAPPORT FINAL")
    print(f"  Total élus             : {total}")
    print(f"  ✓ Traités avec succès  : {updated}")
    print(f"  ⏭️  Skipped (déjà scrapés): {skipped}")
    print(f"  ✗ Non trouvés HATVP    : {not_found}")
    print(f"  ❌ Erreurs             : {errors}")
    print(f"  ⏱️  Temps total          : {elapsed_min}m {elapsed_sec}s")
    print(f"  📁 Détails dans        : {DETAILS_DIR}/")
    github_group_end()
    
    # ── Outputs GitHub Actions ─────────────────────────────────────────────────
    github_set_output("total_processed", processed)
    github_set_output("total_updated", updated)
    github_set_output("total_skipped", skipped)
    github_set_output("total_errors", errors)
    
    # Exit code basé sur le succès
    if errors > total // 2:  # Plus de 50% d'erreurs
        github_log("❌ Trop d'erreurs lors du scraping", "error")
        sys.exit(1)


if __name__ == "__main__":
    main()
