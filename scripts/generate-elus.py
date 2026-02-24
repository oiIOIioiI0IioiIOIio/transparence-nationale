#!/usr/bin/env python3
"""
Script de génération des données des élus français.
Sources: HATVP OpenData CSV, API Assemblée Nationale
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

# Chemins relatifs depuis la racine du projet (calculés à partir de __file__)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")

HATVP_CSV_URL = "https://www.hatvp.fr/livraison/opendata/liste.csv"
AN_API_BASE = "https://data.assemblee-nationale.fr/api/v2/"

# Indemnités parlementaires de base
INDEMNITE_DEPUTE = 85296
INDEMNITE_SENATEUR = 87480

HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (https://github.com/transparence-nationale)"
}


def parse_args():
    parser = argparse.ArgumentParser(description="Génère public/data/elus.json depuis HATVP + API AN.")
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
    return parser.parse_args()


def slugify(text):
    """Convertir un nom en slug ASCII minuscule."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace(" ", "-").replace("'", "-").replace("'", "-")
    # Supprimer les caractères non alphanumériques (sauf tiret)
    text = "".join(c for c in text if c.isalnum() or c == "-")
    # Fusionner les tirets multiples
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-")


def http_get(url, timeout=20):
    """Effectuer une requête GET et retourner le contenu brut, ou None."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as exc:
        print(f"  ⚠ HTTP {exc.code} pour {url}")
    except Exception as exc:
        print(f"  ⚠ Erreur réseau ({url}) : {exc}")
    return None


def fetch_hatvp_csv():
    """Télécharger et parser le CSV HATVP."""
    print(f"🔄 Téléchargement du CSV HATVP…")
    raw = http_get(HATVP_CSV_URL)
    if not raw:
        print("✗ Impossible de télécharger le CSV HATVP")
        return []

    # Le CSV peut être encodé en UTF-8 ou latin-1
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
    print(f"✓ {len(rows)} déclarants HATVP récupérés")
    return rows


def fetch_an_deputes():
    """Récupérer les députés depuis l'API open data de l'Assemblée Nationale."""
    print("🔄 Récupération des députés depuis l'API Assemblée Nationale…")
    deputes = {}
    url = f"{AN_API_BASE}deputes/json"
    data = http_get(url)
    if not data:
        print("  ⚠ API AN indisponible, enrichissement id_an ignoré")
        return deputes

    try:
        result = json.loads(data.decode("utf-8"))
        # Structure possible : {"deputes": [{"depute": {...}}, ...]}
        items = result.get("deputes", [])
        for item in items:
            dep = item.get("depute", item)
            prenom = dep.get("prenom", "") or dep.get("prenom_usuel", "")
            nom = dep.get("nom", "") or dep.get("nom_de_famille", "")
            uid = dep.get("uid", {})
            id_an = uid if isinstance(uid, str) else uid.get("#text", "")
            circ = dep.get("mandats", {})
            region = ""
            if isinstance(circ, dict):
                for mandat in circ.get("mandat", []):
                    if isinstance(mandat, dict) and mandat.get("typeOrgane") == "CIRCONSCRIPTION":
                        region = mandat.get("libelle", "")
                        break

            if prenom and nom:
                key = slugify(f"{prenom} {nom}")
                deputes[key] = {
                    "id_an": id_an,
                    "region": region,
                }
        print(f"✓ {len(deputes)} députés récupérés depuis l'API AN")
    except Exception as exc:
        print(f"  ⚠ Parsing API AN : {exc}")

    return deputes


def hatvp_row_to_elu(row, an_map):
    """Convertir une ligne CSV HATVP en structure élu."""
    # Les colonnes peuvent varier selon la version du CSV
    nom = (row.get("nom") or row.get("Nom") or "").strip()
    prenom = (row.get("prenom") or row.get("Prénom") or row.get("prenom_usuel") or "").strip()
    if not nom or not prenom:
        return None

    elu_id = slugify(f"{prenom} {nom}")
    key = elu_id  # même clé dans an_map

    an_info = an_map.get(key, {})
    id_an = an_info.get("id_an", "")
    region = an_info.get("region", "")

    # Fonctions / mandats
    fonction_raw = (
        row.get("fonction") or row.get("Fonction") or
        row.get("mandat") or row.get("Mandat") or ""
    ).strip()

    # Déterminer le type d'élu et le revenu
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
    else:
        mandats = [fonction_raw] if fonction_raw else ["Élu(e)"]

    # Données patrimoniales
    patrimoine = 0
    immobilier = 0
    placements = 0
    patrimoine_source = "non_disponible"

    def parse_amount(val):
        if not val:
            return 0
        val = val.strip().replace(" ", "").replace(",", ".").replace("€", "")
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    pat_val = (
        row.get("total_patrimoine") or row.get("patrimoine_total") or
        row.get("Patrimoine total") or row.get("montant_total") or ""
    )
    if pat_val:
        patrimoine = parse_amount(pat_val)
        patrimoine_source = "hatvp"

    immo_val = (
        row.get("total_immobilier") or row.get("immobilier") or
        row.get("Immobilier") or ""
    )
    if immo_val:
        immobilier = parse_amount(immo_val)

    place_val = (
        row.get("total_placements") or row.get("placements") or
        row.get("Placements") or ""
    )
    if place_val:
        placements = parse_amount(place_val)

    # Parti
    parti = (row.get("parti") or row.get("Parti") or row.get("groupe") or "").strip()

    # URL HATVP
    hatvp_url = f"https://www.hatvp.fr/fiche-nominative/?declarant={nom}-{prenom}"
    an_url = f"https://www.assemblee-nationale.fr/dyn/deputes/{id_an}" if id_an else ""

    elu = {
        "id": elu_id,
        "nom": nom,
        "prenom": prenom,
        "fonction": fonction,
        "region": region,
        "revenus": revenus,
        "patrimoine": patrimoine,
        "immobilier": immobilier,
        "placements": placements,
        "patrimoine_source": patrimoine_source,
        "mandats": mandats,
        "parti": parti,
        "photo": "/photos/placeholder.jpg",
        "liens": {
            "assemblee": an_url,
            "hatvp": hatvp_url,
            "wikipedia": "",
        },
    }

    if id_an:
        elu["id_an"] = id_an

    return elu


def merge_with_existing(new_elus, existing_elus):
    """
    Fusionner les nouveaux élus avec les existants.
    Les entrées existantes sont enrichies, pas écrasées.
    """
    existing_map = {e["id"]: e for e in existing_elus}

    for elu in new_elus:
        eid = elu["id"]
        if eid in existing_map:
            existing = existing_map[eid]
            # Enrichir les champs manquants ou vides
            for key, value in elu.items():
                if key not in existing or not existing[key]:
                    existing[key] = value
                elif key in ("liens",) and isinstance(value, dict):
                    for lk, lv in value.items():
                        if not existing[key].get(lk):
                            existing[key][lk] = lv
        else:
            existing_map[eid] = elu

    return list(existing_map.values())


def main():
    args = parse_args()

    print("=" * 60)
    print("🗳️  GÉNÉRATEUR DE DONNÉES ÉLUS FRANÇAIS")
    print("=" * 60)

    # Charger les données existantes
    existing_elus = []
    if os.path.exists(args.output):
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                existing_elus = json.load(f)
            print(f"✓ {len(existing_elus)} élus existants chargés depuis {args.output}")
        except Exception as exc:
            print(f"⚠ Impossible de charger {args.output} : {exc}")

    # Récupérer les données
    hatvp_rows = fetch_hatvp_csv()
    time.sleep(0.2)
    an_map = fetch_an_deputes()

    # Convertir les lignes HATVP en élus
    new_elus = []
    seen_ids = set()
    for row in hatvp_rows:
        elu = hatvp_row_to_elu(row, an_map)
        if elu and elu["id"] not in seen_ids:
            seen_ids.add(elu["id"])
            new_elus.append(elu)

    print(f"✓ {len(new_elus)} élus convertis depuis HATVP")

    # Fusionner avec les données existantes
    merged = merge_with_existing(new_elus, existing_elus)

    # Trier par nom
    merged.sort(key=lambda e: (e.get("nom", ""), e.get("prenom", "")))

    # Appliquer la limite si demandée
    if args.limit:
        merged = merged[: args.limit]

    # S'assurer que le répertoire de sortie existe
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # Sauvegarder
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✓ {len(merged)} élus générés → {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
