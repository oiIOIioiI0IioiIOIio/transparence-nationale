#!/usr/bin/env python3
"""
Script d'extraction HATVP des données des élus français.

Corrections v3 :
  ✓ Correspondance nom/prénom insensible à la casse + majuscules
  ✓ Structure de sortie compatible avec elus.json (hatvp_complete)
  ✓ Parsing XML élargi (tous les chemins HATVP connus)
  ✓ Diagnostic CSV intégré (--debug-csv)
  ✓ Sauvegarde incrémentale tous les 100 élus
  ✓ Gestion d'erreurs robuste

Utilisation :
  python scripts/generate-elus.py
  python scripts/generate-elus.py --limit 50
  python scripts/generate-elus.py --test-elu "Damien ABAD"
  python scripts/generate-elus.py --debug-csv        # affiche les colonnes du CSV
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
from typing import Any, Optional

# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")
CACHE_DIR = os.path.join(PROJECT_ROOT, "public", "data", "hatvp_cache")
INDEX_CACHE = os.path.join(CACHE_DIR, "liste.csv")

HATVP_INDEX_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"
HATVP_XML_BASE = "https://www.hatvp.fr/livraison/dossiers/"

DSP_TYPES = {"DSP", "DSPM"}
DI_TYPES = {"DI", "DIM"}
WANTED_TYPES = DSP_TYPES | DI_TYPES

HEADERS = {
    "User-Agent": "Mozilla/5.0 TransparenceNationale/3.0",
    "Accept": "text/csv, application/xml, text/xml, */*",
}

SAVE_INTERVAL = 100

# ══════════════════════════════════════════════════════════════════════════════
# Utilitaires d'affichage
# ══════════════════════════════════════════════════════════════════════════════

class ProgressTracker:
    def __init__(self, total: int):
        self.total = total
        self.current = 0
        self.success = 0
        self.not_found = 0
        self.errors = 0
        self.start_time = time.time()

    def update(self, success=False, not_found=False, error=False):
        self.current += 1
        if success:
            self.success += 1
        elif not_found:
            self.not_found += 1
        elif error:
            self.errors += 1

    def get_stats(self) -> str:
        elapsed = time.time() - self.start_time
        rate = self.current / elapsed if elapsed > 0 else 0
        remaining = (self.total - self.current) / rate if rate > 0 else 0
        return (f"[{self.current}/{self.total}] "
                f"✓{self.success} ✗{self.not_found} ⚠{self.errors} | "
                f"{rate:.1f}/s | ETA: {int(remaining // 60)}m{int(remaining % 60)}s")

    def print_progress(self, name: str, msg: str = ""):
        print(f"\r{self.get_stats()} | {name[:30]:30s} {msg}", end="", flush=True)

    def print_line(self, msg: str):
        print(f"\n{msg}")


# ══════════════════════════════════════════════════════════════════════════════
# Réseau et cache
# ══════════════════════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 30) -> Optional[bytes]:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 403, 410):
            print(f"\n[http_get] HTTP {exc.code} : {url}", file=sys.stderr)
    except Exception as exc:
        print(f"\n[http_get] Erreur : {exc} ({url})", file=sys.stderr)
    return None


def download_with_cache(url: str, cache_path: str, force: bool = False, delay: float = 0.3) -> Optional[bytes]:
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
# Chargement index CSV
# ══════════════════════════════════════════════════════════════════════════════

def load_hatvp_index(force_refresh: bool = False) -> list[dict]:
    os.makedirs(CACHE_DIR, exist_ok=True)

    raw = None
    if not force_refresh and os.path.exists(INDEX_CACHE):
        age_h = (time.time() - os.path.getmtime(INDEX_CACHE)) / 3600
        if age_h < 24:
            print(f"📋 Index CSV en cache ({age_h:.1f}h)")
            with open(INDEX_CACHE, "rb") as f:
                raw = f.read()

    if raw is None:
        print("📥 Téléchargement index HATVP...")
        time.sleep(0.5)
        raw = http_get(HATVP_INDEX_URL)
        if not raw:
            raise RuntimeError("Impossible de télécharger l'index HATVP")
        with open(INDEX_CACHE, "wb") as f:
            f.write(raw)
        print(f"✓ Index téléchargé ({len(raw):,} octets)")

    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    # Détecter le délimiteur (point-virgule ou virgule)
    first_line = text.split("\n")[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    print(f"✓ {len(rows):,} déclarations indexées")
    if rows:
        print(f"  Colonnes CSV : {list(rows[0].keys())[:10]}")
    return rows


def debug_csv(index: list[dict], n: int = 5):
    """Affiche les colonnes et quelques lignes pour diagnostic."""
    if not index:
        print("Index vide !")
        return
    print(f"\n=== COLONNES CSV ({len(index[0])} colonnes) ===")
    print(list(index[0].keys()))
    print(f"\n=== {n} premières lignes ===")
    for row in index[:n]:
        print(json.dumps(dict(row), ensure_ascii=False))


# ══════════════════════════════════════════════════════════════════════════════
# Normalisation et recherche
# ════════════════════════════════════════════════���═════════════════════════════

def normalize_name(s: str) -> str:
    """Normalise un nom : supprime accents, met en minuscules, normalise espaces."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().strip()
    s = re.sub(r"[-\s]+", " ", s)
    return s


def get_row_field(row: dict, *keys: str) -> str:
    """Cherche une clé dans un dict de façon insensible à la casse."""
    row_lower = {k.lower(): v for k, v in row.items()}
    for key in keys:
        val = row_lower.get(key.lower(), "")
        if val:
            return val.strip()
    return ""


def find_declarations(index: list[dict], prenom: str, nom: str) -> list[dict]:
    """Trouve toutes les déclarations d'un élu, insensible à la casse et aux accents."""
    # Dans elus.json, nom est en MAJUSCULES (ex: "ABAD"), prénom en casse normale ("Damien")
    norm_nom = normalize_name(nom)
    norm_prenom = normalize_name(prenom)

    matched = []
    for row in index:
        # Essayer toutes les variantes de noms de colonnes possibles
        row_nom = get_row_field(row, "nom", "Nom", "NOM", "nomDeclarant", "lastName", "last_name")
        row_prenom = get_row_field(row, "prenom", "Prenom", "PRENOM", "prenomDeclarant", "firstName", "first_name")

        if not row_nom:
            continue

        if normalize_name(row_nom) == norm_nom and normalize_name(row_prenom) == norm_prenom:
            matched.append(row)

    # Trier par date décroissante
    def parse_date(row):
        date_str = get_row_field(row, "dateDepot", "DateDepot", "date_depot", "date")
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        return datetime.min

    matched.sort(key=parse_date, reverse=True)
    return matched


def get_xml_url(row: dict) -> Optional[str]:
    """Construit l'URL du XML à partir d'une ligne du CSV."""
    # Essayer les colonnes URL directes
    url = get_row_field(row, "url", "Url", "URL", "urlFichier", "urlXml")
    if url.startswith("http"):
        return url

    # Essayer le nom de fichier
    fichier = get_row_field(row, "fichier", "Fichier", "nomFichier", "fileName")
    if not fichier:
        # Parfois c'est le champ url mais sans http
        fichier = url

    if fichier:
        if not fichier.endswith(".xml"):
            fichier += ".xml"
        return HATVP_XML_BASE + fichier

    return None


def get_declaration_type(row: dict) -> str:
    return get_row_field(row, "typeDeclaration", "TypeDeclaration", "type", "Type").upper()


# ══════════════════════════════════════════════════════════════════════════════
# Parsing XML robuste
# ══════════════════════════════════════════════════════════════════════════════

def xml_text(element, path: str, default: str = "") -> str:
    if element is None:
        return default
    node = element.find(path)
    if node is not None and node.text:
        t = node.text.strip()
        if t and t not in ("[Données non publiées]", "null", "None"):
            return t
    return default


def xml_bool(element, path: str) -> bool:
    return xml_text(element, path).lower() in ("true", "1", "oui")


def parse_montant(s: str) -> Optional[float]:
    if not s:
        return None
    s = str(s).replace("\xa0", "").replace("\u202f", "").replace(" ", "").replace(",", ".").strip()
    s = re.sub(r"[^\d.-]", "", s)
    if not s or s in (".", "-"):
        return None
    try:
        v = float(s)
        return v if v != 0 else None
    except ValueError:
        return None


def is_empty_section(element) -> bool:
    if element is None:
        return True
    neant = xml_text(element, "neant").lower()
    if neant in ("true", "1", "oui"):
        return True
    # Section vide si aucun enfant
    return len(list(element)) == 0


def find_items_in_section(section: ET.Element) -> list[ET.Element]:
    """Trouve tous les éléments-items dans une section, quelle que soit la structure."""
    if section is None:
        return []

    # Chercher d'abord les balises "items" ou "item" directes
    for path in [".//items/items", ".//items", ".//item", ".//declaration"]:
        found = section.findall(path)
        # Filtrer pour ne garder que les éléments qui ont des données (pas les conteneurs)
        items = [e for e in found if len(list(e)) > 0 or e.text]
        if items:
            return items

    # En dernier recours : enfants directs de la section (si elle a plusieurs enfants)
    children = list(section)
    if len(children) > 1:
        return children

    # Si un seul enfant, prendre ses enfants
    if len(children) == 1:
        grandchildren = list(children[0])
        if grandchildren:
            return grandchildren

    return []


def parse_instrument_financier(item: ET.Element) -> Optional[dict]:
    nature_id = xml_text(item, "nature/id") or xml_text(item, "typeInstrument/id") or xml_text(item, "categorie/id")
    nature_label = xml_text(item, "nature/label") or xml_text(item, "typeInstrument/label") or xml_text(item, "categorie/label") or nature_id

    valeur_str = (xml_text(item, "valeur") or xml_text(item, "valeurEstimee") or
                  xml_text(item, "montant") or xml_text(item, "valeurTotale") or
                  xml_text(item, "valeurNominale"))

    description = (xml_text(item, "description") or xml_text(item, "denomination") or
                   xml_text(item, "libelle") or xml_text(item, "nomEmetteur") or
                   xml_text(item, "societe"))

    valeur = parse_montant(valeur_str)
    if not nature_label and not description and valeur is None:
        return None

    return {
        "type": "instrument_financier",
        "nature": nature_label,
        "nature_code": nature_id,
        "description": description,
        "valeur_euro": valeur,
        "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id"),
        "nombre_titres": xml_text(item, "nombreTitres") or xml_text(item, "nbTitres"),
        "isin": xml_text(item, "codeISIN") or xml_text(item, "isin"),
        "etablissement": xml_text(item, "etablissement") or xml_text(item, "nomEtablissement"),
    }


def parse_participation(item: ET.Element) -> Optional[dict]:
    nom_societe = (xml_text(item, "nomSociete") or xml_text(item, "denomination") or
                   xml_text(item, "raisonSociale") or xml_text(item, "organisme"))

    valeur_str = (xml_text(item, "valeurParts") or xml_text(item, "valeur") or
                  xml_text(item, "montant") or xml_text(item, "valeurEstimee") or
                  xml_text(item, "valeurTotale"))

    valeur = parse_montant(valeur_str)
    if not nom_societe and valeur is None:
        return None

    return {
        "type": "participation_financiere",
        "nom_societe": nom_societe,
        "forme_juridique": xml_text(item, "formeJuridique") or xml_text(item, "typeStructure/label"),
        "nb_parts": xml_text(item, "nbParts") or xml_text(item, "nombreParts"),
        "valeur_euro": valeur,
        "pourcentage_detention": xml_text(item, "pourcentage") or xml_text(item, "tauxDetention"),
        "siren": xml_text(item, "siren") or xml_text(item, "numeroSIREN"),
    }


def parse_bien_immobilier(item: ET.Element) -> Optional[dict]:
    nature = (xml_text(item, "nature/label") or xml_text(item, "nature/id") or
              xml_text(item, "typeBien/label") or xml_text(item, "categorie/label"))

    valeur_str = (xml_text(item, "valeur") or xml_text(item, "valeurEstimee") or
                  xml_text(item, "montant") or xml_text(item, "valeurVenale"))

    adresse = (xml_text(item, "adresse") or xml_text(item, "localisation") or
               xml_text(item, "commune") or xml_text(item, "pays"))

    valeur = parse_montant(valeur_str)
    if not nature and not adresse and valeur is None:
        return None

    return {
        "type": "bien_immobilier",
        "nature": nature,
        "adresse": adresse,
        "surface_m2": xml_text(item, "surface") or xml_text(item, "superficieM2"),
        "valeur_euro": valeur,
        "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id"),
        "date_acquisition": xml_text(item, "dateAcquisition") or xml_text(item, "dateAchat"),
        "usage": xml_text(item, "usage") or xml_text(item, "affectation"),
    }


def parse_pret(item: ET.Element) -> Optional[dict]:
    montant = parse_montant(xml_text(item, "montant") or xml_text(item, "montantEmprunte") or xml_text(item, "capitalEmprunte"))
    capital_restant = parse_montant(xml_text(item, "capitalRestantDu") or xml_text(item, "montantRestant") or xml_text(item, "solde"))

    if montant is None and capital_restant is None:
        return None

    return {
        "type": "pret_bancaire",
        "nature": xml_text(item, "nature/label") or xml_text(item, "typeCredit/label"),
        "etablissement": xml_text(item, "etablissement") or xml_text(item, "organisme"),
        "montant_emprunte_euro": montant,
        "capital_restant_du_euro": capital_restant,
        "objet": xml_text(item, "objet") or xml_text(item, "finalite"),
    }


def parse_autre_bien(item: ET.Element) -> Optional[dict]:
    valeur = parse_montant(xml_text(item, "valeur") or xml_text(item, "valeurEstimee") or xml_text(item, "montant"))
    nature = xml_text(item, "nature/label") or xml_text(item, "categorie/label") or xml_text(item, "type/label")
    description = xml_text(item, "description") or xml_text(item, "designation") or xml_text(item, "libelle")

    if not nature and not description and valeur is None:
        return None

    return {
        "type": "autre_bien",
        "nature": nature,
        "description": description,
        "valeur_euro": valeur,
    }


def parse_revenu(item: ET.Element) -> Optional[dict]:
    montant = parse_montant(xml_text(item, "montant") or xml_text(item, "montantAnnuel") or
                            xml_text(item, "remunerationAnnuelle") or xml_text(item, "remunerationBrute"))
    nature = xml_text(item, "nature/label") or xml_text(item, "typeActivite/label") or xml_text(item, "categorie/label")
    employeur = xml_text(item, "employeur") or xml_text(item, "source") or xml_text(item, "organisme")
    fonction = xml_text(item, "fonction") or xml_text(item, "activite") or xml_text(item, "poste")

    if not nature and not employeur and not fonction and montant is None:
        return None

    return {
        "type": "revenu",
        "nature": nature,
        "employeur": employeur,
        "fonction": fonction,
        "montant_annuel_euro": montant,
    }


def parse_mandat(item: ET.Element) -> Optional[dict]:
    nature = xml_text(item, "nature/label") or xml_text(item, "typeMandat/label") or xml_text(item, "type/label")
    fonction = xml_text(item, "fonction") or xml_text(item, "qualite") or xml_text(item, "titre")
    collectivite = xml_text(item, "collectivite") or xml_text(item, "organe") or xml_text(item, "institution")

    if not nature and not fonction and not collectivite:
        return None

    return {
        "type": "mandat_electif",
        "nature": nature,
        "fonction": fonction,
        "collectivite": collectivite,
        "date_debut": xml_text(item, "dateDebut"),
        "date_fin": xml_text(item, "dateFin"),
    }


def parse_fonction(item: ET.Element) -> Optional[dict]:
    fonction = xml_text(item, "fonction") or xml_text(item, "titre") or xml_text(item, "poste")
    organisme = xml_text(item, "organisme") or xml_text(item, "structure") or xml_text(item, "denomination")

    if not fonction and not organisme:
        return None

    return {
        "type": "fonction_dirigeante",
        "fonction": fonction,
        "organisme": organisme,
        "remuneree": xml_bool(item, "remuneree"),
        "montant_annuel_euro": parse_montant(xml_text(item, "montant")),
    }


def parse_items_section(section: ET.Element, parser) -> list:
    """Parse générique d'une section XML."""
    if is_empty_section(section):
        return []

    items_found = find_items_in_section(section)
    results = []
    for elem in items_found:
        try:
            parsed = parser(elem)
            if parsed:
                results.append(parsed)
        except Exception:
            pass
    return results


def parse_xml_declaration(xml_bytes: bytes, url: str) -> Optional[dict]:
    """Parse complet d'un XML HATVP."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"\n[XML] Erreur parse : {e} ({url})", file=sys.stderr)
        return None

    # Supprimer les namespaces pour simplifier les chemins
    for elem in root.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]

    result = {
        "url_xml": url,
        "type_declaration": xml_text(root, ".//general/typeDeclaration/id") or xml_text(root, ".//typeDeclaration/id"),
        "date_depot": xml_text(root, ".//dateDepot") or xml_text(root, ".//dateDeclaration"),
    }

    # Sections à parser — chemins XML HATVP connus
    sections_config = [
        # (xpath_section, parser_func, clé_résultat)
        (".//instrumentsFinanciersDto", parse_instrument_financier, "instruments_financiers"),
        (".//instrumentsFinanciers",    parse_instrument_financier, "instruments_financiers"),
        (".//participationFinanciereDto", parse_participation,      "participations_financieres"),
        (".//participationsFinancieres",  parse_participation,      "participations_financieres"),
        (".//participationFinanciere",    parse_participation,      "participations_financieres"),
        (".//biensImmobiliersDto",       parse_bien_immobilier,     "biens_immobiliers"),
        (".//biensImmobiliers",          parse_bien_immobilier,     "biens_immobiliers"),
        (".//pretsBancairesDto",         parse_pret,                "prets_bancaires"),
        (".//pretsBancaires",            parse_pret,                "prets_bancaires"),
        (".//autresBiensDto",            parse_autre_bien,          "autres_biens"),
        (".//autresBiens",               parse_autre_bien,          "autres_biens"),
        (".//revenusDto",                parse_revenu,              "revenus"),
        (".//revenus",                   parse_revenu,              "revenus"),
        (".//activitesRemunerees",       parse_revenu,              "activites"),
        (".//activitesProfessionnelles", parse_revenu,              "activites"),
        (".//mandatsElectifsDto",        parse_mandat,              "mandats_electifs"),
        (".//mandatsElectifs",           parse_mandat,              "mandats_electifs"),
        (".//fonctionsDto",              parse_fonction,            "fonctions_dirigeantes"),
        (".//fonctionsDirigeantes",      parse_fonction,            "fonctions_dirigeantes"),
        (".//fonctionsBenevolesDto",     parse_fonction,            "fonctions_dirigeantes"),
    ]

    seen_sections = set()  # éviter doublons si deux xpath pointent sur la même section
    for xpath, parser, key in sections_config:
        section = root.find(xpath)
        if section is None:
            continue
        section_id = id(section)
        if section_id in seen_sections:
            continue
        seen_sections.add(section_id)

        items = parse_items_section(section, parser)
        if key in result:
            result[key].extend(items)
        else:
            result[key] = items

    # Famille / conjoint
    for conj_path in [".//conjoint", ".//declarantConjoint", ".//situationFamiliale"]:
        conjoint_section = root.find(conj_path)
        if conjoint_section is not None:
            result["famille"] = {
                "conjoint": {
                    "nom": xml_text(conjoint_section, "nom"),
                    "prenom": xml_text(conjoint_section, "prenom"),
                    "profession": xml_text(conjoint_section, "profession") or xml_text(conjoint_section, "activiteProfessionnelle"),
                }
            }
            break

    # Enfants
    enfants = root.findall(".//enfants/enfants") or root.findall(".//enfant")
    result["nb_enfants"] = len(enfants)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Calculs patrimoine
# ══════════════════════════════════════════════════════════════════════════════

def calculate_patrimoine(data: dict) -> dict:
    instruments = data.get("instruments_financiers", [])
    participations = data.get("participations_financieres", [])
    immobilier = data.get("biens_immobiliers", [])
    prets = data.get("prets_bancaires", [])
    autres_biens = data.get("autres_biens", [])
    revenus = data.get("revenus", []) + data.get("activites", [])

    val_instruments = sum(i.get("valeur_euro") or 0 for i in instruments)
    val_participations = sum(p.get("valeur_euro") or 0 for p in participations)
    val_immobilier = sum(b.get("valeur_euro") or 0 for b in immobilier)
    val_autres = sum(b.get("valeur_euro") or 0 for b in autres_biens)
    total_dettes = sum(p.get("capital_restant_du_euro") or 0 for p in prets)
    revenus_annuels = sum(r.get("montant_annuel_euro") or 0 for r in revenus)

    patrimoine_brut = val_instruments + val_participations + val_immobilier + val_autres
    patrimoine_net = patrimoine_brut - total_dettes

    def r(v): return round(v, 2) if v else 0

    return {
        "patrimoine_brut_euro": r(patrimoine_brut),
        "patrimoine_net_euro": r(patrimoine_net),
        "valeur_instruments_euro": r(val_instruments),
        "valeur_participations_euro": r(val_participations),
        "valeur_immobilier_euro": r(val_immobilier),
        "valeur_autres_biens_euro": r(val_autres),
        "total_dettes_euro": r(total_dettes),
        "revenus_annuels_euro": r(revenus_annuels),
        "nb_instruments_financiers": len(instruments),
        "nb_participations_societes": len(participations),
        "nb_biens_immobiliers": len(immobilier),
        "nb_prets_bancaires": len(prets),
        "nb_autres_biens": len(autres_biens),
        "nb_revenus_activites": len(revenus),
        "nb_mandats_electifs": len(data.get("mandats_electifs", [])),
        "nb_fonctions_dirigeantes": len(data.get("fonctions_dirigeantes", [])),
        "a_conjoint": bool(data.get("famille", {}).get("conjoint", {}).get("nom")),
        "nb_enfants": data.get("nb_enfants", 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Traitement d'un élu
# ══════════════════════════════════════════════════════════════════════════════

def process_elu(elu: dict, index: list[dict], force: bool, delay: float) -> Optional[dict]:
    prenom = elu.get("prenom", "").strip()
    nom = elu.get("nom", "").strip()

    if not prenom or not nom:
        return None

    declarations_rows = find_declarations(index, prenom, nom)
    if not declarations_rows:
        return None

    # Filtrer uniquement les types voulus
    wanted_rows = [r for r in declarations_rows if get_declaration_type(r) in WANTED_TYPES]
    if not wanted_rows:
        return None

    dsp_row = next((r for r in wanted_rows if get_declaration_type(r) in DSP_TYPES), None)
    di_row = next((r for r in wanted_rows if get_declaration_type(r) in DI_TYPES), None)

    consolidated = {
        "instruments_financiers": [],
        "participations_financieres": [],
        "biens_immobiliers": [],
        "prets_bancaires": [],
        "autres_biens": [],
        "revenus": [],
        "activites": [],
        "mandats_electifs": [],
        "fonctions_dirigeantes": [],
        "famille": {},
        "nb_enfants": 0,
        "declarations": [],
    }

    nb_declarations_total = len(declarations_rows)

    for row in [dsp_row, di_row]:
        if row is None:
            continue

        xml_url = get_xml_url(row)
        if not xml_url:
            continue

        filename = xml_url.split("/")[-1]
        if not filename.endswith(".xml"):
            filename += ".xml"
        cache_path = os.path.join(CACHE_DIR, "xmls", filename)

        xml_bytes = download_with_cache(xml_url, cache_path, force=force, delay=delay)
        if not xml_bytes:
            continue

        parsed = parse_xml_declaration(xml_bytes, xml_url)
        if not parsed:
            continue

        for key in ["instruments_financiers", "participations_financieres", "biens_immobiliers",
                    "prets_bancaires", "autres_biens", "revenus", "activites",
                    "mandats_electifs", "fonctions_dirigeantes"]:
            if key in parsed:
                consolidated[key].extend(parsed[key])

        if parsed.get("famille"):
            consolidated["famille"] = parsed["famille"]
        if parsed.get("nb_enfants", 0) > consolidated["nb_enfants"]:
            consolidated["nb_enfants"] = parsed["nb_enfants"]

        consolidated["declarations"].append({
            "type": parsed.get("type_declaration", get_declaration_type(row)),
            "date_depot": parsed.get("date_depot", get_row_field(row, "dateDepot", "DateDepot")),
            "url": xml_url,
        })

    if not consolidated["declarations"]:
        return None

    patrimoine = calculate_patrimoine(consolidated)

    # Structure compatible avec elus.json → hatvp_complete
    hatvp_complete = {
        **patrimoine,
        "nb_declarations_hatvp": nb_declarations_total,
        "hatvp_scraped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "declarations": consolidated["declarations"],
    }

    # Détails patrimoine (toutes les données, sans limite arbitraire)
    if any([
        consolidated["instruments_financiers"],
        consolidated["biens_immobiliers"],
        consolidated["participations_financieres"],
        consolidated["prets_bancaires"],
        consolidated["autres_biens"],
    ]):
        hatvp_complete["patrimoine_details"] = {
            "instruments_financiers": consolidated["instruments_financiers"],
            "biens_immobiliers": consolidated["biens_immobiliers"],
            "participations_financieres": consolidated["participations_financieres"],
            "prets_bancaires": consolidated["prets_bancaires"],
            "autres_biens": consolidated["autres_biens"],
        }

    if consolidated["revenus"] or consolidated["activites"]:
        hatvp_complete["revenus_details"] = consolidated["revenus"] + consolidated["activites"]

    if consolidated["mandats_electifs"]:
        hatvp_complete["mandats_details"] = consolidated["mandats_electifs"]

    if consolidated["fonctions_dirigeantes"]:
        hatvp_complete["fonctions_details"] = consolidated["fonctions_dirigeantes"]

    return hatvp_complete


# ══════════════════════════════════════════════════════════════════════════════
# I/O elus.json
# ══════════════════════════════════════════════════════════════════════════════

def load_elus() -> list[dict]:
    if not os.path.exists(OUTPUT_JSON):
        print(f"⚠ {OUTPUT_JSON} introuvable")
        return []
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def save_elus(elus: list[dict], backup: bool = True) -> None:
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    if backup and os.path.exists(OUTPUT_JSON):
        backup_path = OUTPUT_JSON + f".backup.{int(time.time())}"
        import shutil
        shutil.copy2(OUTPUT_JSON, backup_path)

    tmp_path = OUTPUT_JSON + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(elus, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, OUTPUT_JSON)
    print(f"✓ Sauvegardé : {OUTPUT_JSON}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(description="Extraction HATVP v3 - données élus français")
    p.add_argument("--limit", type=int, help="Limiter le nombre d'élus traités")
    p.add_argument("--force", action="store_true", help="Forcer re-téléchargement XMLs")
    p.add_argument("--delay", type=float, default=0.3, help="Délai entre requêtes (secondes)")
    p.add_argument("--test-elu", type=str, help='Tester un élu : "Prénom NOM" ou "NOM Prénom"')
    p.add_argument("--refresh-index", action="store_true", help="Re-télécharger l'index CSV")
    p.add_argument("--skip-existing", action="store_true", help="Passer les élus déjà enrichis (patrimoine > 0)")
    p.add_argument("--debug-csv", action="store_true", help="Afficher la structure du CSV HATVP et quitter")
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 80)
    print("💰 EXTRACTION HATVP v3")
    print("=" * 80)

    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.join(CACHE_DIR, "xmls"), exist_ok=True)

    try:
        index = load_hatvp_index(force_refresh=args.refresh_index)
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return

    # Mode debug CSV
    if args.debug_csv:
        debug_csv(index, n=10)
        return

    # Mode test élu unique
    if args.test_elu:
        print(f"\n🧪 MODE TEST : {args.test_elu}")

        # Parser "Prénom NOM" ou "NOM Prénom"
        parts = args.test_elu.strip().split()
        if len(parts) < 2:
            print("❌ Format attendu : 'Prénom NOM' ou 'NOM Prénom'")
            return

        # Essayer les deux ordres
        test_cases = [
            {"prenom": parts[0], "nom": " ".join(parts[1:])},
            {"prenom": " ".join(parts[:-1]), "nom": parts[-1]},
        ]

        elu = None
        elus = load_elus()
        query_norm = normalize_name(args.test_elu)
        for e in elus:
            full = f"{e.get('prenom', '')} {e.get('nom', '')}"
            if normalize_name(full) == query_norm or normalize_name(args.test_elu) in normalize_name(full):
                elu = e
                break

        if not elu:
            elu = test_cases[0]
            print(f"  (élu non trouvé dans elus.json, utilisation directe: {elu})")

        # Essayer avec les deux ordres prénom/nom
        result = None
        for tc in test_cases:
            decls = find_declarations(index, tc["prenom"], tc["nom"])
            if decls:
                print(f"  ✓ Trouvé avec prénom='{tc['prenom']}' nom='{tc['nom']}' → {len(decls)} déclarations")
                for d in decls[:5]:
                    typ = get_declaration_type(d)
                    url = get_xml_url(d)
                    date = get_row_field(d, "dateDepot", "DateDepot")
                    print(f"    - Type: {typ:6s} | Date: {date:20s} | URL: {url}")
                result = process_elu({**elu, **tc}, index, force=True, delay=args.delay)
                break

        if result is None:
            print(f"\n✗ Aucune déclaration trouvée pour '{args.test_elu}'")
            print("\n  Essayez --debug-csv pour voir les colonnes du CSV")
            print("  Vérifiez l'orthographe exacte du nom dans le CSV HATVP")
        else:
            print("\n✅ RÉSULTAT :")
            print(f"  Patrimoine net  : {result.get('patrimoine_net_euro', 0):>12,.0f} €")
            print(f"  Patrimoine brut : {result.get('patrimoine_brut_euro', 0):>12,.0f} €")
            print(f"  Revenus annuels : {result.get('revenus_annuels_euro', 0):>12,.0f} €")
            print(f"  Instruments     : {result.get('nb_instruments_financiers', 0)}")
            print(f"  Immobilier      : {result.get('nb_biens_immobiliers', 0)}")
            print(f"  Participations  : {result.get('nb_participations_societes', 0)}")
            print(f"  Déclarations    : {len(result.get('declarations', []))}")

            test_path = os.path.join(CACHE_DIR, "test_result.json")
            with open(test_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Détails complets : {test_path}")
        return

    # Mode batch
    print("\n🔄 Traitement batch...")
    elus = load_elus()
    if not elus:
        print("❌ elus.json vide ou introuvable")
        return

    if args.limit:
        elus = elus[:args.limit]
        print(f"  Limité à {args.limit} élus")

    progress = ProgressTracker(len(elus))
    updated_count = 0

    for i, elu in enumerate(elus):
        prenom = elu.get("prenom", "")
        nom = elu.get("nom", "")
        elu_name = f"{prenom} {nom}"

        progress.print_progress(elu_name, "⏳")

        # Skip si déjà enrichi et patrimoine non nul
        if args.skip_existing:
            hc = elu.get("hatvp_complete", {})
            if hc.get("hatvp_scraped_at") and (hc.get("patrimoine_brut_euro", 0) > 0 or hc.get("nb_biens_immobiliers", 0) > 0):
                progress.update(not_found=True)
                continue

        try:
            result = process_elu(elu, index, force=args.force, delay=args.delay)

            if result:
                # Mettre à jour hatvp_complete (compatible avec la structure existante)
                if "hatvp_complete" not in elu:
                    elu["hatvp_complete"] = {}
                elu["hatvp_complete"].update(result)

                # Mettre à jour aussi les champs de premier niveau pour compatibilité
                if result.get("patrimoine_net_euro"):
                    elu["patrimoine"] = result["patrimoine_net_euro"]
                if result.get("valeur_immobilier_euro"):
                    elu["immobilier"] = result["valeur_immobilier_euro"]
                if result.get("revenus_annuels_euro"):
                    elu["revenus"] = result["revenus_annuels_euro"]

                progress.update(success=True)
                updated_count += 1

                pat = result.get("patrimoine_net_euro", 0) or 0
                rev = result.get("revenus_annuels_euro", 0) or 0
                progress.print_progress(elu_name, f"✓ {pat:>10,.0f}€ net  {rev:>8,.0f}€/an")
            else:
                progress.update(not_found=True)
                progress.print_progress(elu_name, "✗ non trouvé")

            # Sauvegarde incrémentale
            if (i + 1) % SAVE_INTERVAL == 0:
                progress.print_line(f"💾 Sauvegarde incrémentale ({updated_count} mis à jour)...")
                save_elus(elus, backup=False)

        except Exception as exc:
            progress.update(error=True)
            progress.print_progress(elu_name, f"⚠ {str(exc)[:40]}")

    # Sauvegarde finale
    print(f"\n\n💾 Sauvegarde finale...")
    save_elus(elus, backup=True)

    print("\n" + "=" * 80)
    print("📊 RAPPORT FINAL")
    print("=" * 80)
    print(f"  Total traités  : {progress.total}")
    print(f"  ✓ Mis à jour   : {progress.success}")
    print(f"  ✗ Non trouvés  : {progress.not_found}")
    print(f"  ⚠ Erreurs      : {progress.errors}")
    print(f"  Temps total    : {int((time.time() - progress.start_time) / 60)}m{int((time.time() - progress.start_time) % 60)}s")
    print("=" * 80)


if __name__ == "__main__":
    main()
