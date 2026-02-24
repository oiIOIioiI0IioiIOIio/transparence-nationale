#!/usr/bin/env python3
"""
Script de génération des données des élus français.
Sources:
  - API HATVP (JSON) → déclarations détaillées avec liste des placements/actifs
  - Fallback: HATVP CSV (liste.csv) si l'API JSON est indisponible
  - API Assemblée Nationale (open data) → id_an, circonscription
Génère: public/data/elus.json
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

# ── Sources HATVP ──────────────────────────────────────────────────────────────
# CSV de liste (fallback)
HATVP_CSV_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"
# API REST HATVP : liste des déclarants paginée
HATVP_API_DECLARANTS = "https://www.hatvp.fr/rest/api/declarations/list"
# API REST HATVP : fiche complète d'un déclarant (remplacer {id} par l'id HATVP)
HATVP_API_DECLARATION = "https://www.hatvp.fr/rest/api/declarations/{hatvp_id}"

# ── Sources Assemblée Nationale ────────────────────────────────────────────────
# Endpoint nosdeputes.fr (données AN remixées, stable et JSON propre)
NOSDEPUTES_DEPUTES_URL = "https://www.nosdeputes.fr/deputes/json"
# Endpoint officiel open data AN (fallback)
AN_OPENDATA_URL = "https://data.assemblee-nationale.fr/api/v2/deputes/json"

# Indemnités parlementaires de base (brut annuel)
INDEMNITE_DEPUTE = 85296
INDEMNITE_SENATEUR = 87480

HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (https://github.com/transparence-nationale)",
    "Accept": "application/json",
}

# ── Types d'actifs HATVP reconnus comme "placements" ──────────────────────────
# Les clés correspondent aux libellés ou codes retournés par l'API HATVP
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
# ══════════════════��═══════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Génère public/data/elus.json depuis HATVP (API JSON) + API AN."
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
        help="Ne pas appeler l'API HATVP détaillée (plus rapide, moins de données)",
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
    text = text.replace(" ", "-").replace("'", "-").replace("\u2019", "-")
    text = "".join(c for c in text if c.isalnum() or c == "-")
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-")


def http_get(url: str, timeout: int = 25) -> bytes | None:
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


# ══════════════════════════════════════════════════════════════════════════════
# Récupération HATVP
# ══════════════════════════════════════════════════════════════════════════════

def fetch_hatvp_declarants_api() -> list[dict]:
    """
    Récupérer la liste paginée des déclarants via l'API REST HATVP.
    Retourne une liste de dicts avec au moins : nom, prenom, id (hatvp_id), fonction.
    """
    print("🔄 Récupération des déclarants HATVP via l'API REST…")
    all_items = []
    page = 1
    page_size = 100

    while True:
        params = urllib.parse.urlencode({"page": page, "size": page_size})
        url = f"{HATVP_API_DECLARANTS}?{params}"
        raw = http_get(url)
        if not raw:
            if page == 1:
                print("  ⚠ API HATVP indisponible, bascule sur le CSV")
                return []
            break

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            print(f"  ⚠ Parsing JSON HATVP page {page} : {exc}")
            break

        # L'API HATVP retourne typiquement {"items": [...], "total": N}
        # ou directement une liste selon la version
        items = data if isinstance(data, list) else data.get("items", data.get("results", data.get("declarations", [])))
        if not items:
            break

        all_items.extend(items)
        print(f"  … page {page} → {len(items)} entrées (total : {len(all_items)})")

        # Pagination : s'arrêter si on a tout récupéré
        total = data.get("total", data.get("totalItems", None)) if isinstance(data, dict) else None
        if total and len(all_items) >= total:
            break
        if len(items) < page_size:
            break
        page += 1
        time.sleep(0.1)

    print(f"✓ {len(all_items)} déclarants HATVP récupérés via l'API")
    return all_items


def fetch_hatvp_csv() -> list[dict]:
    """Télécharger et parser le CSV HATVP (fallback)."""
    print(f"🔄 Téléchargement du CSV HATVP (fallback)…")
    raw = http_get(HATVP_CSV_URL)
    if not raw:
        print("✗ Impossible de télécharger le CSV HATVP")
        return []

    for encoding in ("utf-8-sig", "latin-1", "utf-8"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        print("✗ Impossible de décoder le CSV HATVP")
        return []

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    print(f"✓ {len(rows)} déclarants récupérés depuis le CSV HATVP")
    return rows


def fetch_hatvp_declaration_detail(hatvp_id: str) -> dict | None:
    """
    Récupérer la fiche complète d'un déclarant (placements détaillés, patrimoine, etc.).
    Retourne le dict JSON brut ou None.
    """
    url = HATVP_API_DECLARATION.format(hatvp_id=hatvp_id)
    raw = http_get(url, timeout=30)
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def extract_placements_from_detail(detail: dict) -> tuple[int, list[dict]]:
    """
    Extraire les placements détaillés d'une fiche HATVP complète.

    L'API HATVP structure les actifs dans plusieurs nœuds selon le type de
    déclaration (parlementaire / ministérielle / ...).
    On remonte les blocs communs reconnus et on construit une liste normalisée.

    Retourne : (montant_total_placements, liste_placements)
    Chaque placement : {
        "type": str,         # catégorie normalisée
        "libelle": str,      # description / nom de la société
        "montant": int,      # valeur estimée en €
        "devise": str,       # EUR par défaut
        "details": str,      # informations complémentaires
    }
    """
    placements = []

    # Chemins possibles dans la réponse HATVP selon la version de l'API
    # On cherche plusieurs nœuds potentiels
    def _walk(node, path=""):
        """Parcourir récursivement le JSON pour trouver les actifs financiers."""
        if isinstance(node, list):
            for item in node:
                _walk(item, path)
        elif isinstance(node, dict):
            # Détecter un bloc "actif" / "placement" / "valeur mobilière"
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

            # Identifier si ce nœud est un actif financier (placement)
            is_placement = False
            for key in PLACEMENT_CATEGORIES:
                if key in type_actif or type_actif in key:
                    is_placement = True
                    break
            # Heuristique supplémentaire : présence d'un montant + libellé société
            if not is_placement and montant_raw and libelle and any(
                kw in type_actif for kw in [
                    "action", "obligation", "part", "titre", "fonds",
                    "opcvm", "pea", "compte", "assurance", "épargne",
                    "financi", "mobili", "placement", "portefeuille",
                ]
            ):
                is_placement = True

            if is_placement and (libelle or montant_raw):
                # Normaliser le type
                type_norm = "Autres placements"
                for key, label in PLACEMENT_CATEGORIES.items():
                    if key in type_actif or any(
                        kw in type_actif for kw in key.split("_")
                    ):
                        type_norm = label
                        break

                placements.append({
                    "type": type_norm,
                    "libelle": libelle or type_norm,
                    "montant": parse_amount(montant_raw),
                    "devise": devise.upper(),
                    "details": details,
                })

            # Continuer la traversée sur les enfants
            for v in node.values():
                if isinstance(v, (dict, list)):
                    _walk(v, path + "." + str(list(node.keys())[0] if node else ""))

    _walk(detail)

    # Dédupliquer (même libellé + montant)
    seen = set()
    unique = []
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
    """
    Récupérer les députés depuis nosdeputes.fr (JSON propre) avec fallback AN opendata.
    Retourne un dict slug → {id_an, id_circo, region, groupe}.
    """
    print("🔄 Récupération des députés (nosdeputes.fr)…")
    deputes: dict[str, dict] = {}

    # ── Tentative 1 : nosdeputes.fr ──────────────────────────────────────────
    raw = http_get(NOSDEPUTES_DEPUTES_URL)
    if raw:
        try:
            result = json.loads(raw.decode("utf-8"))
            # {"deputes": [{"depute": {...}}, ...]}
            items = result.get("deputes", [])
            for item in items:
                dep = item.get("depute", item)
                prenom = (dep.get("prenom") or dep.get("prenom_usuel") or "").strip()
                nom = (dep.get("nom") or dep.get("nom_de_famille") or "").strip()
                id_an = str(dep.get("id_an") or dep.get("uid") or "").strip()
                slug_an = dep.get("slug", "")
                region = (dep.get("nom_circo") or dep.get("circo") or "").strip()
                groupe = (
                    dep.get("groupe_sigle") or
                    dep.get("groupe", {}).get("sigle", "") if isinstance(dep.get("groupe"), dict) else ""
                ).strip()
                if prenom and nom:
                    key = slugify(f"{prenom} {nom}")
                    deputes[key] = {
                        "id_an": id_an,
                        "slug_an": slug_an,
                        "region": region,
                        "groupe": groupe,
                    }
            print(f"✓ {len(deputes)} députés récupérés depuis nosdeputes.fr")
            return deputes
        except Exception as exc:
            print(f"  ⚠ Parsing nosdeputes.fr : {exc}")

    # ── Tentative 2 : API open data AN ───────────────────────────────────────
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
        print(f"✓ {len(deputes)} députés récupérés depuis l'API AN (fallback)")
    except Exception as exc:
        print(f"  ⚠ Parsing API AN : {exc}")

    return deputes


# ══════════════════════════════════════════════════════════════════════════════
# Conversion ligne → élu
# ══════════════════════════════════════════════════════════════════════════════

def hatvp_api_item_to_elu(item: dict, an_map: dict[str, dict]) -> dict | None:
    """Convertir un item de l'API HATVP en structure élu (sans détails placements)."""
    nom = (
        item.get("nom") or item.get("lastName") or item.get("last_name") or ""
    ).strip().upper()
    prenom = (
        item.get("prenom") or item.get("firstName") or item.get("first_name") or
        item.get("prenom_usuel") or ""
    ).strip().title()

    if not nom or not prenom:
        return None

    hatvp_id = str(
        item.get("id") or item.get("hatvp_id") or item.get("identifiant") or ""
    ).strip()

    fonction_raw = (
        item.get("fonction") or item.get("mandat") or item.get("role") or
        item.get("qualite") or ""
    ).strip()

    parti = (item.get("parti") or item.get("groupe") or item.get("formation_politique") or "").strip()

    return _build_elu(nom, prenom, hatvp_id, fonction_raw, parti, an_map)


def hatvp_csv_row_to_elu(row: dict, an_map: dict[str, dict]) -> dict | None:
    """Convertir une ligne CSV HATVP en structure élu."""
    nom = (row.get("nom") or row.get("Nom") or "").strip().upper()
    prenom = (row.get("prenom") or row.get("Prénom") or row.get("prenom_usuel") or "").strip().title()
    if not nom or not prenom:
        return None

    hatvp_id = str(row.get("id") or row.get("hatvp_id") or row.get("identifiant") or "").strip()
    fonction_raw = (
        row.get("fonction") or row.get("Fonction") or
        row.get("mandat") or row.get("Mandat") or ""
    ).strip()
    parti = (row.get("parti") or row.get("Parti") or row.get("groupe") or "").strip()

    elu = _build_elu(nom, prenom, hatvp_id, fonction_raw, parti, an_map)
    if elu is None:
        return None

    # Données patrimoniales depuis le CSV (agrégées)
    def _get(*keys):
        for k in keys:
            v = row.get(k)
            if v:
                return v
        return ""

    pat_val = _get("total_patrimoine", "patrimoine_total", "Patrimoine total", "montant_total")
    if pat_val:
        elu["patrimoine"] = parse_amount(pat_val)
        elu["patrimoine_source"] = "hatvp_csv"

    immo_val = _get("total_immobilier", "immobilier", "Immobilier")
    if immo_val:
        elu["immobilier"] = parse_amount(immo_val)

    place_val = _get("total_placements", "placements", "Placements")
    if place_val:
        elu["placements_montant"] = parse_amount(place_val)

    return elu


def _build_elu(
    nom: str, prenom: str, hatvp_id: str, fonction_raw: str,
    parti: str, an_map: dict[str, dict]
) -> dict | None:
    """Construire le dict élu commun."""
    elu_id = slugify(f"{prenom} {nom}")
    an_info = an_map.get(elu_id, {})
    id_an = an_info.get("id_an", "")
    slug_an = an_info.get("slug_an", "")
    region = an_info.get("region", "")
    groupe = an_info.get("groupe", "")

    revenus = INDEMNITE_DEPUTE
    mandats = []
    fonction = fonction_raw or "Élu(e)"

    if "sénateur" in fonction.lower() or "sénatrice" in fonction.lower():
        revenus = INDEMNITE_SENATEUR
        mandats = ["Sénateur(trice)"]
        if not fonction_raw:
            fonction = "Sénateur(trice)"
    elif "député" in fonction.lower() or "députée" in fonction.lower():
        mandats = ["Député(e)"]
        if region and "de" not in fonction.lower():
            fonction = f"Député(e) de {region}"
    elif "ministre" in fonction.lower():
        mandats = [fonction_raw]
        revenus = 0  # rémunération ministérielle distincte
    else:
        mandats = [fonction_raw] if fonction_raw else ["Élu(e)"]

    # URLs
    hatvp_url = f"https://www.hatvp.fr/fiche-nominative/?declarant={urllib.parse.quote(f'{nom}-{prenom}')}"
    an_url = ""
    if id_an:
        # URL canonique AN
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
        "placements": [],          # liste détaillée des placements
        "patrimoine_source": "non_disponible",
        "mandats": mandats,
        "parti": parti or groupe,
        "hatvp_id": hatvp_id,
        "photo": "/photos/placeholder.jpg",
        "liens": {
            "assemblee": an_url,
            "hatvp": hatvp_url,
            "senat": "",
            "wikipedia": "",
        },
    }


def enrich_with_detail(elu: dict, delay: float) -> None:
    """
    Enrichir un élu avec les données détaillées de l'API HATVP.
    Modifie `elu` en place.
    """
    hatvp_id = elu.get("hatvp_id", "")
    if not hatvp_id:
        return

    time.sleep(delay)
    detail = fetch_hatvp_declaration_detail(hatvp_id)
    if not detail:
        return

    # ── Patrimoine global ──────────────────────────────────────────────────────
    patrimoine_raw = (
        detail.get("totalPatrimoine") or detail.get("total_patrimoine") or
        detail.get("patrimoineTotal") or detail.get("montant_total") or None
    )
    if patrimoine_raw:
        elu["patrimoine"] = parse_amount(patrimoine_raw)
        elu["patrimoine_source"] = "hatvp_api"

    # ── Immobilier ─────────────────────────────────────────────────────────────
    immo_raw = (
        detail.get("totalImmobilier") or detail.get("total_immobilier") or
        detail.get("bienImmobilier") or None
    )
    if immo_raw:
        elu["immobilier"] = parse_amount(immo_raw) if not isinstance(immo_raw, list) else sum(
            parse_amount(b.get("valeurVenale") or b.get("valeur") or 0) for b in immo_raw
        )

    # ── Placements détaillés ───────────────────────────────────────────────────
    total_place, placements_list = extract_placements_from_detail(detail)
    if placements_list:
        elu["placements"] = placements_list
        elu["placements_montant"] = total_place
        if not patrimoine_raw:
            # Recalcul si pas de total global
            elu["patrimoine"] = elu.get("immobilier", 0) + total_place
            elu["patrimoine_source"] = "hatvp_api_partiel"


# ════════════════════���═════════════════════════════════════════════════════════
# Fusion
# ══════════════════════════════════════════════════════════════════════════════

def merge_with_existing(new_elus: list[dict], existing_elus: list[dict]) -> list[dict]:
    """
    Fusionner les nouveaux élus avec les existants.
    Les placements détaillés des nouvelles données ont la priorité.
    """
    existing_map = {e["id"]: e for e in existing_elus}

    for elu in new_elus:
        eid = elu["id"]
        if eid in existing_map:
            existing = existing_map[eid]
            for key, value in elu.items():
                if key == "liens" and isinstance(value, dict):
                    for lk, lv in value.items():
                        if lv and not existing["liens"].get(lk):
                            existing["liens"][lk] = lv
                elif key == "placements" and value:
                    # Les placements détaillés remplacent toujours
                    existing[key] = value
                elif key in ("patrimoine", "placements_montant", "immobilier") and value:
                    existing[key] = value
                elif key not in existing or not existing[key]:
                    existing[key] = value
        else:
            existing_map[eid] = elu

    return list(existing_map.values())


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    print("=" * 60)
    print("🗳️  GÉNÉRATEUR DE DONNÉES ÉLUS FRANÇAIS")
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

    # ── Récupération AN ────────────────────────────────────────────────────────
    an_map = fetch_an_deputes()
    time.sleep(0.3)

    # ── Récupération HATVP ────────────────────────────────────────────────────
    use_csv = False
    hatvp_items = fetch_hatvp_declarants_api()
    if not hatvp_items:
        use_csv = True
        hatvp_items = fetch_hatvp_csv()

    # ── Conversion en élus ────────────────────────────────────────────────────
    new_elus: list[dict] = []
    seen_ids: set[str] = set()

    for item in hatvp_items:
        if use_csv:
            elu = hatvp_csv_row_to_elu(item, an_map)
        else:
            elu = hatvp_api_item_to_elu(item, an_map)

        if elu and elu["id"] not in seen_ids:
            seen_ids.add(elu["id"])
            new_elus.append(elu)

    print(f"✓ {len(new_elus)} élus convertis depuis HATVP")

    # ── Enrichissement avec les fiches détaillées ─────────────────────────────
    if not args.no_detail and not use_csv:
        total_detail = len(new_elus) if not args.limit else min(args.limit, len(new_elus))
        print(f"\n🔍 Enrichissement détaillé pour {total_detail} élus…")
        for i, elu in enumerate(new_elus[:total_detail], 1):
            if elu.get("hatvp_id"):
                print(f"  [{i}/{total_detail}] {elu['prenom']} {elu['nom']} (id={elu['hatvp_id']})", end="")
                enrich_with_detail(elu, args.delay)
                n_place = len(elu.get("placements", []))
                print(f" → {n_place} placement(s), patrimoine={elu['patrimoine']:,}€")
    elif args.no_detail:
        print("ℹ Enrichissement détaillé désactivé (--no-detail)")

    # ── Fusion + tri ──────────────────────────────────────────────────────────
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
    print(f"  dont {n_with_placements} avec placements détaillés")
    print("=" * 60)


if __name__ == "__main__":
    main()
