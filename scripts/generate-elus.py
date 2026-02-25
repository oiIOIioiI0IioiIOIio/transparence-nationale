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
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

# ── Chemins ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_JSON  = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")
CACHE_DIR    = os.path.join(PROJECT_ROOT, "public", "data", "hatvp_cache")
INDEX_CACHE  = os.path.join(CACHE_DIR, "liste.csv")
XML_CACHE    = os.path.join(CACHE_DIR, "declarations.xml")

# ── URLs HATVP open data ───────────────────────────────────────────────────────
HATVP_INDEX_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"

# Le XML unique contenant TOUTES les déclarations
HATVP_DECLARATIONS_XML_URL = "https://www.hatvp.fr/livraison/opendata/declarations.xml"

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
DSP_TYPES = {"DSP", "DSPM", "DSPFIN", "DSPMAJ"}
DI_TYPES  = {"DI", "DIM", "DIMAJ"}
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
    Retourne l'élément racine.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    raw = download_file(
        HATVP_DECLARATIONS_XML_URL, XML_CACHE,
        force=force_refresh, max_age_h=48, delay=delay
    )
    if not raw:
        print("  ⚠ Impossible de télécharger le XML complet")
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
    La colonne 'nom_fichier' contient le nom du PDF, mais le XML
    est souvent disponible au même chemin avec extension .xml.
    La colonne 'url_dossier' contient le slug vers la fiche.
    """
    nom_fichier = (csv_row.get("nom_fichier") or "").strip()
    if nom_fichier:
        # Remplacer .pdf par .xml
        base = nom_fichier.rsplit(".", 1)[0] if "." in nom_fichier else nom_fichier
        return HATVP_DOSSIER_BASE + base + ".xml"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Extraction récursive complète d'une déclaration XML
# ══════════════════════════════════════════════════════════════════════════════

# Sections connues du XML HATVP et leur catégorie
KNOWN_SECTIONS = {
    # DSP — Patrimoine
    "instrumentsFinanciersDto":     "instruments_financiers",
    "participationFinanciereDto":   "participations_financieres",
    "biensImmobiliersDto":          "biens_immobiliers",
    "bienImmobilierDto":            "biens_immobiliers",
    "comptesBancairesDto":          "comptes_bancaires",
    "compteBancaireDto":            "comptes_bancaires",
    "liquiditesDto":                "comptes_bancaires",
    "vehiculesDto":                 "vehicules",
    "vehiculeDto":                  "vehicules",
    "autresBiensDto":               "biens_mobiliers_valeur",
    "biensMobiliersDto":            "biens_mobiliers_valeur",
    "biensValeurDto":               "biens_mobiliers_valeur",
    "dettesDto":                    "dettes",
    "detteDto":                     "dettes",
    "empruntsDto":                  "dettes",
    "revenusDto":                   "revenus",
    "revenuDto":                    "revenus",
    "revenusActiviteDto":           "revenus",
    # DI — Intérêts
    "activitesProfessionnellesDto": "activites_professionnelles",
    "activiteProfessionnelleDto":   "activites_professionnelles",
    "fonctionsActuellesDto":        "activites_professionnelles",
    "activitesAnterieuresDto":      "activites_anterieures",
    "activiteAnterieureDto":        "activites_anterieures",
    "fonctionsAnterieuresDto":      "activites_anterieures",
    "mandatsElectifsDto":           "mandats_electifs",
    "mandatElectifDto":             "mandats_electifs",
    "mandatsDto":                   "mandats_electifs",
    "participationsOrganeDto":      "participations_organes",
    "participationOrganeDto":       "participations_organes",
    "organesDirigeantsDto":         "participations_organes",
    "fonctionsBenevolesDto":        "fonctions_benevoles",
    "soutiensAssociationsDto":      "fonctions_benevoles",
    "soutienAssociationDto":        "fonctions_benevoles",
    "activitesBenevolesDto":        "fonctions_benevoles",
    "autresLiensInteretsDto":       "autres_liens_interets",
    "autreLienInteretDto":          "autres_liens_interets",
    "liensInteretsDto":             "autres_liens_interets",
    "autresActivitesDto":           "autres_activites",
    "autreActiviteDto":             "autres_activites",
    # Sections additionnelles courantes
    "fonctionsGouvernementalesDto":  "fonctions_gouvernementales",
    "consultatifEtAutresDto":        "fonctions_consultatives",
    "participationExploitantDto":    "participations_exploitant",
}

ALL_OUTPUT_SECTIONS = sorted(set(KNOWN_SECTIONS.values()))

SECTION_LABELS = {
    "instruments_financiers":       "📈 Instruments financiers",
    "participations_financieres":   "🏢 Participations dans des sociétés",
    "biens_immobiliers":            "🏠 Biens immobiliers",
    "comptes_bancaires":            "🏦 Comptes bancaires & épargne",
    "vehicules":                    "🚗 Véhicules",
    "biens_mobiliers_valeur":       "💎 Biens mobiliers de valeur",
    "dettes":                       "📉 Dettes & emprunts",
    "revenus":                      "💶 Revenus",
    "activites_professionnelles":   "💼 Activités professionnelles",
    "activites_anterieures":        "📋 Activités antérieures",
    "mandats_electifs":             "🗳️  Mandats électifs",
    "participations_organes":       "🏛️  Participations à des organes",
    "fonctions_benevoles":          "🤝 Fonctions bénévoles",
    "autres_liens_interets":        "⚠️  Autres liens d'intérêts",
    "autres_activites":             "📝 Autres activités",
    "fonctions_gouvernementales":   "🏛️  Fonctions gouvernementales",
    "fonctions_consultatives":      "📋 Fonctions consultatives",
    "participations_exploitant":    "🏭 Participations exploitant",
}


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
        "scraped_at":            datetime.utcnow().isoformat() + "Z",
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

    return result


def build_resume_hatvp(data: dict) -> dict:
    """Construire un résumé compact pour elus.json."""

    def count_and_total(items: list[dict]) -> tuple[int, float]:
        n = len(items)
        total = 0.0
        for i in items:
            for k in ("valeur_euro", "solde_euro", "montant_euro",
                       "valeur", "solde", "montant", "valeurParts",
                       "capitalRestantDu", "remuneration_euro", "indemnite_euro"):
                v = i.get(k)
                if v is not None:
                    if isinstance(v, str):
                        v = parse_montant(v)
                    if isinstance(v, (int, float)):
                        total += v
                        break
        return n, total

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
            "mandats_electifs", "participations_organes",
            "fonctions_benevoles", "autres_liens_interets",
            "autres_activites", "fonctions_gouvernementales",
            "fonctions_consultatives",
        ):
            patrimoine_brut += total

    if patrimoine_brut or total_dettes:
        resume["total_actif_brut_euro"] = patrimoine_brut
        resume["total_dettes_euro"]     = total_dettes
        resume["patrimoine_net_euro"]   = patrimoine_brut - total_dettes
    if total_revenus:
        resume["total_revenus_euro"] = total_revenus

    return resume


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
    updated: dict[str, dict] = {}

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
        else:
            done += 1
            resume = build_resume_hatvp(result)
            updated[elu_id] = resume

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

    # ���─ Mettre à jour elus.json ────────────────────────────────────────────────
    if not args.dry_run and updated:
        all_elus = load_elus()
        for e in all_elus:
            if e.get("id") in updated:
                e["hatvp"] = updated[e["id"]]
        save_elus(all_elus)

    print("\n" + "=" * 65)
    print("📊 RAPPORT FINAL")
    print("=" * 65)
    print(f"  Total traités              : {total}")
    print(f"  ✓ Trouvés dans HATVP       : {done}")
    print(f"  ✓ Avec données financières : {with_data}")
    print(f"  ✗ Non trouvés              : {not_found}")
    print(f"  Détails dans               : {CACHE_DIR}/")
    print("=" * 65)


if __name__ == "__main__":
    main()
