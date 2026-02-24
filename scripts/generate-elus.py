#!/usr/bin/env python3
"""
Script de récupération des déclarations HATVP complètes des élus français.

Lit le fichier index officiel HATVP (liste.csv), télécharge les XMLs
correspondant à chaque élu et extrait TOUTES les sections patrimoniales :
  - instruments financiers (actions, obligations, ETF, PEA, assurance-vie…)
  - participations financières dans des sociétés (cotées ou non)
  - biens immobiliers (résidence principale, secondaire, locatifs…)
  - comptes bancaires et livrets d'épargne
  - véhicules (voitures, bateaux, avions…)
  - autres biens mobiliers (œuvres d'art, bijoux, chevaux…)
  - dettes et emprunts
  - revenus (salaires, revenus locatifs, jetons de présence…)
  - activités professionnelles et mandats (DI)
  - autres liens d'intérêts (DI)

Sources :
  Index CSV  : https://www.hatvp.fr/livraison/opendata/liste.csv
  XMLs       : https://www.hatvp.fr/livraison/dossiers/{fichier}.xml
  Doc xlsx   : https://www.data.gouv.fr/api/1/datasets/r/f99ea4c7-ddf4-484b-b7de-ea4419c9f865

Utilisation :
  python generate-elus.py --dry-run
  python generate-elus.py --limit 50
  python generate-elus.py --test-elu "Yaël Braun-Pivet"
  python generate-elus.py --force
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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")
CACHE_DIR = os.path.join(PROJECT_ROOT, "public", "data", "hatvp_cache")
INDEX_CACHE = os.path.join(CACHE_DIR, "liste.csv")

# ── URLs HATVP open data ───────────────────────────────────────────────────────
HATVP_INDEX_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"
HATVP_XML_BASE  = "https://www.hatvp.fr/livraison/dossiers/"

# ── Types de déclaration ───────────────────────────────────────────────────────
# DSP  = Déclaration de Situation Patrimoniale (initiale)
# DSPM = DSP Modificative
# DI   = Déclaration d'Intérêts (initiale)
# DIM  = DI Modificative
WANTED_TYPES = {"DSP", "DSPM", "DI", "DIM"}
DSP_TYPES    = {"DSP", "DSPM"}
DI_TYPES     = {"DI",  "DIM"}

# ── Headers HTTP ──────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (open source)",
    "Accept": "text/csv, application/xml, text/xml, */*",
}


# ══════════════════════════════════════════════════════════════════════════════
# Parsing args
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Extrait le patrimoine complet (DSP + DI) depuis les XMLs HATVP."
    )
    p.add_argument("--dry-run",       action="store_true", help="Ne pas écrire de fichiers")
    p.add_argument("--force",         action="store_true", help="Re-télécharger même si en cache")
    p.add_argument("--limit",         type=int,   default=None, help="Limiter le nombre d'élus")
    p.add_argument("--delay",         type=float, default=0.5,  help="Délai entre requêtes (défaut 0.5 s)")
    p.add_argument("--test-elu",      type=str,   default=None, help="Tester un élu précis")
    p.add_argument("--refresh-index", action="store_true",
                   help="Forcer le re-téléchargement du CSV index HATVP")
    return p.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
# Réseau
# ══════════════════════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 30) -> bytes | None:
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


# ══════════════════════════════════════════════════════════════════════════════
# Chargement de l'index CSV HATVP
# ══════════════════════════════════════════════════════════════════════════════

def load_hatvp_index(force_refresh: bool = False, delay: float = 0.5) -> list[dict]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    raw = None

    if not force_refresh and os.path.exists(INDEX_CACHE):
        age_h = (time.time() - os.path.getmtime(INDEX_CACHE)) / 3600
        if age_h < 24:
            print(f"  ✓ Index CSV en cache (âge : {age_h:.1f} h)")
            with open(INDEX_CACHE, "rb") as f:
                raw = f.read()
        else:
            print(f"  ↻ Cache trop ancien ({age_h:.1f} h), re-téléchargement…")

    if raw is None:
        print(f"  🔄 Téléchargement index HATVP : {HATVP_INDEX_URL}")
        time.sleep(delay)
        raw = http_get(HATVP_INDEX_URL)
        if not raw:
            raise RuntimeError(f"Impossible de télécharger l'index HATVP : {HATVP_INDEX_URL}")
        with open(INDEX_CACHE, "wb") as f:
            f.write(raw)
        print(f"  ✓ Index téléchargé ({len(raw):,} octets) et mis en cache")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    print(f"  ✓ {len(rows):,} déclarations dans l'index")
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# Correspondance élu ↔ déclarations HATVP
# ══════════════════════════════════════════════════════════════════════════════

def normalize_name(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[-\s]+", " ", s).strip()
    return s


def find_declarations_for_elu(index: list[dict], prenom: str, nom: str) -> list[dict]:
    norm_prenom = normalize_name(prenom)
    norm_nom    = normalize_name(nom)
    matched = []
    for row in index:
        row_nom    = (row.get("nom")    or row.get("Nom")    or row.get("NOM")    or row.get("nomDeclarant")    or "").strip()
        row_prenom = (row.get("prenom") or row.get("Prenom") or row.get("PRENOM") or row.get("prenomDeclarant") or "").strip()
        if not row_nom:
            continue
        if normalize_name(row_nom) == norm_nom and normalize_name(row_prenom) == norm_prenom:
            matched.append(row)

    def parse_date(row):
        date_str = (row.get("dateDepot") or row.get("DateDepot") or row.get("date_depot") or "")
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return datetime.min

    matched.sort(key=parse_date, reverse=True)
    return matched


def get_xml_url(row: dict) -> str | None:
    url = (row.get("url") or row.get("Url") or row.get("URL") or row.get("urlFichier") or row.get("lien") or "").strip()
    if url.startswith("http"):
        return url
    fichier = (row.get("fichier") or row.get("Fichier") or row.get("nomFichier") or url).strip()
    if fichier:
        if not fichier.endswith(".xml"):
            fichier += ".xml"
        return HATVP_XML_BASE + fichier
    return None


def get_declaration_type(row: dict) -> str:
    return (row.get("typeDeclaration") or row.get("TypeDeclaration") or row.get("type") or row.get("Type") or "").strip().upper()


# ══════════════════════════════════════════════════════════════════════════════
# Téléchargement XML
# ══════════════════════════════════════════════════════════════════════════════

def download_xml(url: str, cache_path: str, force: bool = False, delay: float = 0.5) -> bytes | None:
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
# Helpers XML
# ══════════════════════════════════════════════════════════════════════════════

def xml_text(element, path: str, default: str = "") -> str:
    if element is None:
        return default
    node = element.find(path)
    if node is not None and node.text:
        t = node.text.strip()
        if t and t != "[Données non publiées]":
            return t
    return default


def parse_montant(s: str) -> float | None:
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def items_of(section: ET.Element) -> list[ET.Element]:
    """Retourne la liste des <items> enfants d'une section, en gérant l'imbrication."""
    if section is None:
        return []
    result = section.findall(".//items/items")
    if not result:
        result = section.findall("items")
    # Filtrer les conteneurs vides (aucun enfant avec du texte)
    return [el for el in result if any(child.text for child in el)]


def is_neant(section: ET.Element) -> bool:
    return xml_text(section, "neant").lower() == "true"


# ══════════════════════════════════════════════════════════════════════════════
# Parsers par section DSP
# ══════════════════════════════════════════════════════════════════════════════

def parse_instruments_financiers(root: ET.Element) -> list[dict]:
    """Actions, obligations, ETF, PEA, assurance-vie, OPCVM…"""
    section = root.find(".//instrumentsFinanciersDto")
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        nature_id    = xml_text(item, "nature/id")    or xml_text(item, "typeInstrument/id")    or ""
        nature_label = xml_text(item, "nature/label") or xml_text(item, "typeInstrument/label") or nature_id
        valeur_str   = xml_text(item, "valeur") or xml_text(item, "valeurEstimee") or xml_text(item, "montant") or ""
        entry = {
            "nature":        nature_label or nature_id,
            "nature_code":   nature_id,
            "description":   xml_text(item, "description") or xml_text(item, "denomination") or xml_text(item, "libelle") or "",
            "valeur_euro":   parse_montant(valeur_str),
            "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id") or "",
            "commentaire":   xml_text(item, "commentaire"),
        }
        nb = xml_text(item, "nombreTitres") or xml_text(item, "nbTitres")
        if nb:
            entry["nb_titres"] = nb
        vu = xml_text(item, "valeurUnitaire")
        if vu:
            entry["valeur_unitaire_euro"] = parse_montant(vu)
        if not entry["nature"] and not entry["description"] and entry["valeur_euro"] is None:
            continue
        result.append(entry)
    return result


def parse_participations_financieres(root: ET.Element) -> list[dict]:
    """Parts dans des sociétés (SARL, SCI, SA non cotées���)."""
    section = root.find(".//participationFinanciereDto")
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        nom_societe = xml_text(item, "nomSociete") or xml_text(item, "denomination") or ""
        valeur_str  = xml_text(item, "valeurParts") or xml_text(item, "valeur") or xml_text(item, "montant") or ""
        entry = {
            "nom_societe":   nom_societe,
            "nb_parts":      xml_text(item, "nbParts") or xml_text(item, "nombreParts") or "",
            "valeur_euro":   parse_montant(valeur_str),
            "pourcentage":   xml_text(item, "pourcentage") or xml_text(item, "tauxDetention") or "",
            "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id") or "",
            "objet_social":  xml_text(item, "objetSocial") or xml_text(item, "activite") or "",
            "commentaire":   xml_text(item, "commentaire"),
        }
        if not entry["nom_societe"] and entry["valeur_euro"] is None:
            continue
        result.append(entry)
    return result


def parse_biens_immobiliers(root: ET.Element) -> list[dict]:
    """Résidence principale, secondaire, biens locatifs, terrains, forêts…"""
    # Plusieurs noms de section possibles selon la version du schéma
    section = (
        root.find(".//biensImmobiliersDto") or
        root.find(".//bienImmobilierDto")   or
        root.find(".//immobilierDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        valeur_str = (
            xml_text(item, "valeurVenale") or
            xml_text(item, "valeur")       or
            xml_text(item, "valeurEstimee") or
            xml_text(item, "montant")      or ""
        )
        entry = {
            "nature":          xml_text(item, "nature/label")  or xml_text(item, "nature/id")  or xml_text(item, "typeBien/label") or xml_text(item, "typeBien/id") or "",
            "description":     xml_text(item, "description")   or xml_text(item, "adresse")    or xml_text(item, "localisation") or "",
            "localisation":    xml_text(item, "localisation")  or xml_text(item, "commune")    or xml_text(item, "departement") or "",
            "valeur_euro":     parse_montant(valeur_str),
            "surface_m2":      xml_text(item, "surface")       or xml_text(item, "superficie") or "",
            "mode_acquisition": xml_text(item, "modeAcquisition/label") or xml_text(item, "modeAcquisition/id") or "",
            "mode_detention":  xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id") or "",
            "revenu_locatif_euro": parse_montant(xml_text(item, "revenuLocatif") or xml_text(item, "loyersAnnuels") or ""),
            "commentaire":     xml_text(item, "commentaire"),
        }
        if not entry["nature"] and not entry["description"] and entry["valeur_euro"] is None:
            continue
        result.append(entry)
    return result


def parse_comptes_bancaires(root: ET.Element) -> list[dict]:
    """Comptes courants, livrets, PEL, CEL, PEP…"""
    section = (
        root.find(".//comptesBancairesDto") or
        root.find(".//compteBancaireDto")   or
        root.find(".//liquiditesDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        valeur_str = xml_text(item, "solde") or xml_text(item, "valeur") or xml_text(item, "montant") or ""
        entry = {
            "type_compte":  xml_text(item, "typeCompte/label") or xml_text(item, "typeCompte/id") or xml_text(item, "nature/label") or xml_text(item, "nature/id") or "",
            "etablissement": xml_text(item, "etablissement") or xml_text(item, "banque") or "",
            "solde_euro":   parse_montant(valeur_str),
            "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id") or "",
            "commentaire":  xml_text(item, "commentaire"),
        }
        if not entry["type_compte"] and entry["solde_euro"] is None:
            continue
        result.append(entry)
    return result


def parse_vehicules(root: ET.Element) -> list[dict]:
    """Voitures, motos, bateaux, avions de tourisme…"""
    section = (
        root.find(".//vehiculesDto")  or
        root.find(".//vehiculeDto")   or
        root.find(".//biensVehicules")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        valeur_str = xml_text(item, "valeur") or xml_text(item, "valeurEstimee") or xml_text(item, "montant") or ""
        entry = {
            "type_vehicule": xml_text(item, "typeVehicule/label") or xml_text(item, "typeVehicule/id") or xml_text(item, "nature/label") or xml_text(item, "nature/id") or "",
            "description":   xml_text(item, "description") or xml_text(item, "marque") or xml_text(item, "modele") or "",
            "annee":         xml_text(item, "annee") or xml_text(item, "dateAcquisition") or "",
            "valeur_euro":   parse_montant(valeur_str),
            "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id") or "",
            "commentaire":   xml_text(item, "commentaire"),
        }
        if not entry["type_vehicule"] and not entry["description"] and entry["valeur_euro"] is None:
            continue
        result.append(entry)
    return result


def parse_biens_mobiliers(root: ET.Element) -> list[dict]:
    """Meubles de valeur, œuvres d'art, bijoux, métaux précieux, chevaux de course…"""
    section = (
        root.find(".//autresBiensDto")      or
        root.find(".//biensMobiliersDto")   or
        root.find(".//biensValeurDto")      or
        root.find(".//mobilierDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        valeur_str = xml_text(item, "valeur") or xml_text(item, "valeurEstimee") or xml_text(item, "montant") or ""
        entry = {
            "nature":      xml_text(item, "nature/label") or xml_text(item, "nature/id") or xml_text(item, "typeBien/label") or xml_text(item, "typeBien/id") or "",
            "description": xml_text(item, "description") or xml_text(item, "libelle") or "",
            "valeur_euro": parse_montant(valeur_str),
            "commentaire": xml_text(item, "commentaire"),
        }
        if not entry["nature"] and not entry["description"] and entry["valeur_euro"] is None:
            continue
        result.append(entry)
    return result


def parse_dettes(root: ET.Element) -> list[dict]:
    """Emprunts immobiliers, crédits à la consommation, autres dettes…"""
    section = (
        root.find(".//dettesDto")   or
        root.find(".//detteDto")    or
        root.find(".//empruntsDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        valeur_str = (
            xml_text(item, "capitalRestantDu") or
            xml_text(item, "montantRestant")   or
            xml_text(item, "valeur")           or
            xml_text(item, "montant")          or ""
        )
        entry = {
            "nature":        xml_text(item, "nature/label")       or xml_text(item, "nature/id")  or xml_text(item, "objet") or "",
            "creancier":     xml_text(item, "creancier")          or xml_text(item, "organisme")  or xml_text(item, "banque") or "",
            "montant_euro":  parse_montant(valeur_str),
            "taux":          xml_text(item, "taux")               or xml_text(item, "tauxInteret") or "",
            "echeance":      xml_text(item, "echeance")           or xml_text(item, "dateEcheance") or "",
            "commentaire":   xml_text(item, "commentaire"),
        }
        if not entry["nature"] and not entry["creancier"] and entry["montant_euro"] is None:
            continue
        result.append(entry)
    return result


def parse_revenus(root: ET.Element) -> list[dict]:
    """Revenus professionnels, locatifs, mobiliers, jetons de présence, allocations…"""
    section = (
        root.find(".//revenusDto")        or
        root.find(".//revenuDto")         or
        root.find(".//revenusActiviteDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        montant_str = (
            xml_text(item, "montant")       or
            xml_text(item, "valeur")        or
            xml_text(item, "revenuAnnuel")  or
            xml_text(item, "revenuNet")     or ""
        )
        entry = {
            "nature":       xml_text(item, "nature/label")  or xml_text(item, "nature/id")  or xml_text(item, "typeRevenu/label") or xml_text(item, "typeRevenu/id") or "",
            "source":       xml_text(item, "source")        or xml_text(item, "employeur")  or xml_text(item, "organisme") or "",
            "montant_euro": parse_montant(montant_str),
            "periodicite":  xml_text(item, "periodicite")   or xml_text(item, "frequence")  or "",
            "commentaire":  xml_text(item, "commentaire"),
        }
        if not entry["nature"] and not entry["source"] and entry["montant_euro"] is None:
            continue
        result.append(entry)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Parsers par section DI
# ══════════════════════════════════════════════════════════════════════════════

def parse_activites_professionnelles(root: ET.Element) -> list[dict]:
    """Fonctions et emplois rémunérés actuels (DI)."""
    section = (
        root.find(".//activitesProfessionnellesDto") or
        root.find(".//activiteProfessionnelleDto")   or
        root.find(".//fonctionsActuellesDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        montant_str = xml_text(item, "remuneration") or xml_text(item, "revenu") or xml_text(item, "montant") or ""
        entry = {
            "employeur":     xml_text(item, "employeur")    or xml_text(item, "organisme")    or xml_text(item, "entreprise") or "",
            "fonction":      xml_text(item, "fonction")     or xml_text(item, "poste")         or xml_text(item, "qualite") or "",
            "date_debut":    xml_text(item, "dateDebut")    or xml_text(item, "dateNomination") or "",
            "date_fin":      xml_text(item, "dateFin")      or "",
            "remuneration_euro": parse_montant(montant_str),
            "type_activite": xml_text(item, "typeActivite/label") or xml_text(item, "typeActivite/id") or "",
            "commentaire":   xml_text(item, "commentaire"),
        }
        if not entry["employeur"] and not entry["fonction"]:
            continue
        result.append(entry)
    return result


def parse_activites_anterieures(root: ET.Element) -> list[dict]:
    """Fonctions et emplois exercés dans les 5 dernières années (DI)."""
    section = (
        root.find(".//activitesAnterieuresDto")    or
        root.find(".//activiteAnterieureDto")      or
        root.find(".//fonctionsAnterieuresDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        entry = {
            "employeur":     xml_text(item, "employeur")  or xml_text(item, "organisme") or xml_text(item, "entreprise") or "",
            "fonction":      xml_text(item, "fonction")   or xml_text(item, "poste")     or xml_text(item, "qualite") or "",
            "date_debut":    xml_text(item, "dateDebut")  or "",
            "date_fin":      xml_text(item, "dateFin")    or "",
            "type_activite": xml_text(item, "typeActivite/label") or xml_text(item, "typeActivite/id") or "",
            "commentaire":   xml_text(item, "commentaire"),
        }
        if not entry["employeur"] and not entry["fonction"]:
            continue
        result.append(entry)
    return result


def parse_mandats_elus(root: ET.Element) -> list[dict]:
    """Mandats et fonctions électifs exercés (DI)."""
    section = (
        root.find(".//mandatsElectifsDto") or
        root.find(".//mandatElectifDto")   or
        root.find(".//mandatsDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        montant_str = xml_text(item, "indemnite") or xml_text(item, "remuneration") or xml_text(item, "montant") or ""
        entry = {
            "mandat":       xml_text(item, "typeMandat/label") or xml_text(item, "typeMandat/id") or xml_text(item, "mandat") or "",
            "collectivite": xml_text(item, "collectivite")     or xml_text(item, "organisme")     or xml_text(item, "institution") or "",
            "date_debut":   xml_text(item, "dateDebut")        or "",
            "date_fin":     xml_text(item, "dateFin")          or "",
            "indemnite_euro": parse_montant(montant_str),
            "commentaire":  xml_text(item, "commentaire"),
        }
        if not entry["mandat"] and not entry["collectivite"]:
            continue
        result.append(entry)
    return result


def parse_participations_organes(root: ET.Element) -> list[dict]:
    """Participations à des organes délibérants, conseils d'administration, comités (DI)."""
    section = (
        root.find(".//participationsOrganeDto")     or
        root.find(".//participationOrganeDto")      or
        root.find(".//organesDirigeantsDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        montant_str = xml_text(item, "remuneration") or xml_text(item, "jeton") or xml_text(item, "indemnite") or ""
        entry = {
            "organisme":    xml_text(item, "organisme")  or xml_text(item, "denomination") or "",
            "fonction":     xml_text(item, "fonction")   or xml_text(item, "qualite")      or "",
            "date_debut":   xml_text(item, "dateDebut")  or "",
            "date_fin":     xml_text(item, "dateFin")    or "",
            "remuneration_euro": parse_montant(montant_str),
            "commentaire":  xml_text(item, "commentaire"),
        }
        if not entry["organisme"] and not entry["fonction"]:
            continue
        result.append(entry)
    return result


def parse_soutiens_associations(root: ET.Element) -> list[dict]:
    """Activités bénévoles / soutien à des associations (DI)."""
    section = (
        root.find(".//soutiensAssociationsDto") or
        root.find(".//soutienAssociationDto")   or
        root.find(".//activitesBenevolesDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        entry = {
            "association":  xml_text(item, "association") or xml_text(item, "organisme") or xml_text(item, "denomination") or "",
            "objet":        xml_text(item, "objet")       or xml_text(item, "activite")  or "",
            "fonction":     xml_text(item, "fonction")    or xml_text(item, "qualite")   or "",
            "commentaire":  xml_text(item, "commentaire"),
        }
        if not entry["association"] and not entry["objet"]:
            continue
        result.append(entry)
    return result


def parse_autres_liens_interets(root: ET.Element) -> list[dict]:
    """Autres liens susceptibles de créer un conflit d'intérêts (DI)."""
    section = (
        root.find(".//autresLiensInteretsDto") or
        root.find(".//autreLienInteretDto")    or
        root.find(".//liensInteretsDto")
    )
    if section is None or is_neant(section):
        return []
    result = []
    for item in items_of(section):
        entry = {
            "nature":      xml_text(item, "nature/label") or xml_text(item, "nature/id") or xml_text(item, "typeInteraction/label") or "",
            "description": xml_text(item, "description")  or xml_text(item, "libelle")   or "",
            "commentaire": xml_text(item, "commentaire"),
        }
        if not entry["nature"] and not entry["description"]:
            continue
        result.append(entry)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Parser principal : toutes sections d'une déclaration XML
# ══════════════════════════════════════════════════════════════════════════════

def parse_declaration_xml(xml_bytes: bytes, url: str) -> dict:
    """
    Parser un XML de déclaration HATVP et extraire TOUTES les données disponibles.
    Retourne un dict structuré avec les sections triées.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        print(f"    ⚠ XML invalide ({exc}) : {url}")
        return {}

    # ── Métadonnées générales ──────────────────────────────────────────────────
    type_decl_id    = xml_text(root, "general/typeDeclaration/id")    or ""
    type_decl_label = xml_text(root, "general/typeDeclaration/label") or type_decl_id
    date_depot      = xml_text(root, "dateDepot")
    uuid            = xml_text(root, "uuid")
    declarant_nom   = xml_text(root, "general/declarant/nom")
    declarant_prenom= xml_text(root, "general/declarant/prenom")
    qualite         = xml_text(root, "general/qualiteDeclarant")
    organe          = xml_text(root, "general/organe/labelOrgane")
    mandat          = xml_text(root, "general/qualiteMandat/labelTypeMandat")

    result = {
        "uuid":                    uuid,
        "url_xml":                 url,
        "type_declaration":        type_decl_id,
        "type_declaration_label":  type_decl_label,
        "date_depot":              date_depot,
        "declarant":               f"{declarant_prenom} {declarant_nom}".strip(),
        "qualite":                 qualite,
        "organe":                  organe,
        "mandat":                  mandat,
        # ── Patrimoine (DSP) ───────────────────────────────────────────────────
        "instruments_financiers":      [],   # actions, ETF, PEA, assurance-vie…
        "participations_financieres":  [],   # parts dans des sociétés
        "biens_immobiliers":           [],   # résidence, locatif, terrain…
        "comptes_bancaires":           [],   # courant, livret, PEL…
        "vehicules":                   [],   # voiture, bateau, avion…
        "biens_mobiliers_valeur":      [],   # œuvres d'art, bijoux…
        "dettes":                      [],   # emprunts, crédits
        "revenus":                     [],   # salaires, revenus locatifs…
        # ── Intérêts (DI) ─────────────────────────────────────────────────────
        "activites_professionnelles":  [],   # emplois actuels
        "activites_anterieures":       [],   # emplois 5 dernières années
        "mandats_electifs":            [],   # mandats & fonctions électives
        "participations_organes":      [],   # CA, comités, conseils…
        "soutiens_associations":       [],   # bénévolat
        "autres_liens_interets":       [],   # autres conflits potentiels
    }

    # ── Sections patrimoniales (DSP / DSPM) ───────────────────────────────────
    result["instruments_financiers"]     = parse_instruments_financiers(root)
    result["participations_financieres"] = parse_participations_financieres(root)
    result["biens_immobiliers"]          = parse_biens_immobiliers(root)
    result["comptes_bancaires"]          = parse_comptes_bancaires(root)
    result["vehicules"]                  = parse_vehicules(root)
    result["biens_mobiliers_valeur"]     = parse_biens_mobiliers(root)
    result["dettes"]                     = parse_dettes(root)
    result["revenus"]                    = parse_revenus(root)

    # ── Sections intérêts (DI / DIM) ──────────────────────────────────────────
    result["activites_professionnelles"] = parse_activites_professionnelles(root)
    result["activites_anterieures"]      = parse_activites_anterieures(root)
    result["mandats_electifs"]           = parse_mandats_elus(root)
    result["participations_organes"]     = parse_participations_organes(root)
    result["soutiens_associations"]      = parse_soutiens_associations(root)
    result["autres_liens_interets"]      = parse_autres_liens_interets(root)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Orchestration par élu
# ══════════════════════════════════════════════════════════════════════════════

# Toutes les clés de sections extraites (dans l'ordre d'affichage)
ALL_SECTIONS = [
    "instruments_financiers",
    "participations_financieres",
    "biens_immobiliers",
    "comptes_bancaires",
    "vehicules",
    "biens_mobiliers_valeur",
    "dettes",
    "revenus",
    "activites_professionnelles",
    "activites_anterieures",
    "mandats_electifs",
    "participations_organes",
    "soutiens_associations",
    "autres_liens_interets",
]

SECTION_LABELS = {
    "instruments_financiers":     "📈 Instruments financiers",
    "participations_financieres": "🏢 Participations dans des sociétés",
    "biens_immobiliers":          "🏠 Biens immobiliers",
    "comptes_bancaires":          "🏦 Comptes bancaires & épargne",
    "vehicules":                  "🚗 Véhicules",
    "biens_mobiliers_valeur":     "💎 Biens mobiliers de valeur",
    "dettes":                     "📉 Dettes & emprunts",
    "revenus":                    "💶 Revenus",
    "activites_professionnelles": "💼 Activités professionnelles actuelles",
    "activites_anterieures":      "📋 Activités professionnelles antérieures",
    "mandats_electifs":           "🗳️  Mandats électifs",
    "participations_organes":     "🏛️  Participations à des organes",
    "soutiens_associations":      "🤝 Soutiens associatifs",
    "autres_liens_interets":      "⚠️  Autres liens d'intérêts",
}


def fetch_hatvp_data_for_elu(
    elu: dict,
    index: list[dict],
    force: bool,
    dry_run: bool,
    delay: float,
) -> dict | None:
    """
    Récupérer l'intégralité des données HATVP pour un élu (DSP + DI).
    Retourne un dict consolidé ou None si aucune déclaration trouvée.
    """
    prenom = elu.get("prenom", "").strip()
    nom    = elu.get("nom",    "").strip()
    if not prenom or not nom:
        return None

    declarations_rows = find_declarations_for_elu(index, prenom, nom)
    if not declarations_rows:
        print(f"    ✗ Aucune déclaration HATVP trouvée pour {prenom} {nom}")
        return None

    print(f"    ✓ {len(declarations_rows)} déclaration(s) trouvée(s)")

    # Prendre la DSP la plus récente et la DI la plus récente
    dsp_row = next((r for r in declarations_rows if get_declaration_type(r) in DSP_TYPES), None)
    di_row  = next((r for r in declarations_rows if get_declaration_type(r) in DI_TYPES),  None)

    result = {
        "prenom":               prenom,
        "nom":                  nom,
        "scraped_at":           datetime.utcnow().isoformat() + "Z",
        "declarations_trouvees": len(declarations_rows),
        "declarations":         [],
    }
    # Initialiser toutes les sections à vide
    for section in ALL_SECTIONS:
        result[section] = []

    for row, label in [(dsp_row, "DSP"), (di_row, "DI")]:
        if row is None:
            continue

        xml_url = get_xml_url(row)
        if not xml_url:
            print(f"    ⚠ URL XML introuvable pour la {label} de {prenom} {nom}")
            continue

        decl_type  = get_declaration_type(row)
        date_depot = row.get("dateDepot") or row.get("DateDepot") or "?"
        print(f"    🔄 {label} ({decl_type}, {date_depot}) : {xml_url}")

        if dry_run:
            result["declarations"].append({"type": decl_type, "url": xml_url, "dry_run": True})
            continue

        filename   = xml_url.split("/")[-1]
        cache_path = os.path.join(CACHE_DIR, "xmls", filename)
        xml_bytes  = download_xml(xml_url, cache_path, force=force, delay=delay)
        if not xml_bytes:
            print(f"    ✗ Impossible de télécharger {xml_url}")
            continue

        parsed = parse_declaration_xml(xml_bytes, xml_url)
        if not parsed:
            continue

        # Fusionner toutes les sections extraites
        for section in ALL_SECTIONS:
            result[section].extend(parsed.get(section, []))

        result["declarations"].append({
            "type":       parsed.get("type_declaration"),
            "label":      parsed.get("type_declaration_label"),
            "date_depot": parsed.get("date_depot"),
            "uuid":       parsed.get("uuid"),
            "url":        xml_url,
            "qualite":    parsed.get("qualite"),
            "organe":     parsed.get("organe"),
        })

    return result


def build_resume_hatvp(data: dict) -> dict:
    """Construire un résumé compact (pour elus.json) depuis les données brutes."""

    def total_valeur(items: list[dict], key: str = "valeur_euro") -> float:
        return sum(i[key] for i in items if i.get(key) is not None)

    instruments    = data.get("instruments_financiers",     [])
    participations = data.get("participations_financieres", [])
    immobilier     = data.get("biens_immobiliers",          [])
    comptes        = data.get("comptes_bancaires",          [])
    vehicules      = data.get("vehicules",                  [])
    mobilier       = data.get("biens_mobiliers_valeur",     [])
    dettes         = data.get("dettes",                     [])
    revenus        = data.get("revenus",                    [])

    valeur_instruments    = total_valeur(instruments)
    valeur_participations = total_valeur(participations)
    valeur_immobilier     = total_valeur(immobilier)
    valeur_comptes        = total_valeur(comptes, "solde_euro")
    valeur_vehicules      = total_valeur(vehicules)
    valeur_mobilier       = total_valeur(mobilier)
    total_dettes          = total_valeur(dettes, "montant_euro")
    total_revenus         = total_valeur(revenus, "montant_euro")

    actif_brut = (
        valeur_instruments    +
        valeur_participations +
        valeur_immobilier     +
        valeur_comptes        +
        valeur_vehicules      +
        valeur_mobilier
    )

    # Regrouper les instruments par nature
    natures_instruments: dict[str, int] = {}
    for i in instruments:
        n = i.get("nature", "Autre")
        natures_instruments[n] = natures_instruments.get(n, 0) + 1

    return {
        # Comptages
        "nb_instruments_financiers":      len(instruments),
        "nb_participations_societes":     len(participations),
        "nb_biens_immobiliers":           len(immobilier),
        "nb_comptes_bancaires":           len(comptes),
        "nb_vehicules":                   len(vehicules),
        "nb_biens_mobiliers_valeur":      len(mobilier),
        "nb_dettes":                      len(dettes),
        "nb_sources_revenus":             len(revenus),
        "nb_activites_pro":               len(data.get("activites_professionnelles", [])),
        "nb_activites_anterieures":       len(data.get("activites_anterieures",      [])),
        "nb_mandats_electifs":            len(data.get("mandats_electifs",           [])),
        "nb_participations_organes":      len(data.get("participations_organes",     [])),
        "nb_soutiens_associations":       len(data.get("soutiens_associations",      [])),
        "nb_autres_liens_interets":       len(data.get("autres_liens_interets",      [])),
        # Valorisations
        "valeur_instruments_euro":        valeur_instruments,
        "valeur_participations_euro":     valeur_participations,
        "valeur_immobilier_euro":         valeur_immobilier,
        "valeur_comptes_euro":            valeur_comptes,
        "valeur_vehicules_euro":          valeur_vehicules,
        "valeur_mobilier_euro":           valeur_mobilier,
        "total_actif_brut_euro":          actif_brut,
        "total_dettes_euro":              total_dettes,
        "patrimoine_net_euro":            actif_brut - total_dettes,
        "total_revenus_euro":             total_revenus,
        # Détail instruments
        "types_instruments":              natures_instruments,
        # Méta
        "nb_declarations_hatvp":          data.get("declarations_trouvees", 0),
        "hatvp_scraped_at":               data.get("scraped_at", ""),
    }


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
    print(f"✓ {OUTPUT_JSON} mis à jour")


def find_elu_by_name(elus: list[dict], query: str) -> dict | None:
    q = query.lower()
    for e in elus:
        full = f"{e.get('prenom', '')} {e.get('nom', '')}".lower()
        if q in full:
            return e
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Affichage test
# ══════════════════════════════════════════════════════════════════════════════

def print_section_test(result: dict, section: str, nb: int = 5) -> None:
    items = result.get(section, [])
    if not items:
        return
    label = SECTION_LABELS.get(section, section)
    print(f"\n  {label} ({len(items)}) :")
    for item in items[:nb]:
        # Afficher les champs non vides sur une ligne
        parts = []
        for k, v in item.items():
            if v is not None and v != "" and k != "commentaire":
                if isinstance(v, float):
                    parts.append(f"{k}={v:,.0f} €")
                else:
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
    print("   Sources : liste.csv + XMLs https://www.hatvp.fr/livraison/")
    if args.dry_run:
        print("   ⚠ MODE DRY-RUN — aucun fichier ne sera écrit")
    print("=" * 65)

    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.join(CACHE_DIR, "xmls"), exist_ok=True)

    print("\n📥 Chargement de l'index HATVP…")
    try:
        index = load_hatvp_index(force_refresh=args.refresh_index, delay=args.delay)
    except RuntimeError as exc:
        print(f"❌ {exc}")
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

        result = fetch_hatvp_data_for_elu(
            elu, index, force=True, dry_run=args.dry_run, delay=args.delay
        )

        if result:
            print(f"\n{'=' * 65}")
            print("✅ RÉSULTAT COMPLET")
            print(f"{'=' * 65}")
            print(f"  Déclarations trouvées : {result['declarations_trouvees']}")
            total_items = sum(len(result.get(s, [])) for s in ALL_SECTIONS)
            print(f"  Total éléments extraits : {total_items}")

            for section in ALL_SECTIONS:
                print_section_test(result, section)

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
    updated: dict[str, dict] = {}

    for i, elu in enumerate(elus, 1):
        prenom = elu.get("prenom", "")
        nom    = elu.get("nom",    "")
        elu_id = elu.get("id",     f"elu-{i}")
        print(f"\n[{i}/{total}] {prenom} {nom}")

        result = fetch_hatvp_data_for_elu(
            elu, index, force=args.force, dry_run=args.dry_run, delay=args.delay
        )

        if result is None:
            not_found += 1
        else:
            done += 1
            resume = build_resume_hatvp(result)
            updated[elu_id] = resume

            total_items = sum(len(result.get(s, [])) for s in ALL_SECTIONS)
            if total_items:
                # Afficher un résumé compact par section non vide
                summary_parts = [
                    f"{len(result[s])} {s.replace('_', ' ')}"
                    for s in ALL_SECTIONS if result.get(s)
                ]
                print(f"  ✓ {total_items} éléments : {', '.join(summary_parts)}")
            else:
                print(f"  ○ Déclarations trouvées mais aucun élément déclaré")

            # Sauvegarder le détail complet dans un fichier séparé
            if not args.dry_run:
                detail_path = os.path.join(CACHE_DIR, f"{elu_id}.json")
                with open(detail_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

        time.sleep(args.delay)

    # ── Mettre à jour elus.json ────────────────────────────────────────────────
    if not args.dry_run and updated:
        all_elus = load_elus()
        for e in all_elus:
            if e["id"] in updated:
                e["hatvp"] = updated[e["id"]]
        save_elus(all_elus)

    print("\n" + "=" * 65)
    print("📊 RAPPORT FINAL")
    print("=" * 65)
    print(f"  Total traités              : {total}")
    print(f"  ✓ Données extraites        : {done}")
    print(f"  ✗ Non trouvés dans HATVP   : {not_found}")
    print(f"  Détails dans               : {CACHE_DIR}/")
    print("=" * 65)


if __name__ == "__main__":
    main()
