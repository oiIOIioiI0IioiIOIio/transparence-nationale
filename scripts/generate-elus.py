#!/usr/bin/env python3
"""
Script de récupération des déclarations financières HATVP des élus français.

Lit le fichier index officiel HATVP (liste.csv), télécharge les XMLs
correspondant à chaque élu et extrait :
  - instruments financiers (actions, obligations, ETF, PEA, assurance-vie…)
  - participations financières dans des sociétés (cotées ou non)

Sources :
  Index CSV  : https://www.hatvp.fr/livraison/opendata/liste.csv
  XMLs       : https://www.hatvp.fr/livraison/dossiers/{fichier}.xml
  Doc xlsx   : https://www.data.gouv.fr/api/1/datasets/r/f99ea4c7-ddf4-484b-b7de-ea4419c9f865

Structure XML HATVP pertinente :
  <declaration>
    <general>
      <typeDeclaration><id>DSP|DI|...</id></typeDeclaration>
      <declarant><nom/><prenom/></declarant>
    </general>
    <!-- DSP uniquement — instruments financiers côtés -->
    <instrumentsFinanciersDto>
      <neant>false</neant>
      <items>
        <items>
          <description>Apple Inc.</description>
          <valeur>12500</valeur>
          <nature><id>ACTIONS</id></nature>
          <modeDetention><id>DIRECT</id></modeDetention>
        </items>
      </items>
    </instrumentsFinanciersDto>
    <!-- DSP + DI — participations dans des sociétés -->
    <participationFinanciereDto>
      <neant>false</neant>
      <items>
        <items>
          <nomSociete>SARL EXEMPLE</nomSociete>
          <nbParts>100</nbParts>
          <valeurParts>5000</valeurParts>
        </items>
      </items>
    </participationFinanciereDto>
  </declaration>

Utilisation :
  python scrape-hatvp-finances.py --dry-run
  python scrape-hatvp-finances.py --limit 50
  python scrape-hatvp-finances.py --test-elu "Yaël Braun-Pivet"
  python scrape-hatvp-finances.py --force
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
# Fichier CSV index : liste toutes les déclarations disponibles
HATVP_INDEX_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"

# Fichier XML individuel (chemin complet fourni dans le CSV, colonne "url" ou "fichier")
HATVP_XML_BASE = "https://www.hatvp.fr/livraison/dossiers/"

# ── Types de déclaration à prioriser ──────────────────────────────────────────
# DSP = Situation Patrimoniale (contient les instruments financiers)
# DI  = Déclaration d'Intérêts (contient les participations dans sociétés)
# On veut les deux, DSP en priorité
WANTED_TYPES = {
    "DSP",  # Déclaration de Situation Patrimoniale (initiale)
    "DSPM", # DSP Modificative
    "DI",   # Déclaration d'Intérêts
    "DIM",  # DI Modificative
}

# Types DSP (contiennent les instruments financiers boursiers)
DSP_TYPES = {"DSP", "DSPM"}

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
        description="Extrait les investissements/patrimoine financier depuis HATVP XML."
    )
    p.add_argument("--dry-run", action="store_true", help="Ne pas écrire de fichiers")
    p.add_argument("--force", action="store_true", help="Re-télécharger même si en cache")
    p.add_argument("--limit", type=int, default=None, help="Limiter le nombre d'élus")
    p.add_argument("--delay", type=float, default=0.5, help="Délai entre requêtes (défaut 0.5 s)")
    p.add_argument("--test-elu", type=str, default=None, help="Tester un élu précis")
    p.add_argument(
        "--refresh-index", action="store_true",
        help="Forcer le re-téléchargement du CSV index HATVP"
    )
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
    """
    Télécharger et parser le CSV index HATVP.
    Colonnes typiques (d'après la documentation officielle) :
      uuid, nom, prenom, typeDeclaration, dateDepot, url
    Retourne une liste de dicts, une entrée par déclaration.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    if not force_refresh and os.path.exists(INDEX_CACHE):
        age_h = (time.time() - os.path.getmtime(INDEX_CACHE)) / 3600
        if age_h < 24:
            print(f"  ✓ Index CSV en cache (âge : {age_h:.1f} h)")
            with open(INDEX_CACHE, "rb") as f:
                raw = f.read()
        else:
            print(f"  ↻ Cache trop ancien ({age_h:.1f} h), re-téléchargement…")
            raw = None
    else:
        raw = None

    if raw is None:
        print(f"  🔄 Téléchargement index HATVP : {HATVP_INDEX_URL}")
        time.sleep(delay)
        raw = http_get(HATVP_INDEX_URL)
        if not raw:
            raise RuntimeError(f"Impossible de télécharger l'index HATVP : {HATVP_INDEX_URL}")
        with open(INDEX_CACHE, "wb") as f:
            f.write(raw)
        print(f"  ✓ Index téléchargé ({len(raw):,} octets) et mis en cache")

    # Détecter l'encodage (UTF-8 ou latin-1)
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
    """Normaliser un nom pour la comparaison : minuscules, sans accents, sans tirets."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[-\s]+", " ", s).strip()
    return s


def find_declarations_for_elu(
    index: list[dict],
    prenom: str,
    nom: str,
) -> list[dict]:
    """
    Retrouver toutes les déclarations HATVP d'un élu dans l'index CSV.
    Comparaison insensible à la casse et aux accents.
    Retourne la liste triée par date (la plus récente en premier).
    """
    norm_prenom = normalize_name(prenom)
    norm_nom = normalize_name(nom)

    # Noms des colonnes possibles dans le CSV (HATVP a changé les noms au fil du temps)
    # On essaie plusieurs variantes
    matched = []
    for row in index:
        # Extraire nom et prénom depuis les colonnes possibles
        row_nom = (
            row.get("nom") or row.get("Nom") or row.get("NOM") or
            row.get("nomDeclarant") or ""
        ).strip()
        row_prenom = (
            row.get("prenom") or row.get("Prenom") or row.get("PRENOM") or
            row.get("prenomDeclarant") or ""
        ).strip()

        if not row_nom:
            continue

        if (normalize_name(row_nom) == norm_nom and
                normalize_name(row_prenom) == norm_prenom):
            matched.append(row)

    # Tri par date de dépôt décroissante (plus récent en premier)
    def parse_date(row):
        date_str = (
            row.get("dateDepot") or row.get("DateDepot") or
            row.get("date_depot") or ""
        )
        try:
            # Format possible : "31/12/2024 10:03:20" ou "2024-12-31"
            for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return datetime.min

    matched.sort(key=parse_date, reverse=True)
    return matched


def get_xml_url(row: dict) -> str | None:
    """
    Extraire l'URL du fichier XML depuis une ligne du CSV index.
    Le CSV peut avoir une colonne 'url', 'fichier', 'urlFichier', etc.
    """
    url = (
        row.get("url") or row.get("Url") or row.get("URL") or
        row.get("urlFichier") or row.get("lien") or ""
    ).strip()

    if url.startswith("http"):
        return url

    # Si c'est juste un nom de fichier, construire l'URL complète
    fichier = (
        row.get("fichier") or row.get("Fichier") or row.get("nomFichier") or url
    ).strip()
    if fichier:
        if not fichier.endswith(".xml"):
            fichier += ".xml"
        return HATVP_XML_BASE + fichier

    return None


def get_declaration_type(row: dict) -> str:
    """Extraire le type de déclaration depuis une ligne CSV."""
    return (
        row.get("typeDeclaration") or row.get("TypeDeclaration") or
        row.get("type") or row.get("Type") or ""
    ).strip().upper()


# ══════════════════════════════════════════════════════════════════════════════
# Téléchargement et parsing XML
# ══════════════════════════════════════════════════════════════════════════════

def download_xml(url: str, cache_path: str, force: bool = False, delay: float = 0.5) -> bytes | None:
    """Télécharger un XML HATVP (avec cache local)."""
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


def xml_text(element, path: str, default: str = "") -> str:
    """Extraire le texte d'un nœud XML en toute sécurité."""
    if element is None:
        return default
    node = element.find(path)
    if node is not None and node.text:
        t = node.text.strip()
        if t and t != "[Données non publiées]":
            return t
    return default


def parse_montant(s: str) -> float | None:
    """Convertir une chaîne montant en float (gère '12 500', '1 157', etc.)."""
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_instruments_financiers(root: ET.Element) -> list[dict]:
    """
    Parser la section <instrumentsFinanciersDto> du XML DSP.
    Contient les actions cotées, obligations, ETF, PEA, assurance-vie, etc.
    """
    section = root.find(".//instrumentsFinanciersDto")
    if section is None:
        return []

    neant = xml_text(section, "neant").lower()
    if neant == "true":
        return []

    instruments = []
    # Les items sont imbriqués : <items><items>...</items></items>
    for item in section.findall(".//items/items") or section.findall(".//items"):
        # Ignorer les conteneurs vides
        if not any(child.text for child in item):
            continue

        nature_id = xml_text(item, "nature/id") or xml_text(item, "typeInstrument/id") or ""
        nature_label = (
            xml_text(item, "nature/label") or
            xml_text(item, "typeInstrument/label") or
            nature_id
        )
        valeur_str = (
            xml_text(item, "valeur") or
            xml_text(item, "valeurEstimee") or
            xml_text(item, "montant") or ""
        )
        instrument = {
            "type": "instrument_financier",
            "nature": nature_label or nature_id,
            "nature_code": nature_id,
            "description": (
                xml_text(item, "description") or
                xml_text(item, "denomination") or
                xml_text(item, "libelle") or ""
            ),
            "valeur_euro": parse_montant(valeur_str),
            "mode_detention": (
                xml_text(item, "modeDetention/label") or
                xml_text(item, "modeDetention/id") or ""
            ),
            "commentaire": xml_text(item, "commentaire"),
        }

        # Champs optionnels selon la nature
        nb_titres = xml_text(item, "nombreTitres") or xml_text(item, "nbTitres")
        if nb_titres:
            instrument["nb_titres"] = nb_titres

        valeur_unitaire = xml_text(item, "valeurUnitaire")
        if valeur_unitaire:
            instrument["valeur_unitaire_euro"] = parse_montant(valeur_unitaire)

        # Ignorer les lignes totalement vides
        if not instrument["nature"] and not instrument["description"] and instrument["valeur_euro"] is None:
            continue

        instruments.append(instrument)

    return instruments


def parse_participation_financiere(root: ET.Element) -> list[dict]:
    """
    Parser la section <participationFinanciereDto>.
    Contient les participations dans des sociétés (actions non cotées, SARL, SCI, etc.)
    Présente dans DSP et DI.
    """
    section = root.find(".//participationFinanciereDto")
    if section is None:
        return []

    neant = xml_text(section, "neant").lower()
    if neant == "true":
        return []

    participations = []
    for item in section.findall(".//items/items") or section.findall(".//items"):
        if not any(child.text for child in item):
            continue

        nom_societe = xml_text(item, "nomSociete") or xml_text(item, "denomination") or ""
        valeur_str = (
            xml_text(item, "valeurParts") or
            xml_text(item, "valeur") or
            xml_text(item, "montant") or ""
        )
        participation = {
            "type": "participation_financiere",
            "nom_societe": nom_societe,
            "nb_parts": xml_text(item, "nbParts") or xml_text(item, "nombreParts"),
            "valeur_euro": parse_montant(valeur_str),
            "pourcentage": xml_text(item, "pourcentage") or xml_text(item, "tauxDetention"),
            "mode_detention": (
                xml_text(item, "modeDetention/label") or
                xml_text(item, "modeDetention/id") or ""
            ),
            "objet_social": xml_text(item, "objetSocial") or xml_text(item, "activite"),
            "commentaire": xml_text(item, "commentaire"),
        }
        if not participation["nom_societe"] and participation["valeur_euro"] is None:
            continue
        participations.append(participation)

    return participations


def parse_declaration_xml(xml_bytes: bytes, url: str) -> dict:
    """
    Parser un XML de déclaration HATVP et extraire toutes les données financières.
    Retourne un dict structuré.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        print(f"    ⚠ XML invalide ({exc}) : {url}")
        return {}

    # ── Métadonnées générales ──────────────────────────────────────────────────
    general = root.find("general")
    type_decl_id = xml_text(root, "general/typeDeclaration/id") or ""
    type_decl_label = xml_text(root, "general/typeDeclaration/label") or type_decl_id
    date_depot = xml_text(root, "dateDepot")
    uuid = xml_text(root, "uuid")

    declarant_nom = xml_text(root, "general/declarant/nom")
    declarant_prenom = xml_text(root, "general/declarant/prenom")
    qualite = xml_text(root, "general/qualiteDeclarant")
    organe = xml_text(root, "general/organe/labelOrgane")
    mandat = xml_text(root, "general/qualiteMandat/labelTypeMandat")

    result = {
        "uuid": uuid,
        "url_xml": url,
        "type_declaration": type_decl_id,
        "type_declaration_label": type_decl_label,
        "date_depot": date_depot,
        "declarant": f"{declarant_prenom} {declarant_nom}".strip(),
        "qualite": qualite,
        "organe": organe,
        "mandat": mandat,
        # Données financières
        "instruments_financiers": [],
        "participations_financieres": [],
    }

    # ── Instruments financiers (DSP uniquement) ────────────────────────────────
    result["instruments_financiers"] = parse_instruments_financiers(root)

    # ── Participations financières (DSP + DI) ──────────────────────────────────
    result["participations_financieres"] = parse_participation_financiere(root)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Orchestration par élu
# ══════════════════════════════════════════════════════════════════════════════

def fetch_hatvp_finances_for_elu(
    elu: dict,
    index: list[dict],
    force: bool,
    dry_run: bool,
    delay: float,
) -> dict | None:
    """
    Récupérer les données financières HATVP pour un élu.
    Retourne un dict consolidé ou None si aucune déclaration trouvée.
    """
    prenom = elu.get("prenom", "").strip()
    nom = elu.get("nom", "").strip()

    if not prenom or not nom:
        return None

    # Trouver les déclarations dans l'index
    declarations_rows = find_declarations_for_elu(index, prenom, nom)
    if not declarations_rows:
        print(f"    ✗ Aucune déclaration HATVP trouvée pour {prenom} {nom}")
        return None

    print(f"    ✓ {len(declarations_rows)} déclaration(s) trouvée(s)")

    # Séparer DSP et DI, prendre la plus récente de chaque type
    dsp_row = next(
        (r for r in declarations_rows if get_declaration_type(r) in DSP_TYPES),
        None
    )
    di_row = next(
        (r for r in declarations_rows if get_declaration_type(r) in {"DI", "DIM"}),
        None
    )

    result = {
        "prenom": prenom,
        "nom": nom,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "declarations_trouvees": len(declarations_rows),
        "instruments_financiers": [],       # DSP : actions, obligations, fonds, PEA…
        "participations_financieres": [],    # DSP+DI : sociétés non cotées
        "declarations": [],                 # Métadonnées de chaque déclaration parsée
    }

    # ── Parser la DSP (instruments financiers boursiers) ──────────────────────
    for row, label in [(dsp_row, "DSP"), (di_row, "DI")]:
        if row is None:
            continue

        xml_url = get_xml_url(row)
        if not xml_url:
            print(f"    ⚠ URL XML introuvable pour la {label} de {prenom} {nom}")
            continue

        decl_type = get_declaration_type(row)
        date_depot = row.get("dateDepot") or row.get("DateDepot") or "?"
        print(f"    🔄 {label} ({decl_type}, {date_depot}) : {xml_url}")

        if dry_run:
            print(f"    [dry-run] Téléchargement simulé : {xml_url}")
            result["declarations"].append({
                "type": decl_type,
                "url": xml_url,
                "dry_run": True,
            })
            continue

        # Chemin de cache local
        filename = xml_url.split("/")[-1]
        cache_path = os.path.join(CACHE_DIR, "xmls", filename)

        xml_bytes = download_xml(xml_url, cache_path, force=force, delay=delay)
        if not xml_bytes:
            print(f"    ✗ Impossible de télécharger {xml_url}")
            continue

        parsed = parse_declaration_xml(xml_bytes, xml_url)
        if not parsed:
            continue

        # Ajouter les instruments à la liste consolidée
        result["instruments_financiers"].extend(parsed.get("instruments_financiers", []))
        result["participations_financieres"].extend(parsed.get("participations_financieres", []))
        result["declarations"].append({
            "type": parsed.get("type_declaration"),
            "label": parsed.get("type_declaration_label"),
            "date_depot": parsed.get("date_depot"),
            "uuid": parsed.get("uuid"),
            "url": xml_url,
            "qualite": parsed.get("qualite"),
            "organe": parsed.get("organe"),
        })

    return result


def build_resume_hatvp(data: dict) -> dict:
    """Construire un résumé compact à injecter dans elus.json."""
    instruments = data.get("instruments_financiers", [])
    participations = data.get("participations_financieres", [])

    valeur_totale_instruments = sum(
        i["valeur_euro"] for i in instruments if i.get("valeur_euro") is not None
    )
    valeur_totale_participations = sum(
        p["valeur_euro"] for p in participations if p.get("valeur_euro") is not None
    )

    # Regrouper les instruments par nature
    natures: dict[str, int] = {}
    for i in instruments:
        n = i.get("nature", "Autre")
        natures[n] = natures.get(n, 0) + 1

    return {
        "nb_instruments_financiers": len(instruments),
        "nb_participations_societes": len(participations),
        "valeur_totale_instruments_euro": valeur_totale_instruments,
        "valeur_totale_participations_euro": valeur_totale_participations,
        "valeur_totale_euro": valeur_totale_instruments + valeur_totale_participations,
        "types_instruments": natures,
        "nb_declarations_hatvp": data.get("declarations_trouvees", 0),
        "hatvp_scraped_at": data.get("scraped_at", ""),
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
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    print("=" * 65)
    print("💰 SCRAPER HATVP — PATRIMOINE & INSTRUMENTS FINANCIERS")
    print("   Sources : liste.csv + XMLs https://www.hatvp.fr/livraison/")
    if args.dry_run:
        print("   ⚠ MODE DRY-RUN — aucun fichier ne sera écrit")
    print("=" * 65)

    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.join(CACHE_DIR, "xmls"), exist_ok=True)

    # ── Charger l'index CSV HATVP ──────────────────────────────────────────────
    print("\n📥 Chargement de l'index HATVP…")
    try:
        index = load_hatvp_index(force_refresh=args.refresh_index, delay=args.delay)
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return

    # ── Mode test ──────────────────────────────────────────────────────────────
    if args.test_elu:
        print(f"\n🧪 Mode test — élu : {args.test_elu}")

        # Chercher dans elus.json ou créer un profil minimal
        elus = load_elus()
        elu = find_elu_by_name(elus, args.test_elu)
        if not elu:
            parts = args.test_elu.strip().split()
            elu = {
                "id": "test",
                "prenom": parts[0],
                "nom": " ".join(parts[1:]),
            }
        print(f"  Profil : {elu.get('prenom')} {elu.get('nom')}")

        result = fetch_hatvp_finances_for_elu(
            elu, index,
            force=True,
            dry_run=args.dry_run,
            delay=args.delay,
        )

        if result:
            print(f"\n{'=' * 65}")
            print("✅ RÉSULTAT")
            print(f"{'=' * 65}")
            print(f"  Déclarations trouvées : {result['declarations_trouvees']}")
            print(f"  Instruments financiers: {len(result['instruments_financiers'])}")
            print(f"  Participations soc.   : {len(result['participations_financieres'])}")

            if result["instruments_financiers"]:
                print(f"\n  📈 Instruments financiers (extrait) :")
                for i in result["instruments_financiers"][:5]:
                    valeur = f"{i['valeur_euro']:,.0f} €" if i.get("valeur_euro") is not None else "?"
                    print(f"    • {i.get('nature', '?'):25s} | {i.get('description', '?'):30s} | {valeur}")
                if len(result["instruments_financiers"]) > 5:
                    print(f"    … et {len(result['instruments_financiers']) - 5} autres")

            if result["participations_financieres"]:
                print(f"\n  🏢 Participations dans des sociétés :")
                for p in result["participations_financieres"][:5]:
                    valeur = f"{p['valeur_euro']:,.0f} €" if p.get("valeur_euro") is not None else "?"
                    print(f"    • {p.get('nom_societe', '?'):40s} | {valeur}")

            print(f"\n  📊 Résumé :")
            print(json.dumps(build_resume_hatvp(result), ensure_ascii=False, indent=4))
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

    total = len(elus)
    done = 0
    not_found = 0
    failed = 0
    updated: dict[str, dict] = {}

    for i, elu in enumerate(elus, 1):
        prenom = elu.get("prenom", "")
        nom = elu.get("nom", "")
        elu_id = elu.get("id", f"elu-{i}")
        print(f"\n[{i}/{total}] {prenom} {nom}")

        result = fetch_hatvp_finances_for_elu(
            elu, index,
            force=args.force,
            dry_run=args.dry_run,
            delay=args.delay,
        )

        if result is None:
            not_found += 1
        elif result.get("instruments_financiers") or result.get("participations_financieres"):
            done += 1
            resume = build_resume_hatvp(result)
            updated[elu_id] = resume
            # Sauvegarder le détail complet dans un fichier séparé
            if not args.dry_run:
                detail_path = os.path.join(CACHE_DIR, f"{elu_id}.json")
                with open(detail_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  ✓ {len(result['instruments_financiers'])} instruments, "
                  f"{len(result['participations_financieres'])} participations")
        else:
            # Trouvé dans l'index mais néant dans les deux sections
            done += 1
            updated[elu_id] = build_resume_hatvp(result)
            print(f"  ○ Déclarations trouvées mais aucun actif financier déclaré")

        time.sleep(args.delay)

    # ── Mettre à jour elus.json ────────────────────────────────────────────────
    if not args.dry_run and updated:
        all_elus = load_elus()
        for e in all_elus:
            if e["id"] in updated:
                e["hatvp_finances"] = updated[e["id"]]
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
