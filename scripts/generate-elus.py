#!/usr/bin/env python3
"""
Script d'extraction OPTIMISÉE des données HATVP des élus français.

Améliorations :
  ✓ Sauvegarde incrémentale tous les 100 élus
  ✓ Barre de progression détaillée
  ✓ Parsing XML robuste et exhaustif
  ✓ Gestion d'erreurs améliorée
  ✓ Optimisation mémoire
  ✓ Intégration directe dans elus.json

Utilisation :
  python generate-elus-hatvp-optimized.py
  python generate-elus-hatvp-optimized.py --limit 50
  python generate-elus-hatvp-optimized.py --test-elu "Yaël Braun-Pivet"
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

WANTED_TYPES = {"DSP", "DSPM", "DI", "DIM"}
DSP_TYPES = {"DSP", "DSPM"}
DI_TYPES = {"DI", "DIM"}

HEADERS = {
    "User-Agent": "TransparenceNationale/2.0",
    "Accept": "text/csv, application/xml, text/xml, */*",
}

SAVE_INTERVAL = 100  # Sauvegarder tous les 100 élus

# ══════════════════════════════════════════════════════════════════════════════
# Utilitaires d'affichage
# ══════════════════════════════════════════════════════════════════════════════

class ProgressTracker:
    """Suivi de progression avec statistiques temps réel."""
    
    def __init__(self, total: int):
        self.total = total
        self.current = 0
        self.success = 0
        self.not_found = 0
        self.errors = 0
        self.start_time = time.time()
        
    def update(self, success: bool = False, not_found: bool = False, error: bool = False):
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
                f"{rate:.1f}/s | ETA: {int(remaining//60)}m{int(remaining%60)}s")
    
    def print_progress(self, elu_name: str, message: str = ""):
        stats = self.get_stats()
        print(f"\r{stats} | {elu_name[:30]:30s} {message}", end="", flush=True)
        
    def print_line(self, message: str):
        """Afficher un message complet sur une nouvelle ligne."""
        print(f"\n{message}")


# ══════════════════════════════════════════════════════════════════════════════
# Réseau et cache
# ══════════════════════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 30) -> Optional[bytes]:
    """Télécharger une URL avec gestion d'erreurs."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 403, 410):
            print(f"\n[http_get] HTTP {exc.code} : {url}", file=sys.stderr)
    except Exception as exc:
        print(f"\n[http_get] Erreur inattendue : {exc} ({url})", file=sys.stderr)
    return None


def download_with_cache(url: str, cache_path: str, force: bool = False, delay: float = 0.3) -> Optional[bytes]:
    """Télécharger avec cache local."""
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
    """Charger l'index HATVP avec cache intelligent."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    raw = None
    if not force_refresh and os.path.exists(INDEX_CACHE):
        age_h = (time.time() - os.path.getmtime(INDEX_CACHE)) / 3600
        if age_h < 24:
            print(f"📋 Index CSV en cache ({age_h:.1f}h)")
            with open(INDEX_CACHE, "rb") as f:
                raw = f.read()
    
    if raw is None:
        print(f"📥 Téléchargement index HATVP...")
        time.sleep(0.5)
        raw = http_get(HATVP_INDEX_URL)
        if not raw:
            raise RuntimeError("Impossible de télécharger l'index HATVP")
        with open(INDEX_CACHE, "wb") as f:
            f.write(raw)
        print(f"✓ Index téléchargé ({len(raw):,} octets)")
    
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    print(f"✓ {len(rows):,} déclarations indexées")
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# Normalisation et recherche
# ══════════════════════════════════════════════════════════════════════════════

def normalize_name(s: str) -> str:
    """Normaliser un nom pour la recherche."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[-\s]+", " ", s).strip()
    return s


def find_declarations(index: list[dict], prenom: str, nom: str) -> list[dict]:
    """Trouver toutes les déclarations d'un élu."""
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
        date_str = (row.get("dateDepot") or row.get("DateDepot") or "")
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except (ValueError, AttributeError):
                continue
        return datetime.min
    
    matched.sort(key=parse_date, reverse=True)
    return matched


def get_xml_url(row: dict) -> Optional[str]:
    """Extraire l'URL du XML."""
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
# Parsing XML robuste
# ══════════════════════════════════════════════════════════════════════════════

def xml_text(element, path: str, default: str = "") -> str:
    """Extraire texte d'un nœud XML."""
    if element is None:
        return default
    node = element.find(path)
    if node is not None and node.text:
        t = node.text.strip()
        if t and t != "[Données non publiées]":
            return t
    return default


def xml_bool(element, path: str) -> bool:
    """Extraire booléen."""
    return xml_text(element, path).lower() == "true"


def parse_montant(s: str) -> Optional[float]:
    """Parser un montant en euros."""
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    s = re.sub(r"[^\d.-]", "", s)  # Garder seulement chiffres, point, tiret
    try:
        return float(s)
    except ValueError:
        return None


def is_empty_section(element) -> bool:
    """Vérifier si une section est vide."""
    if element is None:
        return True
    neant = xml_text(element, "neant").lower()
    return neant == "true"


def parse_items(section: ET.Element, item_parser) -> list:
    """Parser générique d'items dans une section."""
    if is_empty_section(section):
        return []
    
    items = []
    # Essayer les chemins dans l'ordre, sans fallback sur .//* qui est trop large
    for path in [".//items/items", ".//items", ".//item"]:
        found = section.findall(path)
        if found:
            for elem in found:
                if elem.tag in ("items", "item"):
                    parsed = item_parser(elem)
                    if parsed:
                        items.append(parsed)
            if items:
                break
    
    return items


def parse_instrument_financier(item: ET.Element) -> Optional[dict]:
    """Parser un instrument financier."""
    nature_id = xml_text(item, "nature/id") or xml_text(item, "typeInstrument/id")
    nature_label = xml_text(item, "nature/label") or xml_text(item, "typeInstrument/label") or nature_id
    
    valeur_str = (
        xml_text(item, "valeur") or
        xml_text(item, "valeurEstimee") or
        xml_text(item, "montant") or
        xml_text(item, "valeurTotale")
    )
    
    description = (
        xml_text(item, "description") or
        xml_text(item, "denomination") or
        xml_text(item, "libelle") or
        xml_text(item, "nomEmetteur")
    )
    
    # Filtrer les entrées vides
    if not nature_label and not description and not valeur_str:
        return None
    
    return {
        "type": "instrument_financier",
        "nature": nature_label,
        "nature_code": nature_id,
        "description": description,
        "valeur_euro": parse_montant(valeur_str),
        "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id"),
        "nombre_titres": xml_text(item, "nombreTitres") or xml_text(item, "nbTitres"),
        "valeur_unitaire_euro": parse_montant(xml_text(item, "valeurUnitaire")),
        "isin": xml_text(item, "codeISIN") or xml_text(item, "isin"),
        "devise": xml_text(item, "devise") or xml_text(item, "devise/id"),
        "date_acquisition": xml_text(item, "dateAcquisition") or xml_text(item, "dateOuverture"),
        "etablissement": xml_text(item, "etablissement") or xml_text(item, "nomEtablissement"),
    }


def parse_participation(item: ET.Element) -> Optional[dict]:
    """Parser une participation financière."""
    nom_societe = (
        xml_text(item, "nomSociete") or
        xml_text(item, "denomination") or
        xml_text(item, "raisonSociale")
    )
    
    valeur_str = (
        xml_text(item, "valeurParts") or
        xml_text(item, "valeur") or
        xml_text(item, "montant") or
        xml_text(item, "valeurEstimee")
    )
    
    if not nom_societe and not valeur_str:
        return None
    
    return {
        "type": "participation_financiere",
        "nom_societe": nom_societe,
        "forme_juridique": xml_text(item, "formeJuridique") or xml_text(item, "typeStructure/label"),
        "nb_parts": xml_text(item, "nbParts") or xml_text(item, "nombreParts"),
        "valeur_euro": parse_montant(valeur_str),
        "pourcentage_detention": xml_text(item, "pourcentage") or xml_text(item, "tauxDetention"),
        "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id"),
        "objet_social": xml_text(item, "objetSocial") or xml_text(item, "activite") or xml_text(item, "secteurActivite"),
        "siren": xml_text(item, "siren") or xml_text(item, "numeroSIREN"),
    }


def parse_bien_immobilier(item: ET.Element) -> Optional[dict]:
    """Parser un bien immobilier."""
    nature = (
        xml_text(item, "nature/label") or
        xml_text(item, "nature/id") or
        xml_text(item, "typeBien/label")
    )
    
    valeur_str = (
        xml_text(item, "valeur") or
        xml_text(item, "valeurEstimee") or
        xml_text(item, "montant")
    )
    
    adresse = (
        xml_text(item, "adresse") or
        xml_text(item, "localisation") or
        xml_text(item, "commune")
    )
    
    if not nature and not adresse and not valeur_str:
        return None
    
    return {
        "type": "bien_immobilier",
        "nature": nature,
        "adresse": adresse,
        "surface_m2": xml_text(item, "surface") or xml_text(item, "superficieM2"),
        "valeur_euro": parse_montant(valeur_str),
        "mode_detention": xml_text(item, "modeDetention/label") or xml_text(item, "modeDetention/id"),
        "date_acquisition": xml_text(item, "dateAcquisition") or xml_text(item, "dateAchat"),
        "usage": xml_text(item, "usage") or xml_text(item, "affectation"),
    }


def parse_pret(item: ET.Element) -> Optional[dict]:
    """Parser un prêt bancaire."""
    montant_str = (
        xml_text(item, "montant") or
        xml_text(item, "montantEmprunte") or
        xml_text(item, "capitalEmprunte")
    )
    
    capital_restant_str = (
        xml_text(item, "capitalRestantDu") or
        xml_text(item, "montantRestant") or
        xml_text(item, "solde")
    )
    
    montant = parse_montant(montant_str)
    capital_restant = parse_montant(capital_restant_str)
    
    if montant is None and capital_restant is None:
        return None
    
    return {
        "type": "pret_bancaire",
        "nature": xml_text(item, "nature/label") or xml_text(item, "typeCredit/label"),
        "etablissement": xml_text(item, "etablissement") or xml_text(item, "organisme"),
        "montant_emprunte_euro": montant,
        "capital_restant_du_euro": capital_restant,
        "date_souscription": xml_text(item, "dateSouscription") or xml_text(item, "dateEmprunt"),
        "objet": xml_text(item, "objet") or xml_text(item, "finalite"),
    }


def parse_autre_bien(item: ET.Element) -> Optional[dict]:
    """Parser autre bien."""
    valeur_str = xml_text(item, "valeur") or xml_text(item, "valeurEstimee")
    nature = xml_text(item, "nature/label") or xml_text(item, "categorie/label")
    description = xml_text(item, "description") or xml_text(item, "designation")
    
    if not nature and not description and not valeur_str:
        return None
    
    return {
        "type": "autre_bien",
        "nature": nature,
        "description": description,
        "valeur_euro": parse_montant(valeur_str),
    }


def parse_revenu(item: ET.Element) -> Optional[dict]:
    """Parser revenu/activité."""
    montant_str = (
        xml_text(item, "montant") or
        xml_text(item, "montantAnnuel") or
        xml_text(item, "remunerationAnnuelle")
    )
    
    nature = xml_text(item, "nature/label") or xml_text(item, "typeActivite/label")
    employeur = xml_text(item, "employeur") or xml_text(item, "source")
    fonction = xml_text(item, "fonction") or xml_text(item, "activite")
    
    if not nature and not employeur and not fonction:
        return None
    
    return {
        "type": "revenu",
        "nature": nature,
        "employeur": employeur,
        "fonction": fonction,
        "montant_annuel_euro": parse_montant(montant_str),
    }


def parse_mandat(item: ET.Element) -> Optional[dict]:
    """Parser mandat électif."""
    nature = xml_text(item, "nature/label") or xml_text(item, "typeMandat/label")
    fonction = xml_text(item, "fonction") or xml_text(item, "qualite")
    
    if not nature and not fonction:
        return None
    
    return {
        "type": "mandat_electif",
        "nature": nature,
        "fonction": fonction,
        "collectivite": xml_text(item, "collectivite") or xml_text(item, "organe"),
        "date_debut": xml_text(item, "dateDebut"),
        "date_fin": xml_text(item, "dateFin"),
        "en_cours": xml_bool(item, "enCours"),
    }


def parse_fonction(item: ET.Element) -> Optional[dict]:
    """Parser fonction dirigeante."""
    fonction = xml_text(item, "fonction") or xml_text(item, "titre")
    organisme = xml_text(item, "organisme") or xml_text(item, "structure")
    
    if not fonction and not organisme:
        return None
    
    return {
        "type": "fonction_dirigeante",
        "fonction": fonction,
        "organisme": organisme,
        "nature_organisme": xml_text(item, "natureOrganisme/label"),
        "remuneree": xml_bool(item, "remuneree"),
        "montant_annuel_euro": parse_montant(xml_text(item, "montant")),
    }


def parse_xml_declaration(xml_bytes: bytes, url: str) -> Optional[dict]:
    """Parser complet d'un XML HATVP avec gestion d'erreurs robuste."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    
    result = {
        "url_xml": url,
        "type_declaration": xml_text(root, "general/typeDeclaration/id"),
        "date_depot": xml_text(root, "dateDepot"),
    }
    
    # Parser toutes les sections
    sections = [
        (".//instrumentsFinanciersDto", parse_instrument_financier, "instruments_financiers"),
        (".//participationFinanciereDto", parse_participation, "participations_financieres"),
        (".//biensImmobiliersDto", parse_bien_immobilier, "biens_immobiliers"),
        (".//pretsBancairesDto", parse_pret, "prets_bancaires"),
        (".//autresBiensDto", parse_autre_bien, "autres_biens"),
        (".//revenusDto", parse_revenu, "revenus"),
        (".//activitesRemunerees", parse_revenu, "activites"),
        (".//mandatsElectifsDto", parse_mandat, "mandats_electifs"),
        (".//fonctionsDto", parse_fonction, "fonctions_dirigeantes"),
        (".//fonctionsDirigeantes", parse_fonction, "fonctions_dirigeantes"),
    ]
    
    for xpath, parser, key in sections:
        section = root.find(xpath)
        if section is not None:
            items = parse_items(section, parser)
            if key in result:
                result[key].extend(items)
            else:
                result[key] = items
    
    # Famille
    conjoint_section = root.find(".//conjoint")
    if conjoint_section is not None:
        result["famille"] = {
            "conjoint": {
                "nom": xml_text(conjoint_section, "nom"),
                "prenom": xml_text(conjoint_section, "prenom"),
                "profession": xml_text(conjoint_section, "profession"),
            }
        }
    
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Calculs et agrégation
# ══════════════════════════════════════════════════════════════════════════════

def calculate_patrimoine(data: dict) -> dict:
    """Calculer le patrimoine total et stats."""
    instruments = data.get("instruments_financiers", [])
    participations = data.get("participations_financieres", [])
    immobilier = data.get("biens_immobiliers", [])
    prets = data.get("prets_bancaires", [])
    autres_biens = data.get("autres_biens", [])
    revenus = data.get("revenus", []) + data.get("activites", [])
    
    val_instruments = sum(i.get("valeur_euro", 0) or 0 for i in instruments)
    val_participations = sum(p.get("valeur_euro", 0) or 0 for p in participations)
    val_immobilier = sum(b.get("valeur_euro", 0) or 0 for b in immobilier)
    val_autres = sum(b.get("valeur_euro", 0) or 0 for b in autres_biens)
    total_dettes = sum(p.get("capital_restant_du_euro", 0) or 0 for p in prets)
    revenus_annuels = sum(r.get("montant_annuel_euro", 0) or 0 for r in revenus)
    
    patrimoine_brut = val_instruments + val_participations + val_immobilier + val_autres
    patrimoine_net = patrimoine_brut - total_dettes
    
    return {
        "patrimoine_brut_euro": round(patrimoine_brut, 2) if patrimoine_brut > 0 else None,
        "patrimoine_net_euro": round(patrimoine_net, 2) if patrimoine_net != 0 else None,
        "valeur_instruments_euro": round(val_instruments, 2) if val_instruments > 0 else None,
        "valeur_participations_euro": round(val_participations, 2) if val_participations > 0 else None,
        "valeur_immobilier_euro": round(val_immobilier, 2) if val_immobilier > 0 else None,
        "total_dettes_euro": round(total_dettes, 2) if total_dettes > 0 else None,
        "revenus_annuels_euro": round(revenus_annuels, 2) if revenus_annuels > 0 else None,
        "nb_instruments_financiers": len(instruments),
        "nb_participations": len(participations),
        "nb_biens_immobiliers": len(immobilier),
        "nb_prets_bancaires": len(prets),
        "nb_autres_biens": len(autres_biens),
        "nb_mandats_electifs": len(data.get("mandats_electifs", [])),
        "nb_fonctions": len(data.get("fonctions_dirigeantes", [])),
        "a_conjoint": bool(data.get("famille", {}).get("conjoint", {}).get("nom")),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Traitement d'un élu
# ══════════════════════════════════════════════════════════════════════════════

def process_elu(elu: dict, index: list[dict], force: bool, delay: float) -> Optional[dict]:
    """Traiter un élu : récupérer et parser ses déclarations."""
    prenom = elu.get("prenom", "").strip()
    nom = elu.get("nom", "").strip()
    
    if not prenom or not nom:
        return None
    
    declarations_rows = find_declarations(index, prenom, nom)
    if not declarations_rows:
        return None
    
    # Prendre la DSP et DI les plus récentes
    dsp_row = next((r for r in declarations_rows if get_declaration_type(r) in DSP_TYPES), None)
    di_row = next((r for r in declarations_rows if get_declaration_type(r) in DI_TYPES), None)
    
    if not dsp_row and not di_row:
        return None
    
    # Structure de résultat consolidée
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
        "declarations": [],
    }
    
    # Parser DSP et DI
    for row in [dsp_row, di_row]:
        if row is None:
            continue
        
        xml_url = get_xml_url(row)
        if not xml_url:
            continue
        
        filename = xml_url.split("/")[-1]
        cache_path = os.path.join(CACHE_DIR, "xmls", filename)
        
        xml_bytes = download_with_cache(xml_url, cache_path, force=force, delay=delay)
        if not xml_bytes:
            continue
        
        parsed = parse_xml_declaration(xml_bytes, xml_url)
        if not parsed:
            continue
        
        # Consolider les données
        for key in ["instruments_financiers", "participations_financieres", "biens_immobiliers",
                    "prets_bancaires", "autres_biens", "revenus", "activites",
                    "mandats_electifs", "fonctions_dirigeantes"]:
            if key in parsed:
                consolidated[key].extend(parsed[key])
        
        if parsed.get("famille"):
            consolidated["famille"] = parsed["famille"]
        
        consolidated["declarations"].append({
            "type": parsed["type_declaration"],
            "date_depot": parsed["date_depot"],
            "url": xml_url,
        })
    
    # Calculer patrimoine
    patrimoine = calculate_patrimoine(consolidated)
    
    # Ne garder que les données essentielles
    result = {
        "hatvp_scraped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **patrimoine,
        "declarations": consolidated["declarations"],
    }
    
    # Ajouter détails si présents (optionnel - peut être commenté pour économiser espace)
    if patrimoine.get("patrimoine_net_euro"):
        result["patrimoine_details"] = {
            "instruments_financiers": consolidated["instruments_financiers"][:10],  # Limiter à 10
            "biens_immobiliers": consolidated["biens_immobiliers"][:10],
            "participations_financieres": consolidated["participations_financieres"][:10],
        }
    
    return result


# ══════════════════════════════════════════════════════════════════════════════
# I/O elus.json
# ══════════════════════════════════════════════════════════════════════════════

def load_elus() -> list[dict]:
    """Charger elus.json."""
    if not os.path.exists(OUTPUT_JSON):
        print(f"⚠ {OUTPUT_JSON} introuvable")
        return []
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def save_elus(elus: list[dict], backup: bool = True) -> None:
    """Sauvegarder elus.json de façon atomique."""
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    
    # Backup
    if backup and os.path.exists(OUTPUT_JSON):
        backup_path = OUTPUT_JSON + f".backup.{int(time.time())}"
        os.rename(OUTPUT_JSON, backup_path)
    
    tmp_path = OUTPUT_JSON + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(elus, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, OUTPUT_JSON)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(description="Extraction optimisée HATVP")
    p.add_argument("--limit", type=int, help="Limiter le nombre d'élus")
    p.add_argument("--force", action="store_true", help="Forcer re-téléchargement XMLs")
    p.add_argument("--delay", type=float, default=0.3, help="Délai entre requêtes (secondes)")
    p.add_argument("--test-elu", type=str, help="Tester un élu spécifique")
    p.add_argument("--refresh-index", action="store_true", help="Re-télécharger l'index CSV")
    p.add_argument("--skip-existing", action="store_true", help="Passer les élus qui ont déjà des données HATVP")
    return p.parse_args()


def main():
    args = parse_args()
    
    print("=" * 80)
    print("💰 EXTRACTION HATVP OPTIMISÉE")
    print("=" * 80)
    
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.join(CACHE_DIR, "xmls"), exist_ok=True)
    
    # Charger index
    try:
        index = load_hatvp_index(force_refresh=args.refresh_index)
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return
    
    # Mode test
    if args.test_elu:
        print(f"\n🧪 MODE TEST : {args.test_elu}")
        
        elus = load_elus()
        elu = None
        for e in elus:
            if args.test_elu.lower() in f"{e.get('prenom', '')} {e.get('nom', '')}".lower():
                elu = e
                break
        
        if not elu:
            parts = args.test_elu.split()
            elu = {"id": "test", "prenom": parts[0], "nom": " ".join(parts[1:])}
        
        result = process_elu(elu, index, force=True, delay=args.delay)
        
        if result:
            print("\n✅ RÉSULTAT :")
            print(f"  Patrimoine net : {result.get('patrimoine_net_euro', 0):,.0f} €")
            print(f"  Revenus annuels : {result.get('revenus_annuels_euro', 0):,.0f} €")
            print(f"  Instruments : {result.get('nb_instruments_financiers', 0)}")
            print(f"  Immobilier : {result.get('nb_biens_immobiliers', 0)}")
            print(f"  Déclarations : {len(result.get('declarations', []))}")
            
            # Sauvegarder pour inspection
            test_path = os.path.join(CACHE_DIR, "test_result.json")
            with open(test_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Détails : {test_path}")
        else:
            print("✗ Aucune donnée trouvée")
        
        return
    
    # Mode batch
    print("\n🔄 Traitement batch...")
    elus = load_elus()
    
    if not elus:
        print("❌ elus.json vide")
        return
    
    if args.limit:
        elus = elus[:args.limit]
    
    progress = ProgressTracker(len(elus))
    updated_count = 0
    
    for i, elu in enumerate(elus):
        prenom = elu.get("prenom", "")
        nom = elu.get("nom", "")
        elu_name = f"{prenom} {nom}"
        
        progress.print_progress(elu_name, "⏳")
        
        if args.skip_existing and elu.get("hatvp"):
            progress.update(not_found=True)
            continue
        
        try:
            result = process_elu(elu, index, force=args.force, delay=args.delay)
            
            if result:
                elu["hatvp"] = result
                progress.update(success=True)
                updated_count += 1
                
                # Afficher succès avec stats
                pat = result.get("patrimoine_net_euro", 0)
                rev = result.get("revenus_annuels_euro", 0)
                progress.print_progress(elu_name, f"✓ {pat:>10,.0f}€ {rev:>8,.0f}€/an")
            else:
                progress.update(not_found=True)
                progress.print_progress(elu_name, "✗")
            
            # Sauvegarde incrémentale
            if (i + 1) % SAVE_INTERVAL == 0:
                progress.print_line(f"\n💾 Sauvegarde incrémentale ({updated_count} élus mis à jour)...")
                save_elus(elus, backup=False)
                progress.print_line(f"✓ Sauvegardé")
        
        except Exception as exc:
            progress.update(error=True)
            progress.print_progress(elu_name, f"⚠ {str(exc)[:30]}")
    
    # Sauvegarde finale
    print(f"\n\n💾 Sauvegarde finale...")
    save_elus(elus, backup=True)
    
    print("\n" + "=" * 80)
    print("📊 RAPPORT FINAL")
    print("=" * 80)
    print(f"  Total traités     : {progress.total}")
    print(f"  ✓ Mis à jour      : {progress.success}")
    print(f"  ✗ Non trouvés     : {progress.not_found}")
    print(f"  ⚠ Erreurs         : {progress.errors}")
    print(f"  Temps total       : {int((time.time() - progress.start_time) / 60)}m")
    print("=" * 80)


if __name__ == "__main__":
    main()
