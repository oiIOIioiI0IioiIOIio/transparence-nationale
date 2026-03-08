#!/usr/bin/env python3
"""
Script de récupération des déclarations HATVP complètes des élus français.

Télécharge le fichier XML unique HATVP (declarations.xml) contenant TOUTES
les déclarations publiées, puis extrait récursivement TOUTES les informations
de chaque déclaration pour chaque élu présent dans elus.json.

Sections extraites (DSP — patrimoine) :
  - biens immobiliers, comptes bancaires, instruments financiers
  - participations financières, véhicules, biens mobiliers de valeur
  - dettes/emprunts, revenus
Sections extraites (DI — intérêts) :
  - activités professionnelles, activités antérieures, mandats électifs
  - participations dans des organes, fonctions bénévoles
  - autres liens d'intérêts

Sources :
  Index CSV     : https://www.hatvp.fr/livraison/opendata/liste.csv
  XML (toutes)  : https://www.hatvp.fr/livraison/opendata/declarations.xml
  Doc officielle: https://www.hatvp.fr/open-data/

Utilisation :
  python generate-elus.py --dry-run
  python generate-elus.py --limit 50
  python generate-elus.py --test-elu "Yaël Braun-Pivet"
  python generate-elus.py --force
  python generate-elus.py --dump-xml-sample   # affiche un XML brut pour debug
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
from datetime import datetime, timezone
from progress import BatchProgress

# ── Chemins ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_JSON  = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")
ELUS_DETAIL_DIR = os.path.join(PROJECT_ROOT, "public", "data", "elus")
CACHE_DIR    = os.path.join(PROJECT_ROOT, "public", "data", "hatvp_cache")
INDEX_CACHE  = os.path.join(CACHE_DIR, "liste.csv")
XML_CACHE    = os.path.join(CACHE_DIR, "declarations.xml")
PROGRESS_JSON = os.path.join(PROJECT_ROOT, "public", "data", "progress.json")

# ── URLs HATVP open data ───────────────────────────────────────────────────────
HATVP_INDEX_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"

# Le XML unique contenant TOUTES les déclarations — plusieurs URLs possibles
# URL principale (merge) : contient l'intégralité des déclarations
HATVP_DECLARATIONS_XML_URLS = [
    "https://www.hatvp.fr/livraison/merge/declarations.xml",
    "https://www.data.gouv.fr/api/1/datasets/r/247995fb-3b98-48fd-95a4-2607c8a1de74",
    "https://www.hatvp.fr/livraison/opendata/declarations.xml",
]

# XMLs individuels via la colonne open_data du CSV
HATVP_OPENDATA_BASE = "https://www.hatvp.fr/livraison/opendata/"

# Fallback : XMLs individuels par nom_fichier (colonne du CSV)
HATVP_DOSSIER_BASE = "https://www.hatvp.fr/livraison/dossiers/"

# ── Colonnes réelles du CSV HATVP (notice officielle) ─────────────────────────
# civilite;prenom;nom;classement;type_mandat;qualite;type_document;departement;
# date_publication;nom_fichier;url_dossier;id_origine;url_photo
#
# type_document : DI, DSP, DSPFIN, DIMAJ, etc.
# nom_fichier   : nom du PDF (souvent aussi base du XML)
# url_dossier   : slug URL vers la page de la déclaration

# Types de déclaration à extraire
# DSP  = Déclaration de Situation Patrimoniale (patrimoine)
# DSPM = DSP de modification
# DSPFM = DSP de fin de mandat
# DSPFIN = DSP (ancien format)
# DI   = Déclaration d'Intérêts (ancien format)
# DIM  = DI de modification
# DIA  = Déclaration d'Intérêts et d'Activités (nouveau format depuis 2017)
# DIAM = DIA de modification
DSP_TYPES = {"DSP", "DSPM", "DSPFIN", "DSPMAJ", "DSPFM"}
DI_TYPES  = {"DI", "DIM", "DIMAJ", "DIA", "DIAM"}
ALL_DOC_TYPES = DSP_TYPES | DI_TYPES

# ── Headers HTTP ──────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (open source; github.com/transparence-nationale)",
    "Accept": "text/csv, application/xml, text/xml, */*",
}


# ══════════════════════════════════════════════════════════════════════════════
# Parsing args
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Extrait le patrimoine complet (DSP + DI) depuis les XMLs HATVP."
    )
    p.add_argument("--dry-run",          action="store_true", help="Ne pas écrire de fichiers")
    p.add_argument("--force",            action="store_true", help="Re-télécharger même si en cache")
    p.add_argument("--limit",            type=int,   default=None, help="Limiter le nombre d'élus")
    p.add_argument("--delay",            type=float, default=0.3,  help="Délai entre requêtes (défaut 0.3 s)")
    p.add_argument("--test-elu",         type=str,   default=None, help="Tester un élu précis")
    p.add_argument("--refresh-index",    action="store_true",
                   help="Forcer le re-téléchargement du CSV index HATVP")
    p.add_argument("--refresh-xml",      action="store_true",
                   help="Forcer le re-téléchargement du XML complet HATVP")
    p.add_argument("--dump-xml-sample",  action="store_true",
                   help="Afficher un extrait du XML brut (debug)")
    p.add_argument("--dump-csv-columns", action="store_true",
                   help="Afficher les colonnes du CSV index (debug)")
    p.add_argument("--with-pdf",         action="store_true",
                   help="Use PDF parser as fallback when XML yields no patrimoine data")
    p.add_argument("--no-ocr",           action="store_true",
                   help="Disable OCR in PDF parsing (faster)")
    p.add_argument("--enrich-csv-only",  action="store_true",
                   help="Enrichir elus.json depuis le CSV local (sans télécharger de XMLs)")
    p.add_argument("--split-elus",       action="store_true",
                   help="Générer les fichiers JSON par personne (public/data/elus/{id}.json) depuis elus.json")
    p.add_argument("--reorganize",       action="store_true",
                   help="Réorganiser les données: fichiers individuels complets + elus.json allégé pour la liste")
    p.add_argument("--save-every",       type=int, default=100,
                   help="Sauvegarder les fichiers individuels tous les N élus (défaut 100)")
    return p.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
# Réseau
# ══════════════════════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 120) -> bytes | None:
    """Télécharger une URL. Timeout élevé pour le gros XML (~200 Mo)."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 403, 410):
            print(f"  ⚠ HTTP {exc.code} → {url}")
    except Exception as exc:
        print(f"  ⚠ Réseau : {exc}")
    return None


def download_file(url: str, cache_path: str, force: bool = False,
                  max_age_h: float = 24, delay: float = 0.3) -> bytes | None:
    """Télécharger un fichier avec cache local."""
    if not force and os.path.exists(cache_path):
        age_h = (time.time() - os.path.getmtime(cache_path)) / 3600
        if age_h < max_age_h:
            print(f"  ✓ En cache ({age_h:.1f} h) : {os.path.basename(cache_path)}")
            with open(cache_path, "rb") as f:
                return f.read()
        else:
            print(f"  ↻ Cache trop ancien ({age_h:.1f} h), re-téléchargement…")

    time.sleep(delay)
    print(f"  🔄 Téléchargement : {url}")
    data = http_get(url)
    if data:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(data)
        print(f"  ✓ Téléchargé ({len(data):,} octets) → {cache_path}")
    return data


# ══════════════════════════════════════════════════════════════════════════════
# Helpers XML génériques
# ══════════════════════════════════════════════════════════════════════════════

def xml_text(element: ET.Element | None, path: str, default: str = "") -> str:
    """Extraire le texte d'un nœud XML en toute sécurité."""
    if element is None:
        return default
    node = element.find(path)
    if node is not None and node.text:
        t = node.text.strip()
        if t and t not in ("[Données non publiées]", "null"):
            return t
    return default


def parse_montant(s: str) -> float | None:
    """Convertir une chaîne montant en float."""
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def normalize_name(s: str) -> str:
    """Normaliser un nom : minuscules, sans accents, sans tirets."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[-\s]+", " ", s).strip()
    return s


def element_to_dict(el: ET.Element) -> dict:
    """
    Convertir récursivement un élément XML en dict.
    Si un élément a des enfants, on récurse. Sinon, on prend le texte.
    Gère les listes (<items>) et les sous-objets (<nature><id>X</id></nature>).
    """
    result = {}
    children = list(el)
    if not children:
        # Feuille : retourner le texte
        t = (el.text or "").strip()
        if t and t != "[Données non publiées]":
            return t
        return ""

    for child in children:
        tag = child.tag
        value = element_to_dict(child)

        if tag == "items":
            # Accumuler les <items> dans une liste
            result.setdefault("_items", [])
            if isinstance(value, dict) and "_items" in value:
                # items imbriqués : <items><items>...</items></items>
                result["_items"].extend(value["_items"])
            elif value:  # Ignorer les vides
                result["_items"].append(value)
        elif tag in result:
            # Doublon (rare) : convertir en liste
            existing = result[tag]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[tag] = [existing, value]
        else:
            result[tag] = value

    return result


def flatten_section_items(section_dict: dict) -> list[dict]:
    """Extraire la liste d'items d'une section parsée récursivement."""
    if not isinstance(section_dict, dict):
        return []
    # Vérifier neant
    neant = section_dict.get("neant", "")
    if isinstance(neant, str) and neant.lower() == "true":
        return []
    items = section_dict.get("_items", [])
    # Filtrer les items qui sont des dicts non vides
    result = []
    for item in items:
        if isinstance(item, dict):
            # Aplatir les sous-objets (nature/id → nature_id, nature/label → nature_label)
            flat = flatten_item(item)
            if flat and any(v for v in flat.values() if v):
                result.append(flat)
    return result


def flatten_item(d: dict, prefix: str = "") -> dict:
    """
    Aplatir un dict imbriqué.
    {nature: {id: "X", label: "Y"}} → {nature_id: "X", nature_label: "Y"}
    """
    result = {}
    for k, v in d.items():
        if k == "_items":
            continue  # Ignorer les sous-listes imbriquées
        key = f"{prefix}{k}" if not prefix else f"{prefix}_{k}"
        if isinstance(v, dict):
            # Sous-objet (ex: nature/id, modeDetention/label)
            if "id" in v or "label" in v:
                if v.get("id"):
                    result[f"{key}_id"] = v["id"]
                if v.get("label"):
                    result[f"{key}_label"] = v["label"]
                # Garder aussi la valeur combinée
                result[key] = v.get("label") or v.get("id") or ""
            else:
                # Récurser
                sub = flatten_item(v, key)
                result.update(sub)
        elif isinstance(v, list):
            # Multiple valeurs (rare)
            result[key] = "; ".join(str(x) for x in v if x)
        else:
            result[key] = v if v else ""
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Chargement de l'index CSV HATVP
# ══════════════════════════════════════════════════════════════════════════════

def load_hatvp_index(force_refresh: bool = False, delay: float = 0.3) -> list[dict]:
    """Télécharger et parser le CSV index HATVP."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    raw = download_file(HATVP_INDEX_URL, INDEX_CACHE, force=force_refresh, delay=delay)
    if not raw:
        raise RuntimeError(f"Impossible de télécharger l'index HATVP : {HATVP_INDEX_URL}")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    if rows:
        print(f"  ✓ {len(rows):,} entrées — colonnes : {list(rows[0].keys())}")
    else:
        print("  ⚠ CSV vide")
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# Chargement du XML complet HATVP (declarations.xml)
# ══════════════════════════════════════════════════════════════════════════════

def load_declarations_xml(force_refresh: bool = False, delay: float = 0.3) -> ET.Element | None:
    """
    Télécharger et parser le XML unique contenant TOUTES les déclarations HATVP.
    Essaie plusieurs URLs dans l'ordre (merge, data.gouv.fr, opendata).
    Retourne l'élément racine.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Essayer le cache d'abord
    raw = None
    if not force_refresh and os.path.exists(XML_CACHE):
        age_h = (time.time() - os.path.getmtime(XML_CACHE)) / 3600
        if age_h < 48:
            print(f"  ✓ En cache ({age_h:.1f} h) : {os.path.basename(XML_CACHE)}")
            with open(XML_CACHE, "rb") as f:
                raw = f.read()

    # Si pas en cache, essayer les URLs dans l'ordre
    if not raw:
        for url in HATVP_DECLARATIONS_XML_URLS:
            print(f"  🔄 Tentative : {url}")
            time.sleep(delay)
            data = http_get(url, timeout=300)
            if data and len(data) > 1000:
                raw = data
                # Sauvegarder en cache
                with open(XML_CACHE, "wb") as f:
                    f.write(raw)
                print(f"  ✓ Téléchargé ({len(raw):,} octets) depuis {url}")
                break
            else:
                print(f"  ✗ Échec ou réponse trop courte depuis {url}")

    if not raw:
        print("  ⚠ Impossible de télécharger le XML complet depuis aucune URL")
        return None

    print(f"  📖 Parsing du XML ({len(raw):,} octets)…")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        print(f"  ❌ XML invalide : {exc}")
        return None

    # Compter les déclarations
    declarations = root.findall(".//declaration")
    if not declarations:
        # Essayer d'autres structures possibles
        declarations = list(root)
    print(f"  ✓ {len(declarations)} déclaration(s) dans le XML")
    return root


def build_xml_index(root: ET.Element) -> dict[str, list[ET.Element]]:
    """
    Construire un index {nom_normalisé -> [éléments déclaration]} depuis le XML.
    Permet une recherche rapide par nom d'élu.
    """
    index = {}

    # Le XML peut avoir plusieurs structures. Essayons :
    # <declarations><declaration>...</declaration></declarations>
    # ou directement les enfants du root sont des déclarations
    declarations = root.findall(".//declaration")
    if not declarations:
        declarations = list(root)

    for decl in declarations:
        # Extraire nom/prénom du déclarant
        nom    = xml_text(decl, ".//general/declarant/nom") or xml_text(decl, ".//declarant/nom") or xml_text(decl, ".//nom") or ""
        prenom = xml_text(decl, ".//general/declarant/prenom") or xml_text(decl, ".//declarant/prenom") or xml_text(decl, ".//prenom") or ""

        if not nom:
            continue

        key = normalize_name(f"{prenom} {nom}")
        index.setdefault(key, []).append(decl)

    print(f"  ✓ Index XML : {len(index)} personnes distinctes")
    return index


# ══════════════════════════════════════════════════════════════════════════════
# Index CSV : correspondance élu ↔ déclarations
# ══════════════════════════════════════════════════════════════════════════════

def find_csv_rows_for_elu(csv_index: list[dict], prenom: str, nom: str) -> list[dict]:
    """Retrouver les entrées CSV pour un élu (par nom normalisé)."""
    norm_prenom = normalize_name(prenom)
    norm_nom    = normalize_name(nom)
    matched = []
    for row in csv_index:
        r_nom    = normalize_name(row.get("nom", ""))
        r_prenom = normalize_name(row.get("prenom", ""))
        if r_nom == norm_nom and r_prenom == norm_prenom:
            matched.append(row)
    # Tri par date de publication (plus récent en premier)
    def sort_key(row):
        d = row.get("date_publication", "")
        try:
            return datetime.strptime(d.strip(), "%Y-%m-%d")
        except (ValueError, AttributeError):
            return datetime.min
    matched.sort(key=sort_key, reverse=True)
    return matched


def get_individual_xml_url(csv_row: dict) -> str | None:
    """
    Construire l'URL d'un XML individuel depuis une ligne CSV.
    Priorité 1 : colonne 'open_data' (contient directement le nom du fichier XML)
    Priorité 2 : colonne 'nom_fichier' (PDF) → remplacer .pdf par .xml
    """
    # Priorité 1 : open_data (fiable, c'est directement le XML)
    open_data = (csv_row.get("open_data") or "").strip()
    if open_data:
        return HATVP_OPENDATA_BASE + open_data

    # Priorité 2 : nom_fichier (PDF → XML, moins fiable)
    nom_fichier = (csv_row.get("nom_fichier") or "").strip()
    if nom_fichier:
        base = nom_fichier.rsplit(".", 1)[0] if "." in nom_fichier else nom_fichier
        return HATVP_OPENDATA_BASE + base + ".xml"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Extraction récursive complète d'une déclaration XML
# ══════════════════════════════════════════════════════════════════════════════

# Sections connues du XML HATVP et leur catégorie
# Basé sur opendata-structure.xlsx (feuilles PATRIMOINE et INTERETS)
KNOWN_SECTIONS = {
    # ── DSP — Patrimoine (feuille PATRIMOINE du xlsx) ─────────────────────────
    # Biens immobiliers
    "immeubleDto":                  "biens_immobiliers",
    "biensImmobiliersDto":          "biens_immobiliers",
    "bienImmobilierDto":            "biens_immobiliers",
    # Parts de SCI
    "sciDto":                       "parts_sci",
    # Comptes bancaires
    "comptesBancaireDto":           "comptes_bancaires",
    "comptesBancairesDto":          "comptes_bancaires",
    "compteBancaireDto":            "comptes_bancaires",
    "liquiditesDto":                "comptes_bancaires",
    # Assurances vie
    "assuranceVieDto":              "assurances_vie",
    # Valeurs mobilières en bourse
    "valeursEnBourseDto":           "valeurs_bourse",
    # Valeurs non cotées en bourse
    "valeursNonEnBourseDto":        "valeurs_non_bourse",
    # Instruments financiers (ancien format)
    "instrumentsFinanciersDto":     "instruments_financiers",
    # Participations financières
    "participationFinanciereDto":   "participations_financieres",
    "participationFinancieresDto":  "participations_financieres",
    # Fonds
    "fondDto":                      "fonds",
    # Biens divers
    "bienDiverDto":                 "biens_divers",
    # Autres biens
    "autreBienDto":                 "autres_biens",
    "autresBiensDto":               "autres_biens",
    # Biens à l'étranger
    "bienEtrangerDto":              "biens_etrangers",
    # Véhicules
    "vehiculeDto":                  "vehicules",
    "vehiculesDto":                 "vehicules",
    # Passif (dettes/emprunts)
    "passifDto":                    "dettes",
    "dettesDto":                    "dettes",
    "detteDto":                     "dettes",
    "empruntsDto":                  "dettes",
    # Revenus / mandats
    "revenuMandatDto":              "revenus",
    "revenusDto":                   "revenus",
    "revenuDto":                    "revenus",
    "revenusActiviteDto":           "revenus",
    # Événements majeurs
    "evenementMajeurDto":           "evenements_majeurs",
    # Observations patrimoine
    "observationPatrimoineDto":     "observations_patrimoine",
    # Biens mobiliers de valeur
    "biensMobiliersDto":            "biens_mobiliers_valeur",
    "biensValeurDto":               "biens_mobiliers_valeur",
    # ── DI — Intérêts (feuille INTERETS du xlsx) ─────────────────────────────
    # Activités de consultant
    "activConsultantDto":           "activites_consultant",
    # Activités professionnelles (5 dernières années)
    "activProfCinqDerniereDto":     "activites_professionnelles",
    "activitesProfessionnellesDto": "activites_professionnelles",
    "activiteProfessionnelleDto":   "activites_professionnelles",
    "fonctionsActuellesDto":        "activites_professionnelles",
    # Mandats électifs
    "mandatElectifDto":             "mandats_electifs",
    "mandatsElectifsDto":           "mandats_electifs",
    "mandatsDto":                   "mandats_electifs",
    # Participations en tant que dirigeant
    "participationDirigeantDto":    "participations_organes",
    "participationsOrganeDto":      "participations_organes",
    "participationOrganeDto":       "participations_organes",
    "organesDirigeantsDto":         "participations_organes",
    # Fonctions bénévoles
    "fonctionBenevoleDto":          "fonctions_benevoles",
    "fonctionsBenevolesDto":        "fonctions_benevoles",
    "soutiensAssociationsDto":      "fonctions_benevoles",
    "soutienAssociationDto":        "fonctions_benevoles",
    "activitesBenevolesDto":        "fonctions_benevoles",
    # Activités professionnelles du conjoint
    "activProfConjointDto":         "activites_conjoint",
    # Activités des collaborateurs
    "activCollaborateursDto":       "activites_collaborateurs",
    # Observations intérêts
    "observationInteretDto":        "observations_interets",
    # Activités antérieures
    "activitesAnterieuresDto":      "activites_anterieures",
    "activiteAnterieureDto":        "activites_anterieures",
    "fonctionsAnterieuresDto":      "activites_anterieures",
    # Autres liens d'intérêts
    "autresLiensInteretsDto":       "autres_liens_interets",
    "autreLienInteretDto":          "autres_liens_interets",
    "liensInteretsDto":             "autres_liens_interets",
    # Autres activités
    "autresActivitesDto":           "autres_activites",
    "autreActiviteDto":             "autres_activites",
    # Fonctions gouvernementales
    "fonctionsGouvernementalesDto":  "fonctions_gouvernementales",
    # Fonctions consultatives
    "consultatifEtAutresDto":        "fonctions_consultatives",
    # Participations exploitant
    "participationExploitantDto":    "participations_exploitant",
}

ALL_OUTPUT_SECTIONS = sorted(set(KNOWN_SECTIONS.values()))

SECTION_LABELS = {
    "biens_immobiliers":            "🏠 Biens immobiliers",
    "parts_sci":                    "🏗️  Parts de SCI",
    "comptes_bancaires":            "🏦 Comptes bancaires & épargne",
    "assurances_vie":               "🛡️  Assurances vie",
    "valeurs_bourse":               "📈 Valeurs mobilières cotées",
    "valeurs_non_bourse":           "📊 Valeurs non cotées",
    "instruments_financiers":       "📈 Instruments financiers",
    "participations_financieres":   "🏢 Participations dans des sociétés",
    "fonds":                        "💰 Fonds",
    "biens_divers":                 "🎨 Biens divers",
    "autres_biens":                 "📦 Autres biens",
    "biens_etrangers":              "🌍 Biens à l'étranger",
    "vehicules":                    "🚗 Véhicules",
    "biens_mobiliers_valeur":       "💎 Biens mobiliers de valeur",
    "dettes":                       "📉 Dettes & emprunts",
    "revenus":                      "💶 Revenus",
    "evenements_majeurs":           "⚡ Événements majeurs",
    "observations_patrimoine":      "📝 Observations patrimoine",
    "activites_consultant":         "🔍 Activités de consultant",
    "activites_professionnelles":   "💼 Activités professionnelles",
    "activites_anterieures":        "📋 Activités antérieures",
    "mandats_electifs":             "🗳️  Mandats électifs",
    "participations_organes":       "🏛️  Participations à des organes",
    "fonctions_benevoles":          "🤝 Fonctions bénévoles",
    "activites_conjoint":           "👥 Activités du conjoint",
    "activites_collaborateurs":     "👤 Activités des collaborateurs",
    "observations_interets":        "📝 Observations intérêts",
    "autres_liens_interets":        "⚠️  Autres liens d'intérêts",
    "autres_activites":             "📝 Autres activités",
    "fonctions_gouvernementales":   "🏛️  Fonctions gouvernementales",
    "fonctions_consultatives":      "📋 Fonctions consultatives",
    "participations_exploitant":    "🏭 Participations exploitant",
}


# Financial field names used for deduplication (not part of the identity of an item)
_FINANCIAL_DEDUP_FIELDS = {
    "valeur_euro", "solde_euro", "montant_euro", "valeur", "solde", "montant",
    "valeurParts", "capitalRestantDu", "remuneration_euro", "indemnite_euro",
    "valeurVenale", "prixAcquisition", "valeurDeclaree", "valeurEstimee",
    "montantAnnuel", "montantTotal", "montantBrut", "montantNet",
}


def _item_dedup_key(item: dict) -> str:
    """Build a deduplication key from an item's non-financial string fields."""
    parts = []
    for k, v in sorted(item.items()):
        if k in _FINANCIAL_DEDUP_FIELDS or k.startswith("_"):
            continue
        if v is None or v == "":
            continue
        parts.append(f"{k}:{str(v).strip().lower()}")
    return "|".join(parts)


def deduplicate_section_items(items: list[dict]) -> list[dict]:
    """Remove duplicate items from a section, keeping the one with the highest financial value."""
    if not items or len(items) <= 1:
        return items
    seen: dict[str, dict] = {}
    for item in items:
        key = _item_dedup_key(item)
        if not key:
            # Items with no identifying fields — keep all
            seen[f"__empty_{len(seen)}"] = item
            continue
        existing = seen.get(key)
        if existing is None:
            seen[key] = item
        else:
            # Keep the one with a higher financial value
            def _max_fin(d: dict) -> float:
                mx = 0.0
                for f in _FINANCIAL_DEDUP_FIELDS:
                    v = d.get(f)
                    if isinstance(v, (int, float)):
                        mx = max(mx, abs(v))
                return mx
            if _max_fin(item) > _max_fin(existing):
                seen[key] = item
    return list(seen.values())


def extract_declaration_data(decl_element: ET.Element) -> dict:
    """
    Extraire TOUTES les données d'un élément <declaration> XML
    en parcourant récursivement toutes les sections.
    """
    result = {
        # Métadonnées
        "type_declaration":       xml_text(decl_element, ".//general/typeDeclaration/id") or xml_text(decl_element, "typeDeclaration/id") or "",
        "type_declaration_label": xml_text(decl_element, ".//general/typeDeclaration/label") or xml_text(decl_element, "typeDeclaration/label") or "",
        "date_depot":             xml_text(decl_element, "dateDepot") or xml_text(decl_element, ".//dateDepot") or "",
        "date_publication":       xml_text(decl_element, "datePublication") or "",
        "uuid":                   xml_text(decl_element, "uuid") or xml_text(decl_element, ".//uuid") or "",
        "declarant_nom":          xml_text(decl_element, ".//general/declarant/nom") or xml_text(decl_element, ".//declarant/nom") or "",
        "declarant_prenom":       xml_text(decl_element, ".//general/declarant/prenom") or xml_text(decl_element, ".//declarant/prenom") or "",
        "qualite":                xml_text(decl_element, ".//general/qualiteDeclarant") or xml_text(decl_element, ".//qualite") or "",
        "organe":                 xml_text(decl_element, ".//general/organe/labelOrgane") or xml_text(decl_element, ".//organe") or "",
        "mandat":                 xml_text(decl_element, ".//general/qualiteMandat/labelTypeMandat") or "",
    }

    # Initialiser toutes les sections connues
    for section_name in ALL_OUTPUT_SECTIONS:
        result[section_name] = []

    # Parcourir TOUS les enfants (et descendants) de la déclaration
    # pour trouver les sections connues
    for section_tag, output_key in KNOWN_SECTIONS.items():
        for section_el in decl_element.iter(section_tag):
            parsed = element_to_dict(section_el)
            items = flatten_section_items(parsed)
            result[output_key].extend(items)

    # FALLBACK : parcourir aussi récursivement pour trouver des sections
    # qu'on n'a pas dans notre mapping mais qui contiennent des items
    seen_tags = set(KNOWN_SECTIONS.keys()) | {"general", "uuid", "dateDepot",
                "datePublication", "declaration", "declarations"}
    for child in decl_element:
        tag = child.tag
        if tag in seen_tags:
            continue
        # Vérifier si cette section contient des items
        if child.find("items") is not None or child.find(".//items") is not None:
            parsed = element_to_dict(child)
            items = flatten_section_items(parsed)
            if items:
                # Stocker dans "autres_activites" par défaut
                safe_key = re.sub(r"Dto$", "", tag)
                safe_key = re.sub(r"([A-Z])", r"_\1", safe_key).lower().strip("_")
                # Utiliser la section existante la plus proche ou créer
                if safe_key not in result:
                    result[safe_key] = []
                    # L'ajouter aussi aux sections connues pour l'affichage
                    if safe_key not in ALL_OUTPUT_SECTIONS:
                        ALL_OUTPUT_SECTIONS.append(safe_key)
                result[safe_key].extend(items)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Orchestration par élu
# ══════════════════════════════════════════════════════════════════════════════

def fetch_data_for_elu(
    elu: dict,
    xml_index: dict[str, list[ET.Element]],
    csv_index: list[dict],
    force: bool,
    dry_run: bool,
    delay: float,
) -> dict | None:
    """
    Extraire TOUTES les données HATVP d'un élu.
    Cherche d'abord dans le XML global, sinon tente les XMLs individuels.
    """
    prenom = elu.get("prenom", "").strip()
    nom    = elu.get("nom",    "").strip()
    if not prenom or not nom:
        return None

    result = {
        "prenom":                prenom,
        "nom":                   nom,
        "scraped_at":            datetime.now(timezone.utc).isoformat(),
        "declarations_trouvees": 0,
        "declarations":          [],
    }
    for section_name in ALL_OUTPUT_SECTIONS:
        result[section_name] = []

    # ── Stratégie 1 : chercher dans le XML global ─────────────────────────────
    key = normalize_name(f"{prenom} {nom}")
    xml_decls = xml_index.get(key, [])

    if xml_decls:
        result["declarations_trouvees"] = len(xml_decls)
        print(f"    ✓ {len(xml_decls)} déclaration(s) dans le XML global")

        for decl_el in xml_decls:
            if dry_run:
                result["declarations"].append({"source": "xml_global", "dry_run": True})
                continue

            parsed = extract_declaration_data(decl_el)

            # Fusionner les sections
            for section_name in list(set(ALL_OUTPUT_SECTIONS) | set(parsed.keys())):
                if section_name in (
                    "type_declaration", "type_declaration_label", "date_depot",
                    "date_publication", "uuid", "declarant_nom", "declarant_prenom",
                    "qualite", "organe", "mandat",
                ):
                    continue
                items = parsed.get(section_name, [])
                if isinstance(items, list):
                    if section_name not in result:
                        result[section_name] = []
                    result[section_name].extend(items)

            result["declarations"].append({
                "source":     "xml_global",
                "type":       parsed.get("type_declaration", ""),
                "label":      parsed.get("type_declaration_label", ""),
                "date_depot": parsed.get("date_depot", ""),
                "uuid":       parsed.get("uuid", ""),
                "qualite":    parsed.get("qualite", ""),
                "organe":     parsed.get("organe", ""),
            })

        # Deduplicate items across declarations
        for section_name in list(result.keys()):
            if isinstance(result.get(section_name), list) and section_name not in ("declarations",):
                result[section_name] = deduplicate_section_items(result[section_name])

        return result

    # ── Stratégie 2 : XMLs individuels via le CSV ─────────────────────────────
    csv_rows = find_csv_rows_for_elu(csv_index, prenom, nom)
    if not csv_rows:
        print(f"    ✗ Aucune déclaration HATVP trouvée pour {prenom} {nom}")
        return None

    result["declarations_trouvees"] = len(csv_rows)
    print(f"    ✓ {len(csv_rows)} entrée(s) CSV — fallback XMLs individuels")

    # Prendre les plus récentes : 1 DSP + 1 DI
    fetched_types = set()
    for csv_row in csv_rows:
        doc_type = (csv_row.get("type_document") or "").strip().upper()
        if doc_type not in ALL_DOC_TYPES:
            continue
        # Éviter les doublons de même catégorie
        category = "DSP" if doc_type in DSP_TYPES else "DI"
        if category in fetched_types:
            continue

        xml_url = get_individual_xml_url(csv_row)
        if not xml_url:
            continue

        print(f"    🔄 {doc_type} : {xml_url}")

        if dry_run:
            result["declarations"].append({"source": "xml_individuel", "type": doc_type, "url": xml_url, "dry_run": True})
            fetched_types.add(category)
            continue

        filename   = xml_url.split("/")[-1]
        cache_path = os.path.join(CACHE_DIR, "xmls", filename)
        xml_bytes  = download_file(xml_url, cache_path, force=force, max_age_h=168, delay=delay)

        if not xml_bytes:
            print(f"    ✗ Impossible de télécharger {xml_url}")
            continue

        try:
            decl_root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            print(f"    ⚠ XML invalide ({exc})")
            continue

        parsed = extract_declaration_data(decl_root)

        for section_name in list(set(ALL_OUTPUT_SECTIONS) | set(parsed.keys())):
            if section_name in (
                "type_declaration", "type_declaration_label", "date_depot",
                "date_publication", "uuid", "declarant_nom", "declarant_prenom",
                "qualite", "organe", "mandat",
            ):
                continue
            items = parsed.get(section_name, [])
            if isinstance(items, list):
                if section_name not in result:
                    result[section_name] = []
                result[section_name].extend(items)

        result["declarations"].append({
            "source":     "xml_individuel",
            "type":       parsed.get("type_declaration", ""),
            "label":      parsed.get("type_declaration_label", ""),
            "date_depot": parsed.get("date_depot", ""),
            "uuid":       parsed.get("uuid", ""),
            "url":        xml_url,
            "qualite":    parsed.get("qualite", ""),
            "organe":     parsed.get("organe", ""),
        })
        fetched_types.add(category)

    # Deduplicate items across declarations
    for section_name in list(result.keys()):
        if isinstance(result.get(section_name), list) and section_name not in ("declarations",):
            result[section_name] = deduplicate_section_items(result[section_name])

    return result


# Noms des champs financiers à chercher dans les items XML pour calculer les totaux
FINANCIAL_FIELD_NAMES = (
    "valeur_euro", "solde_euro", "montant_euro",
    "valeur", "solde", "montant", "valeurParts",
    "capitalRestantDu", "remuneration_euro", "indemnite_euro",
    "valeurVenale", "prixAcquisition", "valeurDeclaree",
    "valeurEstimee", "montantAnnuel", "montantTotal",
    "montantBrut", "montantNet",
)


def build_resume_hatvp(data: dict) -> dict:
    """Construire un résumé compact pour elus.json."""

    # Cap detail lists to keep elus.json payload manageable (~6 MB total)
    MAX_DETAIL_ITEMS = 20

    def count_and_total(items: list[dict]) -> tuple[int, float]:
        n = len(items)
        total = 0.0
        for i in items:
            for k in FINANCIAL_FIELD_NAMES:
                v = i.get(k)
                if v is not None:
                    if isinstance(v, str):
                        v = parse_montant(v)
                    if isinstance(v, (int, float)):
                        total += v
                        break
        return n, total

    def _first_financial(item: dict):
        """Return the first numeric financial value found in an item."""
        for k in FINANCIAL_FIELD_NAMES:
            v = item.get(k)
            if v is not None:
                if isinstance(v, str):
                    v = parse_montant(v)
                if isinstance(v, (int, float)):
                    return v
        return None

    def _compact(d: dict) -> dict:
        """Remove keys with empty/None values to keep output compact."""
        return {k: v for k, v in d.items() if v not in (None, "", 0, 0.0)}

    def _extract_details_activites(items: list[dict]) -> list[dict]:
        details = []
        for item in items[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("employeur") or "",
                "remuneration": _first_financial(item),
                "fonction": item.get("fonction") or item.get("fonction_label") or item.get("activite") or item.get("activite_label") or "",
            })
            me = item.get("montant_euro")
            if me and isinstance(me, (int, float)):
                d["montant_euro"] = me
            ra = item.get("revenus_annuels")
            if ra and isinstance(ra, list) and len(ra) > 0:
                d["revenus_annuels"] = ra
            if d:
                details.append(d)
        return details

    def _extract_details_mandats(items: list[dict]) -> list[dict]:
        details = []
        for item in items[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "mandat": item.get("mandat") or item.get("mandat_label") or item.get("typeMandat") or item.get("typeMandat_label") or "",
                "organisme": item.get("organisme") or item.get("organisme_label") or item.get("collectivite") or item.get("collectivite_label") or "",
                "remuneration": _first_financial(item),
            })
            me = item.get("montant_euro")
            if me and isinstance(me, (int, float)):
                d["montant_euro"] = me
            ra = item.get("revenus_annuels")
            if ra and isinstance(ra, list) and len(ra) > 0:
                d["revenus_annuels"] = ra
            if d:
                details.append(d)
        return details

    def _extract_details_participations(items: list[dict]) -> list[dict]:
        details = []
        for item in items[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("designation") or "",
                "type": item.get("nature") or item.get("nature_label") or item.get("type") or item.get("type_label") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        return details

    def _extract_details_revenus(items: list[dict]) -> list[dict]:
        details = []
        for item in items[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "type": item.get("type_revenu") or item.get("nature") or item.get("nature_label") or item.get("description") or "",
                "organisme": item.get("organisme") or item.get("organisme_label") or item.get("denomination") or item.get("employeur") or "",
                "montant": _first_financial(item),
            })
            if d:
                details.append(d)
        return details

    resume = {
        "nb_declarations_hatvp": data.get("declarations_trouvees", 0),
        "hatvp_scraped_at":      data.get("scraped_at", ""),
    }

    patrimoine_brut = 0.0
    total_dettes    = 0.0
    total_revenus   = 0.0

    for section_name in ALL_OUTPUT_SECTIONS:
        items = data.get(section_name, [])
        if not items:
            continue
        n, total = count_and_total(items)
        resume[f"nb_{section_name}"] = n
        if total:
            resume[f"valeur_{section_name}_euro"] = total

        # Calculer patrimoine net
        if section_name == "dettes":
            total_dettes += total
        elif section_name == "revenus":
            total_revenus += total
        elif section_name not in (
            "activites_professionnelles", "activites_anterieures",
            "activites_consultant", "activites_conjoint",
            "activites_collaborateurs",
            "mandats_electifs", "participations_organes",
            "fonctions_benevoles", "autres_liens_interets",
            "autres_activites", "fonctions_gouvernementales",
            "fonctions_consultatives", "observations_patrimoine",
            "observations_interets", "evenements_majeurs",
        ):
            patrimoine_brut += total

    if patrimoine_brut or total_dettes:
        resume["total_actif_brut_euro"] = patrimoine_brut
        resume["total_dettes_euro"]     = total_dettes
        resume["patrimoine_net_euro"]   = patrimoine_brut - total_dettes
    if total_revenus:
        resume["total_revenus_euro"] = total_revenus

    # ── Detailed item lists ──────────────────────────────────────────────────

    # Activités professionnelles
    activites = data.get("activites_professionnelles", [])
    if activites:
        details = _extract_details_activites(activites)
        if details:
            resume["details_activites"] = details

    # Mandats électifs
    mandats = data.get("mandats_electifs", [])
    if mandats:
        details = _extract_details_mandats(mandats)
        if details:
            resume["details_mandats"] = details

    # Participations (financières + organes dirigeants)
    participations = (
        data.get("participations_financieres", [])
        + data.get("participations_organes", [])
    )
    if participations:
        details = _extract_details_participations(participations)
        if details:
            resume["details_participations"] = details

    # Revenus
    revenus = data.get("revenus", [])
    if revenus:
        details = _extract_details_revenus(revenus)
        if details:
            resume["details_revenus"] = details

    # ── NEW: biens immobiliers ────────────────────────────────────────────
    biens_immo = data.get("biens_immobiliers", [])
    if biens_immo:
        details = []
        for item in biens_immo[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "description": item.get("description") or item.get("description_label") or "",
                "nature": item.get("nature") or item.get("nature_label") or item.get("typeBien") or item.get("typeBien_label") or "",
                "lieu": item.get("lieu") or item.get("localisation") or item.get("commune") or item.get("commune_label") or item.get("adresse") or "",
                "departement": item.get("departement") or item.get("departement_label") or item.get("codeDepartement") or "",
                "surface": item.get("surface") or item.get("surfaceBien") or "",
                "mode_acquisition": item.get("modeAcquisition") or item.get("modeAcquisition_label") or item.get("modeDetention") or item.get("modeDetention_label") or "",
                "date_acquisition": item.get("dateAcquisition") or item.get("anneeAcquisition") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_biens_immobiliers"] = details

    # ── NEW: comptes bancaires ────────────────────────────────────────────
    comptes = data.get("comptes_bancaires", [])
    if comptes:
        details = []
        for item in comptes[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "etablissement": item.get("etablissement") or item.get("banque") or item.get("nomEtablissement") or item.get("organisme") or "",
                "type_compte": item.get("nature") or item.get("nature_label") or item.get("typeCompte") or item.get("typeCompte_label") or "",
                "description": item.get("description") or "",
                "solde": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_comptes_bancaires"] = details

    # ── NEW: valeurs en bourse (actions cotées) ───────────────────────────
    bourse = data.get("valeurs_bourse", [])
    if bourse:
        details = []
        for item in bourse[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("description") or "",
                "nature": item.get("nature") or item.get("nature_label") or "",
                "nombre": item.get("nombre") or item.get("nombreParts") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_valeurs_bourse"] = details

    # ── NEW: valeurs non cotées ───────────────────────────────────────────
    non_bourse = data.get("valeurs_non_bourse", [])
    if non_bourse:
        details = []
        for item in non_bourse[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("description") or "",
                "nature": item.get("nature") or item.get("nature_label") or "",
                "nombre": item.get("nombre") or item.get("nombreParts") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_valeurs_non_bourse"] = details

    # ── NEW: assurances vie ───────────────────────────────────────────────
    assurances = data.get("assurances_vie", [])
    if assurances:
        details = []
        for item in assurances[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "organisme": item.get("organisme") or item.get("organisme_label") or item.get("assureur") or item.get("denomination") or "",
                "description": item.get("description") or item.get("nature") or item.get("nature_label") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_assurances_vie"] = details

    # ── NEW: fonds ────────────────────────────────────────────────────────
    fonds = data.get("fonds", [])
    if fonds:
        details = []
        for item in fonds[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("description") or "",
                "gestionnaire": item.get("gestionnaire") or item.get("organisme") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_fonds"] = details

    # ── NEW: instruments financiers ───────────────────────────────────────
    instruments = data.get("instruments_financiers", [])
    if instruments:
        details = []
        for item in instruments[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("description") or "",
                "nature": item.get("nature") or item.get("nature_label") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_instruments_financiers"] = details

    # ── NEW: dettes & emprunts ────────────────────────────────────────────
    dettes = data.get("dettes", [])
    if dettes:
        details = []
        for item in dettes[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "organisme": item.get("organisme") or item.get("organisme_label") or item.get("etablissement") or item.get("preteur") or "",
                "description": item.get("description") or item.get("objet") or item.get("nature") or item.get("nature_label") or "",
                "date_emprunt": item.get("dateEmprunt") or item.get("dateContractation") or "",
                "montant": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_dettes"] = details

    # ── NEW: véhicules ────────────────────────────────────────────────────
    vehicules = data.get("vehicules", [])
    if vehicules:
        details = []
        for item in vehicules[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "marque": item.get("marque") or item.get("marque_label") or "",
                "modele": item.get("modele") or item.get("designation") or item.get("description") or "",
                "annee": item.get("annee") or item.get("anneeMiseEnCirculation") or "",
                "mode_acquisition": item.get("modeAcquisition") or item.get("modeAcquisition_label") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_vehicules"] = details

    # ── NEW: parts de SCI ─────────────────────────────────────────────────
    sci = data.get("parts_sci", [])
    if sci:
        details = []
        for item in sci[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("designation") or "",
                "nombre_parts": item.get("nombreParts") or item.get("nombre") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_parts_sci"] = details

    # ── NEW: biens divers ─────────────────────────────────────────────────
    divers = data.get("biens_divers", [])
    if divers:
        details = []
        for item in divers[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "description": item.get("description") or item.get("nature") or item.get("nature_label") or "",
                "valeur": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_biens_divers"] = details

    # ── NEW: activités du/de la conjoint·e ────────────────────────────────
    conjoint = data.get("activites_conjoint", [])
    if conjoint:
        details = []
        for item in conjoint[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("employeur") or "",
                "fonction": item.get("fonction") or item.get("fonction_label") or item.get("activite") or item.get("activite_label") or "",
                "remuneration": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_activites_conjoint"] = details

    # ── NEW: fonctions bénévoles ──────────────────────────────────────────
    benevoles = data.get("fonctions_benevoles", [])
    if benevoles:
        details = []
        for item in benevoles[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("organisme") or "",
                "fonction": item.get("fonction") or item.get("fonction_label") or item.get("activite") or "",
            })
            if d:
                details.append(d)
        if details:
            resume["details_fonctions_benevoles"] = details

    # ── NEW: activités antérieures ────────────────────────────────────────
    anterieures = data.get("activites_anterieures", [])
    if anterieures:
        details = []
        for item in anterieures[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("employeur") or "",
                "fonction": item.get("fonction") or item.get("fonction_label") or item.get("activite") or item.get("activite_label") or "",
                "date_debut": item.get("dateDebut") or "",
                "date_fin": item.get("dateFin") or "",
                "remuneration": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_activites_anterieures"] = details

    # ── NEW: activités de consultant ──────────────────────────────────────
    consultant = data.get("activites_consultant", [])
    if consultant:
        details = []
        for item in consultant[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "denomination": item.get("denomination") or item.get("denomination_label") or item.get("employeur") or "",
                "fonction": item.get("fonction") or item.get("fonction_label") or "",
                "remuneration": _first_financial(item),
            })
            if d:
                details.append(d)
        if details:
            resume["details_activites_consultant"] = details

    # ── NEW: autres liens d'intérêts ──────────────────────────────────────
    autres_liens = data.get("autres_liens_interets", [])
    if autres_liens:
        details = []
        for item in autres_liens[:MAX_DETAIL_ITEMS]:
            d = _compact({
                "description": item.get("description") or item.get("nature") or item.get("nature_label") or item.get("denomination") or "",
                "organisme": item.get("organisme") or item.get("organisme_label") or "",
            })
            if d:
                details.append(d)
        if details:
            resume["details_autres_liens_interets"] = details

    # ── NEW: déclarations (metadata per declaration) ──────────────────────
    decls = data.get("declarations", [])
    if decls:
        resume["declarations_detail"] = [
            _compact({
                "type": d.get("type", ""),
                "label": d.get("label", ""),
                "date_depot": d.get("date_depot", ""),
                "qualite": d.get("qualite", ""),
                "organe": d.get("organe", ""),
            })
            for d in decls[:10]
            if d and not d.get("dry_run")
        ]

    return resume


def build_full_detail_hatvp(data: dict) -> dict:
    """Build full detail dict for per-person JSON (no MAX_DETAIL_ITEMS cap)."""
    # Reuse resume logic but without item caps
    resume = build_resume_hatvp(data)

    # Now re-extract ALL details without the 20-item cap
    def _first_financial(item: dict):
        for k in FINANCIAL_FIELD_NAMES:
            v = item.get(k)
            if v is not None:
                if isinstance(v, str):
                    v = parse_montant(v)
                if isinstance(v, (int, float)):
                    return v
        return None

    def _compact(d: dict) -> dict:
        return {k: v for k, v in d.items() if v not in (None, "", 0, 0.0)}

    # Map section_name → (details_key, extractor)
    # Each extractor takes a raw item dict and returns a compact detail dict
    def _act(item):
        d = _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("employeur") or "",
            "remuneration": _first_financial(item),
            "fonction": item.get("fonction") or item.get("fonction_label") or item.get("activite") or item.get("activite_label") or "",
        })
        # Preserve montant_euro and revenus_annuels from PDF extraction
        me = item.get("montant_euro")
        if me and isinstance(me, (int, float)):
            d["montant_euro"] = me
        ra = item.get("revenus_annuels")
        if ra and isinstance(ra, list) and len(ra) > 0:
            d["revenus_annuels"] = ra
        return _compact(d)

    def _mandat(item):
        d = _compact({
            "mandat": item.get("mandat") or item.get("mandat_label") or item.get("typeMandat") or item.get("typeMandat_label") or "",
            "organisme": item.get("organisme") or item.get("organisme_label") or item.get("collectivite") or item.get("collectivite_label") or "",
            "remuneration": _first_financial(item),
        })
        # Preserve montant_euro and revenus_annuels from PDF extraction
        me = item.get("montant_euro")
        if me and isinstance(me, (int, float)):
            d["montant_euro"] = me
        ra = item.get("revenus_annuels")
        if ra and isinstance(ra, list) and len(ra) > 0:
            d["revenus_annuels"] = ra
        return _compact(d)

    def _part(item):
        return _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("designation") or "",
            "type": item.get("nature") or item.get("nature_label") or item.get("type") or item.get("type_label") or "",
            "valeur": _first_financial(item),
        })

    def _rev(item):
        return _compact({
            "type": item.get("type_revenu") or item.get("nature") or item.get("nature_label") or item.get("description") or "",
            "organisme": item.get("organisme") or item.get("organisme_label") or item.get("denomination") or item.get("employeur") or "",
            "montant": _first_financial(item),
        })

    def _immo(item):
        return _compact({
            "description": item.get("description") or item.get("description_label") or "",
            "nature": item.get("nature") or item.get("nature_label") or item.get("typeBien") or item.get("typeBien_label") or "",
            "lieu": item.get("lieu") or item.get("localisation") or item.get("commune") or item.get("commune_label") or item.get("adresse") or "",
            "departement": item.get("departement") or item.get("departement_label") or item.get("codeDepartement") or "",
            "surface": item.get("surface") or item.get("surfaceBien") or "",
            "mode_acquisition": item.get("modeAcquisition") or item.get("modeAcquisition_label") or item.get("modeDetention") or item.get("modeDetention_label") or "",
            "date_acquisition": item.get("dateAcquisition") or item.get("anneeAcquisition") or "",
            "valeur": _first_financial(item),
        })

    def _compte(item):
        return _compact({
            "etablissement": item.get("etablissement") or item.get("banque") or item.get("nomEtablissement") or item.get("organisme") or "",
            "type_compte": item.get("nature") or item.get("nature_label") or item.get("typeCompte") or item.get("typeCompte_label") or "",
            "description": item.get("description") or "",
            "solde": _first_financial(item),
        })

    def _bourse(item):
        return _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("description") or "",
            "nature": item.get("nature") or item.get("nature_label") or "",
            "nombre": item.get("nombre") or item.get("nombreParts") or "",
            "valeur": _first_financial(item),
        })

    def _assurance(item):
        return _compact({
            "organisme": item.get("organisme") or item.get("organisme_label") or item.get("assureur") or item.get("denomination") or "",
            "description": item.get("description") or item.get("nature") or item.get("nature_label") or "",
            "valeur": _first_financial(item),
        })

    def _fond(item):
        return _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("description") or "",
            "gestionnaire": item.get("gestionnaire") or item.get("organisme") or "",
            "valeur": _first_financial(item),
        })

    def _instr(item):
        return _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("description") or "",
            "nature": item.get("nature") or item.get("nature_label") or "",
            "valeur": _first_financial(item),
        })

    def _dette(item):
        return _compact({
            "organisme": item.get("organisme") or item.get("organisme_label") or item.get("etablissement") or item.get("preteur") or "",
            "description": item.get("description") or item.get("objet") or item.get("nature") or item.get("nature_label") or "",
            "date_emprunt": item.get("dateEmprunt") or item.get("dateContractation") or "",
            "montant": _first_financial(item),
        })

    def _vehicule(item):
        return _compact({
            "marque": item.get("marque") or item.get("marque_label") or "",
            "modele": item.get("modele") or item.get("designation") or item.get("description") or "",
            "annee": item.get("annee") or item.get("anneeMiseEnCirculation") or "",
            "mode_acquisition": item.get("modeAcquisition") or item.get("modeAcquisition_label") or "",
            "valeur": _first_financial(item),
        })

    def _sci(item):
        return _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("designation") or "",
            "nombre_parts": item.get("nombreParts") or item.get("nombre") or "",
            "valeur": _first_financial(item),
        })

    def _divers(item):
        return _compact({
            "description": item.get("description") or item.get("nature") or item.get("nature_label") or "",
            "valeur": _first_financial(item),
        })

    def _conjoint(item):
        return _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("employeur") or "",
            "fonction": item.get("fonction") or item.get("fonction_label") or item.get("activite") or item.get("activite_label") or "",
            "remuneration": _first_financial(item),
        })

    def _benevole(item):
        return _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("organisme") or "",
            "fonction": item.get("fonction") or item.get("fonction_label") or item.get("activite") or "",
        })

    def _anterieure(item):
        return _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("employeur") or "",
            "fonction": item.get("fonction") or item.get("fonction_label") or item.get("activite") or item.get("activite_label") or "",
            "date_debut": item.get("dateDebut") or "",
            "date_fin": item.get("dateFin") or "",
            "remuneration": _first_financial(item),
        })

    def _consultant(item):
        return _compact({
            "denomination": item.get("denomination") or item.get("denomination_label") or item.get("employeur") or "",
            "fonction": item.get("fonction") or item.get("fonction_label") or "",
            "remuneration": _first_financial(item),
        })

    def _liens(item):
        return _compact({
            "description": item.get("description") or item.get("nature") or item.get("nature_label") or item.get("denomination") or "",
            "organisme": item.get("organisme") or item.get("organisme_label") or "",
        })

    SECTION_EXTRACTORS = {
        "activites_professionnelles": ("details_activites", _act),
        "mandats_electifs":           ("details_mandats", _mandat),
        "participations_financieres": ("details_participations", _part),
        "participations_organes":     ("details_participations", _part),
        "revenus":                    ("details_revenus", _rev),
        "biens_immobiliers":          ("details_biens_immobiliers", _immo),
        "comptes_bancaires":          ("details_comptes_bancaires", _compte),
        "valeurs_bourse":             ("details_valeurs_bourse", _bourse),
        "valeurs_non_bourse":         ("details_valeurs_non_bourse", _bourse),
        "assurances_vie":             ("details_assurances_vie", _assurance),
        "fonds":                      ("details_fonds", _fond),
        "instruments_financiers":     ("details_instruments_financiers", _instr),
        "dettes":                     ("details_dettes", _dette),
        "vehicules":                  ("details_vehicules", _vehicule),
        "parts_sci":                  ("details_parts_sci", _sci),
        "biens_divers":               ("details_biens_divers", _divers),
        "activites_conjoint":         ("details_activites_conjoint", _conjoint),
        "fonctions_benevoles":        ("details_fonctions_benevoles", _benevole),
        "activites_anterieures":      ("details_activites_anterieures", _anterieure),
        "activites_consultant":       ("details_activites_consultant", _consultant),
        "autres_liens_interets":      ("details_autres_liens_interets", _liens),
    }

    for section_name, (details_key, extractor) in SECTION_EXTRACTORS.items():
        items = data.get(section_name, [])
        if not items:
            continue
        details = [d for d in (extractor(item) for item in items) if d]
        if details:
            if details_key in resume:
                resume[details_key].extend(details)
            else:
                resume[details_key] = details

    # Declarations (no cap)
    decls = data.get("declarations", [])
    if decls:
        resume["declarations_detail"] = [
            _compact({
                "type": d.get("type", ""),
                "label": d.get("label", ""),
                "date_depot": d.get("date_depot", ""),
                "qualite": d.get("qualite", ""),
                "organe": d.get("organe", ""),
            })
            for d in decls
            if d and not d.get("dry_run")
        ]

    # ── Pre-compute yearly revenue aggregates ─────────────────────────────────
    # Aggregate revenus_annuels across all activities and mandates so the
    # frontend can display last-year totals without any computation.
    year_totals: dict[str, float] = {}
    for section_key in ("details_activites", "details_mandats"):
        for item in resume.get(section_key, []):
            ra = item.get("revenus_annuels")
            if not ra or not isinstance(ra, list):
                continue
            for ys in ra:
                annee = ys.get("annee")
                montant = ys.get("montant")
                if annee and isinstance(montant, (int, float)) and montant > 0:
                    year_totals[annee] = year_totals.get(annee, 0.0) + montant

    if year_totals:
        valid_years = [y for y in year_totals.keys() if y.isdigit()]
        if valid_years:
            last_year = max(valid_years, key=lambda y: int(y))
            resume["last_year_revenus"] = year_totals[last_year]
            resume["last_year_label"] = last_year
            resume["total_revenus_all_years"] = sum(year_totals.values())

    return resume


def save_elu_detail(elu: dict, hatvp_full: dict) -> None:
    """Save a per-person JSON file to public/data/elus/{id}.json."""
    os.makedirs(ELUS_DETAIL_DIR, exist_ok=True)
    elu_id = elu.get("id", "")
    if not elu_id:
        return
    detail = dict(elu)
    detail["hatvp"] = hatvp_full
    out_path = os.path.join(ELUS_DETAIL_DIR, f"{elu_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False, separators=(",", ":"))


# ══════════════════════════════════════════════════════════════════════════════
# I/O elus.json
# ══════════════════════════════════════════════════════════════════════════════

def load_elus() -> list[dict]:
    if not os.path.exists(OUTPUT_JSON):
        print(f"⚠ {OUTPUT_JSON} introuvable")
        return []
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def save_elus(elus: list[dict]) -> None:
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(elus, f, ensure_ascii=False, indent=2)
    print(f"✓ {OUTPUT_JSON} mis à jour ({len(elus)} élus)")


# ── Fields needed by the list page (/liste) ──────────────────────────────────
# PersonCard displays: id, nom, prenom, fonction, region, groupe, patrimoine,
#   revenus, photo_url, hatvp.nb_declarations_hatvp, declarations_csv (count).
# SearchBar filters on: nom, prenom, fonction, region, groupe, parti, mandats,
#   types_mandat. Sorts by: nom, patrimoine, revenus.
LIST_PAGE_FIELDS = {
    "id", "nom", "prenom", "fonction", "region", "groupe", "parti",
    "mandats", "types_mandat", "patrimoine", "revenus", "immobilier",
    "placements_montant", "photo", "photo_url",
}

# HATVP summary fields needed by list page (counts + aggregates, NO details_*)
LIST_HATVP_FIELDS = {
    "nb_declarations_hatvp", "hatvp_scraped_at",
    "patrimoine_net_euro", "total_actif_brut_euro", "total_dettes_euro",
    "total_revenus_euro", "last_year_revenus", "last_year_label",
    "total_revenus_all_years",
}


def build_list_entry(elu: dict) -> dict:
    """Build a minimal entry for elus.json containing only list-page fields.
    All detail data (details_*, declarations_csv, liens, etc.) is stripped."""
    entry: dict = {}
    for k in LIST_PAGE_FIELDS:
        v = elu.get(k)
        if v is not None and v != "" and v != 0 and v != []:
            entry[k] = v
    # Always include id, nom, prenom, fonction
    for k in ("id", "nom", "prenom", "fonction"):
        if k not in entry:
            entry[k] = elu.get(k, "")

    # Slim HATVP: only counts + aggregates
    hatvp = elu.get("hatvp")
    if hatvp and isinstance(hatvp, dict):
        slim_hatvp: dict = {}
        for k, v in hatvp.items():
            if k in LIST_HATVP_FIELDS:
                if v is not None and v != "" and v != 0:
                    slim_hatvp[k] = v
            elif k.startswith("nb_") and isinstance(v, (int, float)) and v > 0:
                slim_hatvp[k] = v
            elif k.startswith("valeur_") and k.endswith("_euro") and isinstance(v, (int, float)) and v > 0:
                slim_hatvp[k] = v
        if slim_hatvp:
            entry["hatvp"] = slim_hatvp

    # Declaration count for display (avoid storing full declarations_csv)
    decl_csv = elu.get("declarations_csv")
    if decl_csv and isinstance(decl_csv, list) and len(decl_csv) > 0:
        entry["nb_declarations_csv"] = len(decl_csv)

    return entry


def _clean_detail_artifacts(elu: dict) -> dict:
    """Clean page footer artifacts and DIA noise from existing detail data.
    Removes patterns like 'Page 2/3 DI/ABADIE-Muriel' and DIA section headers
    from descriptions."""
    import copy
    elu = copy.deepcopy(elu)
    _PAGE_FOOTER_RE = re.compile(
        r'\s*Page\s+\d+/\d+(?:\s+D[IA]+/[A-Za-zÀ-ÿ\-]+)?\s*'
    )
    _DIA_NOISE_LINES = re.compile(
        r'(?:Rémunération,?\s*indemnité.*|Description\s*|ou\s+gratification\s*|'
        r'Conjoint,?\s*partenaire\s+lié\s+par\s+PACS\s+ou\s+concubin\s*|'
        r'Activité\s+professionnelle\s*|'
        r'Commentaire\s*:\s*Page\s+\d+/\d+\s+D[IA]+/[A-Za-zÀ-ÿ\-]+)',
        re.IGNORECASE,
    )
    _SECTION_HEADER_RE = re.compile(
        r'^\d+°\s+(?:Les\s+)?(?:activit[ée]s|fonctions|participations|collaborateurs).*?'
        r'(?:nomination|élection|d[ée]clarant)\s*',
        re.IGNORECASE,
    )
    _FRAGMENT_RE = re.compile(
        r'^ou\s+de\s+la\s+nomination\s+par\s+le\s+conjoint.*?concubin\s*|'
        r'^ou\s+de\s+la\s+nomination\s+et\s+au\s+cours\s+des\s+cinq.*?d[ée]claration\s*|'
        r'^ou\s+de\s+la\s+nomination\s*$',
        re.IGNORECASE,
    )

    def _clean_str(s: str) -> str:
        if not isinstance(s, str):
            return s
        s = _PAGE_FOOTER_RE.sub(' ', s).strip()
        s = _DIA_NOISE_LINES.sub('', s).strip()
        s = _SECTION_HEADER_RE.sub('', s).strip()
        s = _FRAGMENT_RE.sub('', s).strip()
        s = re.sub(r'\s{2,}', ' ', s)
        return s

    def _clean_dict(d: dict) -> dict:
        for k, v in d.items():
            if isinstance(v, str):
                d[k] = _clean_str(v)
            elif isinstance(v, dict):
                _clean_dict(v)
            elif isinstance(v, list):
                _clean_list(v)
        return d

    def _clean_list(lst: list) -> list:
        for i, item in enumerate(lst):
            if isinstance(item, dict):
                _clean_dict(item)
            elif isinstance(item, str):
                lst[i] = _clean_str(item)
        return lst

    # Clean all detail-related fields in hatvp
    hatvp = elu.get("hatvp")
    if hatvp and isinstance(hatvp, dict):
        for k, v in hatvp.items():
            if k.startswith("details_") and isinstance(v, list):
                _clean_list(v)

    # Clean top-level detail fields (some elus have details_* at top level)
    for k, v in elu.items():
        if k.startswith("details_") and isinstance(v, list):
            _clean_list(v)

    return elu


def reorganize_data(batch_size: int = 100) -> None:
    """Reorganize data: write full individual JSONs + slim elus.json.

    - Each individual {id}.json gets ALL data from the elu
    - elus.json is stripped to only list-page fields (~2-3 MB vs 50+ MB)
    - Individual files are written in batches of `batch_size`

    IMPORTANT: If elus.json is already slim (no details_* in hatvp),
    existing individual JSONs are preserved — only the slim list is rebuilt.
    This prevents data loss when --reorganize runs after an earlier reorganize
    already created full individual JSONs.
    """
    all_elus = load_elus()
    if not all_elus:
        print("⚠ elus.json vide ou introuvable.")
        return

    os.makedirs(ELUS_DETAIL_DIR, exist_ok=True)
    total = len(all_elus)
    slim_list: list[dict] = []
    written = 0

    # Detect if elus.json has full data (details_*) or is already slim.
    # Sample the first 100 elus to decide.
    # We check both details_* (from build_resume/full_detail_hatvp) and
    # declarations_csv (added by enrich_elus_from_csv) — either indicates
    # elus.json has richer data than the slim list-page version.
    source_is_full = any(
        any(k.startswith("details_") for k in (e.get("hatvp") or {}))
        or e.get("declarations_csv")
        for e in all_elus[:100]
    )

    if source_is_full:
        print(f"\n📂 Réorganisation des données ({total} élus)…")
        print(f"   → Fichiers individuels complets dans {ELUS_DETAIL_DIR}/")
        print(f"   → elus.json allégé (champs liste uniquement)")
    else:
        print(f"\n📂 Réorganisation des données ({total} élus)…")
        print(f"   → elus.json déjà allégé — fichiers individuels existants préservés")
        print(f"   → Reconstruction de la liste slim uniquement")

    bp = BatchProgress(
        "📂 Réorganisation",
        total=total,
        save_interval=batch_size,
        progress_json_path=PROGRESS_JSON,
    )

    for elu in all_elus:
        elu_id = elu.get("id", "")
        if not elu_id:
            bp.tick(failed=True)
            continue

        if source_is_full:
            out_path = os.path.join(ELUS_DETAIL_DIR, f"{elu_id}.json")
            base_elu = elu  # default: use elus.json entry

            # If an individual JSON already exists, use it as the base.
            # It may have uncapped details_* (from save_elu_detail /
            # build_full_detail_hatvp) that elus.json's build_resume_hatvp
            # caps at MAX_DETAIL_ITEMS. Merging preserves the richer data.
            if os.path.exists(out_path):
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    # Merge top-level fields from elus.json (enrichment, updates)
                    for k, v in elu.items():
                        if k != "hatvp" and v is not None:
                            existing[k] = v
                    # Merge hatvp: copy counts/totals from elus.json, keep
                    # richer details_* lists from the existing individual JSON
                    elu_hatvp = elu.get("hatvp") or {}
                    existing_hatvp = existing.get("hatvp") or {}
                    for k, v in elu_hatvp.items():
                        if not k.startswith("details_"):
                            existing_hatvp[k] = v
                        else:
                            # Only overwrite details if elus.json has MORE items
                            existing_items = existing_hatvp.get(k, [])
                            if isinstance(v, list) and len(v) > len(existing_items):
                                existing_hatvp[k] = v
                    existing["hatvp"] = existing_hatvp
                    base_elu = existing
                except (json.JSONDecodeError, OSError) as exc:
                    print(f"  ⚠ Could not read existing {elu_id}.json ({exc}), using elus.json entry")
                    pass  # fall back to elus.json entry

            cleaned_elu = _clean_detail_artifacts(base_elu)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(cleaned_elu, f, ensure_ascii=False, separators=(",", ":"))
            written += 1

        # Build slim entry for list (always)
        slim_list.append(build_list_entry(elu))
        bp.tick(updated=True)

    bp.finish()

    # Save slim elus.json
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(slim_list, f, ensure_ascii=False, separators=(",", ":"))

    slim_size = os.path.getsize(OUTPUT_JSON) / (1024 * 1024)
    if source_is_full:
        print(f"\n✅ {written} fichiers individuels générés")
    print(f"✅ elus.json allégé : {slim_size:.1f} MB ({len(slim_list)} élus)")


def find_elu_by_name(elus: list[dict], query: str) -> dict | None:
    q = normalize_name(query)
    for e in elus:
        full = normalize_name(f"{e.get('prenom', '')} {e.get('nom', '')}")
        if q in full or full in q:
            return e
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Affichage
# ══════════════════════════════════════════════════════════════════════════════

def print_section(data: dict, section: str, nb: int = 5) -> None:
    items = data.get(section, [])
    if not items:
        return
    label = SECTION_LABELS.get(section, f"📄 {section}")
    print(f"\n  {label} ({len(items)}) :")
    for item in items[:nb]:
        parts = []
        for k, v in item.items():
            if v and k not in ("commentaire", "_items"):
                if isinstance(v, float):
                    parts.append(f"{k}={v:,.0f} €")
                elif isinstance(v, str) and len(v) < 60:
                    parts.append(f"{k}={v}")
        print(f"    • {' | '.join(parts[:5])}")
    if len(items) > nb:
        print(f"    … et {len(items) - nb} autres")


# Mapping type_mandat CSV → label lisible
MANDAT_LABELS = {
    "depute":       "Député(e)",
    "senateur":     "Sénateur/Sénatrice",
    "president":    "Président(e) de la République",
    "gouvernement": "Membre du Gouvernement",
    "europe":       "Député(e) européen(ne)",
    "region":       "Conseiller(ère) régional(e)",
    "departement":  "Conseiller(ère) départemental(e)",
    "commune":      "Élu(e) municipal(e)",
    "epci":         "Élu(e) intercommunal(e)",
    "ctsp":         "Élu(e) collectivité territoriale",
    "autre":        "Autre mandat",
}


def enrich_elus_from_csv(elus: list[dict], csv_index: list[dict]) -> None:
    """
    Enrichir les élus avec les métadonnées du CSV HATVP
    (qualité, type_mandat, département, photo, etc.)
    """
    # Construire un index CSV par nom normalisé
    csv_by_name: dict[str, list[dict]] = {}
    for row in csv_index:
        nom = normalize_name(row.get("nom", ""))
        prenom = normalize_name(row.get("prenom", ""))
        key = f"{prenom} {nom}"
        csv_by_name.setdefault(key, []).append(row)

    enriched = 0
    for elu in elus:
        prenom = elu.get("prenom", "").strip()
        nom = elu.get("nom", "").strip()
        key = normalize_name(f"{prenom} {nom}")

        rows = csv_by_name.get(key, [])
        if not rows:
            continue

        # Trier par date_publication (plus récent en premier)
        def sort_key(r):
            d = r.get("date_publication", "")
            try:
                return datetime.strptime(d.strip(), "%Y-%m-%d")
            except (ValueError, AttributeError):
                return datetime.min
        rows.sort(key=sort_key, reverse=True)

        # Récupérer la qualité la plus récente comme fonction
        latest = rows[0]
        qualite = (latest.get("qualite") or "").strip()
        if qualite and (elu.get("fonction") in ("Élu(e)", "", None)):
            elu["fonction"] = qualite

        # Récupérer le département
        dept = (latest.get("departement") or "").strip()
        if dept and not elu.get("region"):
            elu["region"] = f"Département {dept}" if dept.isdigit() else dept

        # Photo depuis le CSV (url_photo)
        for row in rows:
            photo_url = (row.get("url_photo") or "").strip()
            if photo_url:
                elu["photo_url"] = photo_url
                break

        # Collecter tous les mandats et qualités uniques
        mandats_set = set()
        types_mandat_set = set()
        declarations_info = []
        for row in rows:
            tm = (row.get("type_mandat") or "").strip().lower()
            q = (row.get("qualite") or "").strip()
            doc_type = (row.get("type_document") or "").strip().lower()
            date_pub = (row.get("date_publication") or "").strip()
            date_depot = (row.get("date_depot") or "").strip()

            if tm:
                types_mandat_set.add(tm)
                label = MANDAT_LABELS.get(tm, tm.capitalize())
                if q:
                    mandats_set.add(q)
                else:
                    mandats_set.add(label)

            # Garder l'info sur les déclarations disponibles
            if doc_type:
                declarations_info.append({
                    "type": doc_type.upper(),
                    "date_publication": date_pub,
                    "date_depot": date_depot,
                    "qualite": q,
                    "type_mandat": tm,
                })

        if mandats_set:
            # Merge with existing mandats to avoid losing data
            existing_mandats = set(elu.get("mandats", []))
            elu["mandats"] = sorted(existing_mandats | mandats_set)

        if types_mandat_set:
            # Merge with existing types_mandat
            existing_types = set(elu.get("types_mandat", []))
            elu["types_mandat"] = sorted(existing_types | types_mandat_set)

        if declarations_info:
            # Merge with existing declarations_csv, avoiding duplicates
            existing_decls = elu.get("declarations_csv", [])
            existing_keys = {(d.get("type", ""), d.get("date_publication", "")) for d in existing_decls}
            for di in declarations_info:
                k = (di.get("type", ""), di.get("date_publication", ""))
                if k not in existing_keys:
                    existing_decls.append(di)
                    existing_keys.add(k)
            elu["declarations_csv"] = existing_decls[:10]  # Limiter à 10

        # Lien HATVP depuis url_dossier
        for row in rows:
            url_dossier = (row.get("url_dossier") or "").strip()
            if url_dossier:
                elu["liens"]["hatvp"] = f"https://www.hatvp.fr{url_dossier}"
                break

        # 85296 = fake default revenue (≈ député brut annuel) applied in initial data generation
        if elu.get("revenus", 0) == 85296:
            elu["revenus"] = 0

        enriched += 1

    print(f"  ✓ {enriched} élus enrichis depuis le CSV")


def _flush_xml_batch(pending: dict[str, dict], csv_index: list[dict]) -> None:
    """Apply a batch of pending XML updates to elus.json and individual JSONs."""
    all_elus = load_elus()

    # Build full detail (no cap) for per-person JSONs
    full_details: dict[str, dict] = {}
    for eid in pending:
        cache_path = os.path.join(CACHE_DIR, f"{eid}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    raw_result = json.load(f)
                full_details[eid] = build_full_detail_hatvp(raw_result)
            except (json.JSONDecodeError, OSError):
                full_details[eid] = pending[eid]
        else:
            full_details[eid] = pending[eid]

    for e in all_elus:
        eid = e.get("id")
        if eid not in pending:
            continue
        resume = pending[eid]
        e["hatvp"] = resume
        if resume.get("total_revenus_euro", 0) > 0:
            e["revenus"] = resume["total_revenus_euro"]
        elif e.get("revenus", 0) == 85296:
            e["revenus"] = 0
        pat_net = resume.get("patrimoine_net_euro", 0)
        if pat_net:
            e["patrimoine"] = pat_net
        act_brut = resume.get("total_actif_brut_euro", 0)
        if act_brut:
            e["immobilier"] = resume.get("valeur_biens_immobiliers_euro", 0)
            e["placements_montant"] = (
                resume.get("valeur_instruments_financiers_euro", 0)
                + resume.get("valeur_participations_financieres_euro", 0)
                + resume.get("valeur_comptes_bancaires_euro", 0)
                + resume.get("valeur_valeurs_bourse_euro", 0)
                + resume.get("valeur_valeurs_non_bourse_euro", 0)
                + resume.get("valeur_assurances_vie_euro", 0)
                + resume.get("valeur_fonds_euro", 0)
            )
        # Save per-person JSON with full details (no item cap)
        save_elu_detail(e, full_details.get(eid, resume))

    enrich_elus_from_csv(all_elus, csv_index)
    save_elus(all_elus)
    print(f"  ✓ Saved {len(pending)} individual JSONs + elus.json")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    print("=" * 65)
    print("💰 SCRAPER HATVP — PATRIMOINE COMPLET (DSP + DI)")
    print("   XML global  : declarations.xml")
    print("   Index CSV   : liste.csv")
    if args.dry_run:
        print("   ⚠ MODE DRY-RUN — aucun fichier ne sera écrit")
    print("=" * 65)

    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.join(CACHE_DIR, "xmls"), exist_ok=True)

    # ── Charger le CSV index ───────────────────────────────────────────────────
    print("\n📥 Chargement de l'index CSV HATVP…")
    csv_index = load_hatvp_index(force_refresh=args.refresh_index, delay=args.delay)

    if args.dump_csv_columns and csv_index:
        print(f"\n  📋 Colonnes CSV : {list(csv_index[0].keys())}")
        print(f"  📋 Exemple ligne 1 :")
        for k, v in csv_index[0].items():
            print(f"    {k:25s} = {v}")
        print(f"  📋 Exemple ligne 2 :")
        for k, v in csv_index[1].items():
            print(f"    {k:25s} = {v}")
        return

    # ── Mode enrichissement CSV uniquement ────────────────────────────────────
    if args.enrich_csv_only:
        print("\n📋 Mode enrichissement CSV uniquement…")
        all_elus = load_elus()
        if not all_elus:
            print("⚠ elus.json vide ou introuvable.")
            return
        enrich_elus_from_csv(all_elus, csv_index)
        if not args.dry_run:
            save_elus(all_elus)
        print(f"\n✅ Enrichissement terminé — {len(all_elus)} élus")
        return

    # ── Mode split: generate per-person JSON files from existing elus.json ────
    if args.split_elus:
        print("\n📂 Génération des fichiers JSON par personne…")
        all_elus = load_elus()
        if not all_elus:
            print("⚠ elus.json vide ou introuvable.")
            return
        os.makedirs(ELUS_DETAIL_DIR, exist_ok=True)
        count = 0
        for elu in all_elus:
            elu_id = elu.get("id", "")
            if not elu_id:
                continue
            out_path = os.path.join(ELUS_DETAIL_DIR, f"{elu_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(elu, f, ensure_ascii=False, separators=(",", ":"))
            count += 1
        print(f"✅ {count} fichiers JSON générés dans {ELUS_DETAIL_DIR}")
        return

    # ── Mode reorganize: full individual JSONs + slim elus.json ───────────────
    if args.reorganize:
        reorganize_data(batch_size=100)
        return

    # ── Charger le XML global ──────────────────────────────────────────────────
    print("\n📥 Chargement du XML global HATVP…")
    xml_root = load_declarations_xml(force_refresh=args.refresh_xml, delay=args.delay)

    if args.dump_xml_sample and xml_root is not None:
        print(f"\n  📋 Structure XML racine : <{xml_root.tag}> ({len(list(xml_root))} enfants)")
        for i, child in enumerate(xml_root):
            if i >= 3:
                break
            print(f"\n  ── Déclaration {i+1} : <{child.tag}>")
            snippet = ET.tostring(child, encoding="unicode")[:3000]
            print(snippet)
        return

    # Construire l'index par nom
    xml_index: dict[str, list[ET.Element]] = {}
    if xml_root is not None:
        print("\n🔨 Construction de l'index par nom…")
        xml_index = build_xml_index(xml_root)

    if not xml_index and not csv_index:
        print("❌ Aucune donnée HATVP disponible (ni XML ni CSV)")
        return

    # ── Mode test ──────────────────────────────────────────────────────────────
    if args.test_elu:
        print(f"\n🧪 Mode test — élu : {args.test_elu}")
        elus = load_elus()
        elu  = find_elu_by_name(elus, args.test_elu)
        if not elu:
            parts = args.test_elu.strip().split()
            elu = {"id": "test", "prenom": parts[0], "nom": " ".join(parts[1:])}
        print(f"  Profil : {elu.get('prenom')} {elu.get('nom')}")

        result = fetch_data_for_elu(
            elu, xml_index, csv_index,
            force=True, dry_run=args.dry_run, delay=args.delay
        )

        if result:
            print(f"\n{'=' * 65}")
            print("✅ RÉSULTAT COMPLET")
            print(f"{'=' * 65}")
            print(f"  Déclarations trouvées : {result['declarations_trouvees']}")

            total_items = sum(
                len(result.get(s, []))
                for s in ALL_OUTPUT_SECTIONS
                if isinstance(result.get(s), list)
            )
            print(f"  Total éléments extraits : {total_items}")

            for section in ALL_OUTPUT_SECTIONS:
                print_section(result, section)

            # Sections dynamiques (non prédéfinies)
            for k, v in result.items():
                if isinstance(v, list) and v and k not in ALL_OUTPUT_SECTIONS and k != "declarations":
                    print_section(result, k)

            print(f"\n  📊 Résumé patrimoine :")
            resume = build_resume_hatvp(result)
            print(json.dumps(resume, ensure_ascii=False, indent=4))
        else:
            print("  ✗ Aucune donnée récupérée")
        return

    # ── Mode batch ────────────────────────────────────────────────────────────
    elus = load_elus()
    if not elus:
        print("⚠ elus.json vide ou introuvable. Utilisez --test-elu pour tester.")
        return

    if args.limit:
        elus = elus[: args.limit]

    total     = len(elus)
    done      = 0
    not_found = 0
    with_data = 0
    save_every = args.save_every
    # Buffer of updates accumulated since last checkpoint save
    pending: dict[str, dict] = {}
    # All updates (for the final reorganize)
    all_updated: dict[str, dict] = {}

    bp = BatchProgress(
        "🗳️ XML Processing",
        total=total,
        save_interval=save_every,
        progress_json_path=PROGRESS_JSON,
    )

    for i, elu in enumerate(elus, 1):
        prenom = elu.get("prenom", "")
        nom    = elu.get("nom",    "")
        elu_id = elu.get("id",     f"elu-{i}")
        print(f"\n[{i}/{total}] {prenom} {nom}")

        result = fetch_data_for_elu(
            elu, xml_index, csv_index,
            force=args.force, dry_run=args.dry_run, delay=args.delay
        )

        if result is None:
            not_found += 1
            is_checkpoint = bp.tick(failed=True)
        else:
            done += 1
            resume = build_resume_hatvp(result)
            pending[elu_id] = resume
            all_updated[elu_id] = resume

            total_items = sum(
                len(result.get(s, []))
                for s in ALL_OUTPUT_SECTIONS
                if isinstance(result.get(s), list)
            )

            if total_items:
                with_data += 1
                summary_parts = [
                    f"{len(result[s])} {s.replace('_', ' ')}"
                    for s in ALL_OUTPUT_SECTIONS
                    if isinstance(result.get(s), list) and result.get(s)
                ]
                print(f"  ✓ {total_items} éléments : {', '.join(summary_parts)}")
            else:
                print(f"  ○ Déclarations trouvées mais aucun élément déclaré")

            # Sauvegarder le détail complet
            if not args.dry_run:
                detail_path = os.path.join(CACHE_DIR, f"{elu_id}.json")
                with open(detail_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

            is_checkpoint = bp.tick(updated=bool(total_items))

        # ── Checkpoint save every save_every elus ────────────────────────
        if is_checkpoint and not args.dry_run and pending:
            print(f"\n💾 Checkpoint ({i}/{total}) — {len(pending)} pending…")
            _flush_xml_batch(pending, csv_index)
            pending.clear()

    # ── Final flush of remaining pending ─────────────────────────────────────
    if not args.dry_run and pending:
        print(f"\n💾 Final save — {len(pending)} remaining…")
        _flush_xml_batch(pending, csv_index)

    bp.finish()

    # NOTE: Do NOT call reorganize_data() here. The checkpoint saves via
    # _flush_xml_batch() already wrote full-detail individual JSONs (via
    # save_elu_detail with build_full_detail_hatvp). Calling reorganize_data()
    # would overwrite those uncapped individual JSONs with the capped resume
    # from elus.json, losing items beyond MAX_DETAIL_ITEMS.
    # The workflow's explicit --reorganize step handles the final slim/split.

    # ── PDF fallback for elus with no patrimoine data ─────────────────────────
    pdf_updated = 0
    if args.with_pdf:
        try:
            from parse_pdf import process_elu_pdfs, update_elu_with_pdf_data
        except ImportError:
            sys.path.insert(0, SCRIPT_DIR)
            from parse_pdf import process_elu_pdfs, update_elu_with_pdf_data

        all_elus = load_elus()
        candidates = [e for e in all_elus if e.get("patrimoine", 0) == 0]
        if args.limit:
            candidates = candidates[:args.limit]

        if candidates:
            print(f"\n{'=' * 65}")
            print(f"📄 PDF FALLBACK — {len(candidates)} élus with patrimoine=0")
            print("=" * 65)

            use_ocr = not args.no_ocr
            for i, elu in enumerate(candidates, 1):
                prenom = elu.get("prenom", "")
                nom = elu.get("nom", "")
                print(f"\n  [PDF {i}/{len(candidates)}] {prenom} {nom}")

                pdf_data = process_elu_pdfs(
                    elu, csv_index,
                    force=args.force,
                    dry_run=args.dry_run,
                    use_ocr=use_ocr,
                    delay=args.delay,
                )

                if pdf_data and update_elu_with_pdf_data(elu, pdf_data):
                    pdf_updated += 1
                    p = elu.get("patrimoine", 0)
                    print(f"    ✓ Patrimoine from PDF: {p:,.0f} €")

            if not args.dry_run and pdf_updated:
                save_elus(all_elus)

    print("\n" + "=" * 65)
    print("📊 RAPPORT FINAL")
    print("=" * 65)
    print(f"  Total traités              : {total}")
    print(f"  ✓ Trouvés dans HATVP       : {done}")
    print(f"  ✓ Avec données financières : {with_data}")
    print(f"  ✗ Non trouvés              : {not_found}")
    if args.with_pdf:
        print(f"  📄 Patrimoine via PDF      : {pdf_updated}")
    print(f"  Détails dans               : {CACHE_DIR}/")
    print("=" * 65)


if __name__ == "__main__":
    main()
