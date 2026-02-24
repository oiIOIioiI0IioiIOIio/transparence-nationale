#!/usr/bin/env python3
"""
Script de génération des données des élus français.
Sources:
  - HATVP open data (data.gouv.fr) → CSV officiel liste des déclarants
  - HATVP CSV direct (hatvp.fr/livraison) → fallback
  - API HATVP fiche individuelle → déclarations détaillées (placements/actifs)
  - API Assemblée Nationale (nosdeputes.fr / open data AN) → id_an, circonscription

Génère: public/data/elus.json

NOTE sur l'API HATVP REST :
  L'endpoint /rest/api/declarations/list n'est plus disponible publiquement.
  On s'appuie désormais sur les exports open data officiels (CSV) disponibles
  sur data.gouv.fr et hatvp.fr/livraison, qui sont les sources canoniques.
  Les fiches individuelles JSON (par hatvp_id) restent tentées pour enrichissement.
"""

import argparse
import csv
import io
import json
import os
import sys
import time
import unicodedata
import urllib.request
import urllib.parse
import urllib.error

# Chemins relatifs depuis la racine du projet
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")

# ── Sources HATVP ─────────────────────────────────────────────────────────────
# CSV officiel HATVP – export open data (source primaire, stable)
# Disponible via data.gouv.fr et directement sur hatvp.fr
HATVP_DATAGOUV_CSV = (
    "https://www.data.gouv.fr/fr/datasets/r/"
    "b6ca8b0e-b9f3-4b80-97f4-f547bfe55e60"  # dataset HATVP liste déclarants
)
# CSV direct hatvp.fr (fallback si data.gouv.fr indisponible)
HATVP_CSV_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"

# API HATVP fiche individuelle (enrichissement patrimoine/placements)
# ⚠ Tentative : l'endpoint varie selon les versions du portail HATVP.
# On tente plusieurs variantes.
HATVP_API_DECLARATION_VARIANTS = [
    "https://www.hatvp.fr/rest/api/declarations/{hatvp_id}",
    "https://www.hatvp.fr/livraison/opendata/declarations/{hatvp_id}.json",
]

# ── Sources Assemblée Nationale ────────────────────────────────���──────────────
# nosdeputes.fr : données AN remixées, JSON propre et stable
NOSDEPUTES_DEPUTES_URL = "https://www.nosdeputes.fr/deputes/json"
# API open data AN (fallback)
AN_OPENDATA_URL = "https://data.assemblee-nationale.fr/api/v2/deputes/json"

# Indemnités parlementaires de base (brut annuel)
INDEMNITE_DEPUTE = 85_296
INDEMNITE_SENATEUR = 87_480

HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (https://github.com/transparence-nationale)",
    "Accept": "application/json, text/csv, */*",
}

# ── Types d'actifs HATVP reconnus comme "placements" ─────────────────────────
PLACEMENT_CATEGORIES = {
    "valeurs_mobilieres": "Valeurs mobilières",
    "assurance_vie": "Assurance-vie",
    "epargne": "Épargne",
    "parts_sociales": "Parts sociales",
    "autres_placements": "Autres placements",
    "instruments_financiers": "Instruments financiers",
    "actions": "Actions",
    "obligations": "Obligations",
    "opcvm": "OPCVM / Fonds",
    "pea": "PEA",
    "compte_titres": "Compte-titres",
    "crowdfunding": "Crowdfunding / Financement participatif",
}


# ══════════════════════════════════════════════════════════════════════════════
# Utilitaires
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Génère public/data/elus.json depuis HATVP (CSV open data) + API AN."
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Chemin de sortie (défaut : {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limiter le nombre d'élus générés (utile pour les tests)",
    )
    parser.add_argument(
        "--no-detail",
        action="store_true",
        help="Ne pas appeler l'API HATVP individuelle (plus rapide, moins de données)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Délai entre requêtes détaillées HATVP en secondes (défaut : 0.3)",
    )
    return parser.parse_args()

def slugify(text: str) -> str:
    """Convertir un nom en slug ASCII minuscule."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace(" ", "-").replace("'", "-").replace("\u2019", "-").replace("\"", "-")
    text = "".join(c for c in text if c.isalnum() or c == "-")
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-")

def normalize_name(name: str) -> str:
    """Normaliser un nom pour la comparaison (sans accents, minuscules, sans tirets)."""
    name = name.lower().strip()
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.replace("-", " ").replace("'", " ").replace("\u2019", " ")
    name = " ".join(name.split())
    return name

def make_dedup_key(nom: str, prenom: str, hatvp_id: str = "") -> tuple:
    """
    Clé de déduplication robuste.
    Utilise l'id HATVP si disponible (plus fiable que le slug nom+prénom
    qui peut collisionner sur les homonymes ou varier selon les accents).
    """
    if hatvp_id:
        return ("hatvp_id", hatvp_id)
    return ("name", normalize_name(nom), normalize_name(prenom))

def http_get(url: str, timeout: int = 30) -> bytes | None:
    """Effectuer une requête GET et retourner le contenu brut, ou None."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as exc:
        print(f"  ⚠ HTTP {exc.code} → {url}")
    except Exception as exc:
        print(f"  ⚠ Erreur réseau ({url}) : {exc}")
    return None

def parse_amount(val) -> int:
    """Parser un montant financier (str ou number) en entier."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    val = str(val).strip().replace("\u202f", "").replace("\xa0", "")
    val = val.replace(" ", "").replace(",", ".").replace("€", "").replace("EUR", "")
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0

def decode_csv_bytes(raw: bytes) -> str | None:
    """Décoder des bytes CSV avec détection d'encodage."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None

# ══════════════════════════════════════════════════════════════════════════════
# Récupération HATVP (CSV open data — source primaire)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_hatvp_csv_from_url(url: str, label: str) -> list[dict]:
    """Télécharger et parser un CSV HATVP depuis une URL donnée."""
    print(f"🔄 Téléchargement du CSV HATVP ({label})…")
    raw = http_get(url)
    if not raw:
        print(f"  ✗ Impossible de télécharger : {url}")
        return []

    text = decode_csv_bytes(raw)
    if not text:
        print(f"  ✗ Impossible de décoder le CSV depuis {url}")
        return []

    # Détecter le délimiteur (point-virgule ou virgule)
    sample = text[:2000]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    print(f"  ✓ {len(rows)} entrées depuis {label}")
    return rows

def fetch_hatvp_data() -> list[dict]:
    """
    Récupérer la liste des déclarants HATVP.
    Stratégie (CSV open data uniquement, l'API REST /list n'est plus disponible) :
      1. data.gouv.fr (export officiel HATVP, le plus à jour)
      2. hatvp.fr/livraison directement (fallback)
    Retourne une liste de dicts (lignes CSV).
    """
    # Tentative 1 : data.gouv.fr
    rows = fetch_hatvp_csv_from_url(HATVP_DATAGOUV_CSV, "data.gouv.fr")
    if rows:
        return rows

    # Tentative 2 : hatvp.fr direct
    rows = fetch_hatvp_csv_from_url(HATVP_CSV_URL, "hatvp.fr/livraison")
    if rows:
        return rows

    print("  ✗ Aucune source HATVP disponible")
    return []

def fetch_hatvp_declaration_detail(hatvp_id: str) -> dict | None:
    """Récupérer la fiche complète d'un déclarant (placements, patrimoine…)."""
    for url_tpl in HATVP_API_DECLARATION_VARIANTS:
        url = url_tpl.format(hatvp_id=hatvp_id)
        raw = http_get(url, timeout=30)
        if not raw:
            continue
        try:
            data = json.loads(raw.decode("utf-8"))
            return data
        except Exception:
            continue
    return None


def extract_placements_from_detail(detail: dict) -> tuple[int, list[dict]]:
    """Extraire les placements détaillés d'une fiche HATVP complète.
    Retourne : (montant_total_placements, liste_placements)"""
    placements = []

    def _walk(node, depth=0):
        if depth > 20:  # éviter les récursions infinies sur des structures cycliques
            return
        if isinstance(node, list):
            for item in node:
                _walk(item, depth + 1)
        elif isinstance(node, dict):
            type_actif = (
                node.get("typeActif") or node.get("type_actif") or
                node.get("nature") or node.get("categorie") or
                node.get("libelle_categorie") or ""
            ).lower()

            libelle = (
                node.get("libelle") or node.get("denomination") or
                node.get("societe") or node.get("emetteur") or
                node.get("description") or node.get("objet") or ""
            ).strip()

            montant_raw = (
                node.get("valeurEstimee") or node.get("valeur_estimee") or
                node.get("montant") or node.get("valeur") or
                node.get("montantTotal") or node.get("montant_total") or
                node.get("valeurVenale") or None
            )

            devise = node.get("devise", "EUR") or "EUR"
            details = (node.get("details") or node.get("observations") or "").strip()

            is_placement = False
            for key in PLACEMENT_CATEGORIES:
                if key in type_actif or type_actif in key:
                    is_placement = True
                    break
            if not is_placement and montant_raw and libelle and any(
                kw in type_actif for kw in [
                    "action", "obligation", "part", "titre", "fonds",
                    "opcvm", "pea", "compte", "assurance", "épargne",
                    "financi", "mobili", "placement", "portefeuille",
                ]
            ):
                is_placement = True

            if is_placement and (libelle or montant_raw):
                type_norm = "Autres placements"
                for key, label in PLACEMENT_CATEGORIES.items():
                    if key in type_actif or any(kw in type_actif for kw in key.split("_")):
                        type_norm = label
                        break
                placements.append({
                    "type": type_norm,
                    "libelle": libelle or type_norm,
                    "montant": parse_amount(montant_raw),
                    "devise": devise.upper(),
                    "details": details,
                })

            for v in node.values():
                if isinstance(v, (dict, list)):
                    _walk(v, depth + 1)

    _walk(detail)

    # Dédupliquer (même libellé + montant + type)
    seen: set[tuple] = set()
    unique: list[dict] = []
    for p in placements:
        key = (p["libelle"].lower(), p["montant"], p["type"])
        if key not in seen:
            seen.add(key)
            unique.append(p)

    total = sum(p["montant"] for p in unique)
    return total, unique

# ══════════════════════════════════════════════════════════════════════════════
# Récupération Assemblée Nationale
# ══════════════════════════════════════════════════════════════════════════════

def fetch_an_deputes() -> dict[str, dict]:
    """Récupérer les députés depuis nosdeputes.fr avec fallback AN open data.
    Retourne un dict slug → {id_an, slug_an, region, groupe}."""
    print("🔄 Récupération des députés (nosdeputes.fr)…")
    deputes: dict[str, dict] = {}

    # Tentative 1 : nosdeputes.fr
    raw = http_get(NOSDEPUTES_DEPUTES_URL)
    if raw:
        try:
            result = json.loads(raw.decode("utf-8"))
            items = result.get("deputes", [])
            for item in items:
                dep = item.get("depute", item)
                prenom = (dep.get("prenom") or dep.get("prenom_usuel") or "").strip()
                nom = (dep.get("nom") or dep.get("nom_de_famille") or "").strip()
                id_an = str(dep.get("id_an") or dep.get("uid") or "").strip()
                slug_an = dep.get("slug", "")
                region = (dep.get("nom_circo") or dep.get("circo") or "").strip()
                groupe_raw = dep.get("groupe", "")
                groupe = (
                    groupe_raw.get("sigle", "") if isinstance(groupe_raw, dict)
                    else dep.get("groupe_sigle", "")
                ).strip()
                if prenom and nom:
                    key = slugify(f"{prenom} {nom}")
                    deputes[key] = {
                        "id_an": id_an,
                        "slug_an": slug_an,
                        "region": region,
                        "groupe": groupe,
                    }
            print(f"  ✓ {len(deputes)} députés depuis nosdeputes.fr")
            return deputes
        except Exception as exc:
            print(f"  ⚠ Parsing nosdeputes.fr : {exc}")

    # Tentative 2 : open data AN
    print("  ↩ Fallback : API open data Assemblée Nationale…")
    raw = http_get(AN_OPENDATA_URL)
    if not raw:
        print("  ⚠ API AN indisponible, enrichissement id_an ignoré")
        return deputes

    try:
        result = json.loads(raw.decode("utf-8"))
        items = result.get("deputes", [])
        for item in items:
            dep = item.get("depute", item)
            prenom = (dep.get("prenom") or dep.get("prenom_usuel") or "").strip()
            nom = (dep.get("nom") or dep.get("nom_de_famille") or "").strip()
            uid = dep.get("uid", {})
            id_an = uid if isinstance(uid, str) else uid.get("#text", "")
            region = ""
            mandats = dep.get("mandats", {})
            if isinstance(mandats, dict):
                for mandat in mandats.get("mandat", []):
                    if isinstance(mandat, dict) and mandat.get("typeOrgane") == "CIRCONSCRIPTION":
                        region = mandat.get("libelle", "")
                        break
            if prenom and nom:
                key = slugify(f"{prenom} {nom}")
                deputes[key] = {"id_an": id_an, "slug_an": "", "region": region, "groupe": ""}
        print(f"  ✓ {len(deputes)} députés depuis l'API AN (fallback)")
    except Exception as exc:
        print(f"  ⚠ Parsing API AN : {exc}")

    return deputes

# ══════════════════════════════════════════════════════════════════════════════
# Conversion ligne CSV → élu
# ══════════════════════════════════════════════════════════════════════════════

def _get_field(row: dict, *keys: str, default: str = "") -> str:
    """Chercher une valeur dans un dict en testant plusieurs clés (insensible à la casse)."""
    row_lower = {k.lower(): v for k, v in row.items()}
    for key in keys:
        v = row_lower.get(key.lower(), "")
        if v and str(v).strip():
            return str(v).strip()
    return default


def hatvp_csv_row_to_elu(row: dict, an_map: dict[str, dict]) -> dict | None:
    """Convertir une ligne CSV HATVP en structure élu."""
    nom = _get_field(row, "nom", "lastName", "last_name", "NOM").upper()
    prenom = _get_field(row, "prenom", "prénom", "prenom_usuel", "firstName", "PRENOM").title()

    if not nom or not prenom:
        return None

    hatvp_id = _get_field(row, "id", "hatvp_id", "identifiant", "ID")
    fonction_raw = _get_field(row, "fonction", "Fonction", "mandat", "Mandat", "qualite", "role")
    parti = _get_field(row, "parti", "Parti", "groupe", "formation_politique")

    elu = _build_elu(nom, prenom, hatvp_id, fonction_raw, parti, an_map)
    if elu is None:
        return None

    # Données patrimoniales agrégées depuis le CSV
    pat_val = _get_field(row, "total_patrimoine", "patrimoine_total", "Patrimoine total", "montant_total")
    if pat_val:
        elu["patrimoine"] = parse_amount(pat_val)
        elu["patrimoine_source"] = "hatvp_csv"

    immo_val = _get_field(row, "total_immobilier", "immobilier", "Immobilier")
    if immo_val:
        elu["immobilier"] = parse_amount(immo_val)

    place_val = _get_field(row, "total_placements", "placements", "Placements")
    if place_val:
        elu["placements_montant"] = parse_amount(place_val)

    return elu


def _build_elu(
    nom: str, prenom: str, hatvp_id: str, fonction_raw: str,
    parti: str, an_map: dict[str, dict]
) -> dict | None:
    """Construire le dict élu commun."""
    elu_id = slugify(f"{prenom} {nom}")
    if not elu_id:
        return None

    an_info = an_map.get(elu_id, {})
    id_an = an_info.get("id_an", "")
    slug_an = an_info.get("slug_an", "")
    region = an_info.get("region", "")
    groupe = an_info.get("groupe", "")

    revenus = INDEMNITE_DEPUTE
    mandats = []
    fonction = fonction_raw or "Élu(e)"
    fonction_lower = fonction_raw.lower()

    if "sénateur" in fonction_lower or "sénatrice" in fonction_lower:
        revenus = INDEMNITE_SENATEUR
        mandats = ["Sénateur(trice)"]
        if not fonction_raw:
            fonction = "Sénateur(trice)"
    elif "député" in fonction_lower or "députée" in fonction_lower:
        mandats = ["Député(e)"]
        if region and "de" not in fonction_lower:
            fonction = f"Député(e) de {region}"
    elif "ministre" in fonction_lower:
        mandats = [fonction_raw]
        revenus = 0
    else:
        mandats = [fonction_raw] if fonction_raw else ["Élu(e)"]

    # URLs
    hatvp_url = (
        f"https://www.hatvp.fr/fiche-nominative/?declarant="
        f"{urllib.parse.quote(f'{nom}-{prenom}') }"
    )
    an_url = ""
    if id_an:
        an_url = f"https://www.assemblee-nationale.fr/dyn/deputes/{id_an}"
    elif slug_an:
        an_url = f"https://www.nosdeputes.fr/{slug_an}"

    return {
        "id": elu_id,
        "nom": nom,
        "prenom": prenom,
        "fonction": fonction,
        "region": region,
        "groupe": groupe,
        "revenus": revenus,
        "patrimoine": 0,
        "immobilier": 0,
        "placements_montant": 0,
        "placements": [],
        "patrimoine_source": "non_disponible",
        "mandats": mandats,
        "parti": parti or groupe,
        "hatvp_id": hatvp_id,
        "id_an": id_an,
        "photo": "/photos/placeholder.jpg",
        "liens": {
            "assemblee": an_url,
            "hatvp": hatvp_url,
            "senat": "",
            "wikipedia": "",
        },
    }


def enrich_with_detail(elu: dict, delay: float) -> None:
    """Enrichir un élu avec les données détaillées de l'API HATVP (modifie en place)."""
    hatvp_id = elu.get("hatvp_id", "")
    if not hatvp_id:
        return

    time.sleep(delay)
    detail = fetch_hatvp_declaration_detail(hatvp_id)
    if not detail:
        return

    patrimoine_raw = (
        detail.get("totalPatrimoine") or detail.get("total_patrimoine") or
        detail.get("patrimoineTotal") or detail.get("montant_total") or None
    )
    if patrimoine_raw:
        elu["patrimoine"] = parse_amount(patrimoine_raw)
        elu["patrimoine_source"] = "hatvp_api"

    immo_raw = (
        detail.get("totalImmobilier") or detail.get("total_immobilier") or
        detail.get("bienImmobilier") or None
    )
    if immo_raw:
        elu["immobilier"] = (
            parse_amount(immo_raw) if not isinstance(immo_raw, list)
            else sum(parse_amount(b.get("valeurVenale") or b.get("valeur") or 0) for b in immo_raw)
        )

    total_place, placements_list = extract_placements_from_detail(detail)
    if placements_list:
        elu["placements"] = placements_list
        elu["placements_montant"] = total_place
        if not patrimoine_raw:
            elu["patrimoine"] = elu.get("immobilier", 0) + total_place
            elu["patrimoine_source"] = "hatvp_api_partiel"

# ══════════════════════════════════════════════════════════════════════════════
# Déduplication et fusion
# ══════════════════════════════════════════════════════════════════════════════

def deduplicate_elus(elus: list[dict]) -> list[dict]:
    """
    Dédupliquer une liste d'élus.
    Stratégie (par ordre de priorité) :
      1. hatvp_id identique → même personne, garder le plus complet
      2. (nom_normalisé, prenom_normalisé) identique ET hatvp_id vide → fusionner
    """
    # Index par hatvp_id (si non vide)
    by_hatvp_id: dict[str, dict] = {}
    # Index par (nom_norm, prenom_norm) pour ceux sans hatvp_id
    by_name: dict[tuple, dict] = {}
    result_order: list[str] = []  # pour préserver l'ordre
    slug_map: dict[str, dict] = {}  # slug → elu final

    def _merge_into(base: dict, other: dict) -> None:
        """Fusionner `other` dans `base` (base a la priorité sur les champs non nuls)."""
        for key, value in other.items():
            if key == "liens" and isinstance(value, dict):
                for lk, lv in value.items():
                    if lv and not base["liens"].get(lk):
                        base["liens"][lk] = lv
            elif key == "placements" and value:
                base[key] = value
            elif key in ("patrimoine", "placements_montant", "immobilier") and value:
                if not base.get(key):
                    base[key] = value
            elif key not in base or not base[key]:
                base[key] = value

    for elu in elus:
        hatvp_id = elu.get("hatvp_id", "").strip()
        nom_norm = normalize_name(elu.get("nom", ""))
        prenom_norm = normalize_name(elu.get("prenom", ""))

        if hatvp_id:
            if hatvp_id in by_hatvp_id:
                _merge_into(by_hatvp_id[hatvp_id], elu)
                continue
            else:
                by_hatvp_id[hatvp_id] = elu
                slug_map[elu["id"]] = elu
                result_order.append(hatvp_id)
        else:
            name_key = (nom_norm, prenom_norm)
            if name_key in by_name:
                _merge_into(by_name[name_key], elu)
                continue
            else:
                by_name[name_key] = elu
                slug_map[elu["id"]] = elu
                result_order.append(f"__name__{nom_norm}__{prenom_norm}")

    # Reconstruire la liste dans l'ordre d'insertion
    seen_keys: set[str] = set()
    final: list[dict] = []
    for key in result_order:
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if key.startswith("__name__"):
            _, nom_norm, prenom_norm = key.split("__name__")[1].split("__", 1) if "__name__" in key else ("", "", "")
            # On reconstruit la clé proprement
            parts = key[len("__name__") :].split("__")
            if len(parts) == 2:
                elu = by_name.get((parts[0], parts[1]))
                if elu:
                    final.append(elu)
        else:
            elu = by_hatvp_id.get(key)
            if elu:
                final.append(elu)

    return final


def merge_with_existing(new_elus: list[dict], existing_elus: list[dict]) -> list[dict]:
    """
    Fusionner les nouveaux élus avec les existants.
    Priorité : nouvelles données > existantes (sauf placements détaillés existants).
    """
    # Index existants par hatvp_id puis par slug
    existing_by_hatvp: dict[str, dict] = {}
    existing_by_slug: dict[str, dict] = {}
    for e in existing_elus:
        hid = e.get("hatvp_id", "").strip()
        if hid:
            existing_by_hatvp[hid] = e
        existing_by_slug[e.get("id", "")] = e

    result_map: dict[str, dict] = {e.get("id", ""): e for e in existing_elus}

    for elu in new_elus:
        eid = elu.get("id", "")
        hid = elu.get("hatvp_id", "").strip()

        # Chercher l'existant par hatvp_id d'abord, puis par slug
        existing = existing_by_hatvp.get(hid) if hid else existing_by_slug.get(eid)

        if existing:
            ex_id = existing.get("id", "")
            for key, value in elu.items():
                if key == "liens" and isinstance(value, dict):
                    for lk, lv in value.items():
                        if lv and not existing["liens"].get(lk):
                            existing["liens"][lk] = lv
                elif key == "placements" and value:
                    existing[key] = value
                elif key in ("patrimoine", "placements_montant", "immobilier") and value:
                    existing[key] = value
                elif key not in existing or not existing[key]:
                    existing[key] = value
            result_map[ex_id] = existing
        else:
            result_map[eid] = elu

    return list(result_map.values())

# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    print("=" * 60)
    print("🗳️  GÉNÉRATEUR DE DONNÉES ÉLUS FRANÇAIS")
    print("   Source HATVP : CSV open data (data.gouv.fr / hatvp.fr)")
    print("=" * 60)

    # Charger les données existantes
    existing_elus: list[dict] = []
    if os.path.exists(args.output):
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                existing_elus = json.load(f)
            print(f"✓ {len(existing_elus)} élus existants chargés depuis {args.output}")
        except Exception as exc:
            print(f"⚠ Impossible de charger {args.output} : {exc}")

    # ── Récupération AN ───────────────────────────────────────────────────────
    an_map = fetch_an_deputes()
    time.sleep(0.3)

    # ── Récupération HATVP (CSV open data) ───────────────────────────────────
    hatvp_rows = fetch_hatvp_data()
    if not hatvp_rows:
        print("✗ Aucune donnée HATVP disponible. Arrêt.")
        sys.exit(1)

    # ── Conversion en élus ────────────────────────────────────────────────────
    raw_elus: list[dict] = []
    for row in hatvp_rows:
        elu = hatvp_csv_row_to_elu(row, an_map)
        if elu:
            raw_elus.append(elu)

    print(f"✓ {len(raw_elus)} élus convertis depuis HATVP (avant déduplication)")

    # ── Déduplication ─────────────────────────────────────────────────────────
    new_elus = deduplicate_elus(raw_elus)
    print(f"✓ {len(new_elus)} élus uniques (après déduplication)")
    if len(raw_elus) - len(new_elus) > 0:
        print(f"  → {len(raw_elus) - len(new_elus)} doublon(s) supprimé(s)")

    # ── Enrichissement avec les fiches détaillées HATVP ──────────────────────
    if not args.no_detail:
        elus_with_id = [e for e in new_elus if e.get("hatvp_id")]
        total_detail = len(elus_with_id) if not args.limit else min(args.limit, len(elus_with_id))
        print(f"\n🔍 Enrichissement détaillé pour {total_detail} élus (avec hatvp_id)…")
        for i, elu in enumerate(elus_with_id[:total_detail], 1):
            print(
                f"  [{i}/{total_detail}] {elu['prenom']} {elu['nom']} "
                f"(id={elu['hatvp_id']})",
                end="",
                flush=True,
            )
            enrich_with_detail(elu, args.delay)
            n_place = len(elu.get("placements", []))
            print(f" → {n_place} placement(s), patrimoine={elu['patrimoine']:,}€")
    else:
        print("ℹ Enrichissement détaillé désactivé (--no-detail)")

    # ── Fusion avec les existants + tri ──────────────────────────────────────
    merged = merge_with_existing(new_elus, existing_elus)
    merged.sort(key=lambda e: (e.get("nom", ""), e.get("prenom", "")))

    if args.limit:
        merged = merged[: args.limit]

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✓ {len(merged)} élus générés → {args.output}")
    n_with_placements = sum(1 for e in merged if e.get("placements"))
    n_with_id_an = sum(1 for e in merged if e.get("id_an"))
    print(f"  dont {n_with_placements} avec placements détaillés")
    print(f"  dont {n_with_id_an} avec id_an (photo AN disponible)")
    print("=" * 60)


if __name__ == "__main__":
    main()