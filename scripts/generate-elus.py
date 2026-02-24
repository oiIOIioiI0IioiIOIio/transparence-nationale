#!/usr/bin/env python3
"""
Script de génération des données des élus français.
Sources:
  - HATVP open data XML (hatvp.fr/livraison/opendata/declarations.xml) → source primaire officielle
  - HATVP XML index (hatvp.fr/livraison/opendata/liste.xml)            → fallback léger
  - API HATVP fiche individuelle JSON                                   → enrichissement si besoin
  - API Assemblée Nationale (nosdeputes.fr / open data AN)             → id_an, circonscription

Génère: public/data/elus.json

NOTE :
  Le CSV open data HATVP est remplacé par l'export XML officiel, qui est
  la source canonique la plus complète (patrimoine, immobilier, placements).
  Aucune dépendance tierce n'est requise (xml.etree.ElementTree est stdlib).
"""

import argparse
import json
import os
import sys
import time
import unicodedata
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET

# Chemins relatifs depuis la racine du projet
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")

# ── Sources HATVP XML ────────────────────────────────────────────────────────
# Export XML complet HATVP (déclarations de patrimoine et d'intérêts)
HATVP_XML_FULL_URL = "https://www.hatvp.fr/livraison/opendata/declarations.xml"
# Index XML allégé (liste des déclarants) — fallback
HATVP_XML_LISTE_URL = "https://www.hatvp.fr/livraison/opendata/liste.xml"

# API HATVP fiche individuelle (enrichissement — tentée si hatvp_id connu)
HATVP_API_DECLARATION_VARIANTS = [
    "https://www.hatvp.fr/rest/api/declarations/{hatvp_id}",
    "https://www.hatvp.fr/livraison/opendata/declarations/{hatvp_id}.json",
]

# ── Sources Assemblée Nationale ──────────────────────────────────────────────
NOSDEPUTES_DEPUTES_URL = "https://www.nosdeputes.fr/deputes/json"
AN_OPENDATA_URL = "https://data.assemblee-nationale.fr/api/v2/deputes/json"

# Indemnités parlementaires de base (brut annuel)
INDEMNITE_DEPUTE = 85_296
INDEMNITE_SENATEUR = 87_480

HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (https://github.com/transparence-nationale)",
    "Accept": "application/xml, application/json, */*",
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

# Tags XML HATVP susceptibles de contenir des actifs financiers
PLACEMENT_XML_TAGS = {
    "valeursMobilieres", "assuranceVie", "epargne", "partsSociales",
    "instrumentsFinanciers", "actions", "obligations", "opcvm", "pea",
    "compteTitres", "autresBiensFinanciers", "autresBiensMobiliers",
}

# ══════════════════════════════════════════════════════════════════════════════
# Utilitaires
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Génère public/data/elus.json depuis HATVP (XML open data) + API AN."
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT,
        help=f"Chemin de sortie (défaut : {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limiter le nombre d'élus générés (utile pour les tests)",
    )
    parser.add_argument(
        "--no-detail", action="store_true",
        help="Ne pas appeler l'API HATVP individuelle (plus rapide, moins de données)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.3,
        help="Délai entre requêtes détaillées HATVP en secondes (défaut : 0.3)",
    )
    return parser.parse_args()


def slugify(text: str) -> str:
    """Convertir un nom en slug ASCII minuscule."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace(" ", "-").replace("'", "-").replace("\u2019", "-").replace('"', "-")
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
    return " ".join(name.split())


def http_get(url: str, timeout: int = 60) -> bytes | None:
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
    val = str(val).strip()
    for ch in ("\u202f", "\xa0", " ", ",", "€", "EUR"):
        val = val.replace(ch, "" if ch not in (",",) else ".")
    val = val.replace(",", ".")
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _xml_text(elem, *tags, default: str = "") -> str:
    """Chercher récursivement le texte d'un sous-élément parmi plusieurs tags."""
    for tag in tags:
        child = elem.find(".//" + tag)
        if child is not None and child.text and child.text.strip():
            return child.text.strip()
    return default


def _xml_int(elem, *tags) -> int:
    return parse_amount(_xml_text(elem, *tags))

# ══════════════════════════════════════════════════════════════════════════════
# Récupération HATVP — XML open data (source primaire)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_xml(url: str, label: str) -> ET.Element | None:
    """Télécharger et parser un fichier XML depuis une URL."""
    print(f"🔄 Téléchargement XML HATVP ({label})…")
    raw = http_get(url, timeout=120)
    if not raw:
        print(f"  ✗ Impossible de télécharger : {url}")
        return None
    try:
        root = ET.fromstring(raw)
        print(f"  ✓ XML parsé ({len(raw):,} octets) depuis {label}")
        return root
    except ET.ParseError as exc:
        print(f"  ✗ Erreur de parsing XML ({label}) : {exc}")
        return None


def fetch_hatvp_xml() -> ET.Element | None:
    """
    Récupérer le XML HATVP.
    Stratégie :
      1. Export complet declarations.xml (patrimoine + intérêts)
      2. Index liste.xml (fallback allégé)
    """
    root = fetch_xml(HATVP_XML_FULL_URL, "declarations.xml (complet)")
    if root is not None:
        return root
    root = fetch_xml(HATVP_XML_LISTE_URL, "liste.xml (fallback)")
    return root


def _extract_placements_from_xml(decl_elem: ET.Element) -> tuple[int, list[dict]]:
    """
    Extraire les placements financiers d'un élément XML de déclaration HATVP.
    Retourne (montant_total, liste_placements).
    """
    placements: list[dict] = []
    seen: set[tuple] = set()

    for tag, label in [
        ("valeursMobilieres",     "Valeurs mobilières"),
        ("assuranceVie",          "Assurance-vie"),
        ("epargne",               "Épargne"),
        ("partsSociales",         "Parts sociales"),
        ("instrumentsFinanciers", "Instruments financiers"),
        ("actions",               "Actions"),
        ("obligations",           "Obligations"),
        ("opcvm",                 "OPCVM / Fonds"),
        ("pea",                   "PEA"),
        ("compteTitres",          "Compte-titres"),
        ("autresBiensFinanciers", "Autres placements"),
        ("autresBiensMobiliers",  "Autres placements"),
    ]:
        for item in decl_elem.findall(f".//{tag}"):
            # Libellé
            libelle = (
                _xml_text(item, "denomination", "libelle", "societe", "emetteur",
                          "description", "objet", "nature")
                or label
            )
            # Montant
            montant = _xml_int(
                item, "valeurEstimee", "valeurVenale", "montant",
                "montantTotal", "valeur", "solde"
            )
            devise_el = item.find(".//devise")
            devise = (devise_el.text.strip().upper() if devise_el is not None and devise_el.text else "EUR")
            details_el = item.find(".//observations")
            details = (details_el.text.strip() if details_el is not None and details_el.text else "")

            dedup_key = (libelle.lower(), montant, label)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            placements.append({
                "type": label,
                "libelle": libelle,
                "montant": montant,
                "devise": devise,
                "details": details,
            })

    total = sum(p["montant"] for p in placements)
    return total, placements


def parse_hatvp_xml(root: ET.Element) -> list[dict]:
    """
    Convertir un arbre XML HATVP en liste de dicts bruts (un par déclarant).
    Supporte les deux formats courants :
      - <declarations><declaration>…</declaration></declarations>
      - <declarants><declarant>…</declarant></declarants>
    """
    # Chercher les éléments déclaration / declarant
    records: list[ET.Element] = (
        root.findall(".//declaration")
        or root.findall(".//declarant")
        or root.findall(".//Declarant")
        or list(root)  # dernier recours : enfants directs
    )

    print(f"  ✓ {len(records)} enregistrements trouvés dans le XML")

    results: list[dict] = []
    for rec in records:
        # ── Identité ───────────────────────────────────────────────────────���─
        nom = (
            _xml_text(rec, "nom", "lastName", "NOM", "nomUsuel")
        ).upper()
        prenom = (
            _xml_text(rec, "prenom", "prénom", "prenomUsuel", "firstName", "PRENOM")
        ).title()
        if not nom or not prenom:
            continue

        hatvp_id = _xml_text(rec, "id", "hatvpId", "identifiant", "declarantId", "uid")
        fonction_raw = _xml_text(
            rec, "fonction", "mandat", "qualite", "Fonction", "Mandat",
            "titreMandat", "libelleFonction"
        )
        parti = _xml_text(rec, "parti", "groupe", "formationPolitique", "groupePolitique")
        region = _xml_text(
            rec, "circonscription", "region", "departement",
            "libellCirconscription", "nomCirco"
        )

        # ── Patrimoine agrégé ────────────────────────────────────────────────
        patrimoine_total = _xml_int(
            rec, "totalPatrimoine", "patrimoineTotal", "montantTotal",
            "totalBiens", "valeurTotalePatrimoine"
        )
        immobilier_total = _xml_int(
            rec, "totalImmobilier", "bienImmobilierTotal",
            "valeurTotaleImmobilier", "totalBiensImmobiliers"
        )

        # Immobilier détaillé (somme des biens immobiliers listés)
        if not immobilier_total:
            immobilier_total = sum(
                _xml_int(b, "valeurVenale", "valeurEstimee", "montant", "valeur")
                for b in rec.findall(".//bienImmobilier")
            )

        # ── Placements ───────────────────────────────────────────────────────
        placements_total, placements_list = _extract_placements_from_xml(rec)

        results.append({
            "nom": nom,
            "prenom": prenom,
            "hatvp_id": hatvp_id,
            "fonction_raw": fonction_raw,
            "parti": parti,
            "region": region,
            "patrimoine_total": patrimoine_total,
            "immobilier_total": immobilier_total,
            "placements_total": placements_total,
            "placements_list": placements_list,
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Enrichissement individuel HATVP (JSON)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_hatvp_declaration_detail(hatvp_id: str) -> dict | None:
    """Récupérer la fiche complète d'un déclarant (JSON individuel)."""
    for url_tpl in HATVP_API_DECLARATION_VARIANTS:
        url = url_tpl.format(hatvp_id=hatvp_id)
        raw = http_get(url, timeout=30)
        if not raw:
            continue
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            continue
    return None


def _extract_placements_from_json(detail: dict) -> tuple[int, list[dict]]:
    """Extraire les placements d'une fiche JSON HATVP individuelle."""
    placements: list[dict] = []

    def _walk(node, depth=0):
        if depth > 20:
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
            devise = (node.get("devise", "EUR") or "EUR").upper()
            details = (node.get("details") or node.get("observations") or "").strip()

            is_placement = any(k in type_actif or type_actif in k for k in PLACEMENT_CATEGORIES)
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
                    "devise": devise,
                    "details": details,
                })

            for v in node.values():
                if isinstance(v, (dict, list)):
                    _walk(v, depth + 1)

    _walk(detail)

    seen: set[tuple] = set()
    unique: list[dict] = []
    for p in placements:
        key = (p["libelle"].lower(), p["montant"], p["type"])
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return sum(p["montant"] for p in unique), unique


# ══════════════════════════════════════════════════════════════════════════════
# Récupération Assemblée Nationale
# ══════════════════════════════════════════════════════════════════════════════

def fetch_an_deputes() -> dict[str, dict]:
    """Récupérer les députés depuis nosdeputes.fr avec fallback AN open data.
    Retourne un dict slug → {id_an, slug_an, region, groupe}."""
    print("🔄 Récupération des députés (nosdeputes.fr)…")
    deputes: dict[str, dict] = {}

    raw = http_get(NOSDEPUTES_DEPUTES_URL)
    if raw:
        try:
            result = json.loads(raw.decode("utf-8"))
            for item in result.get("deputes", []):
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
                    deputes[slugify(f"{prenom} {nom}")] = {
                        "id_an": id_an, "slug_an": slug_an,
                        "region": region, "groupe": groupe,
                    }
            print(f"  ✓ {len(deputes)} députés depuis nosdeputes.fr")
            return deputes
        except Exception as exc:
            print(f"  ⚠ Parsing nosdeputes.fr : {exc}")

    print("  ↩ Fallback : API open data Assemblée Nationale…")
    raw = http_get(AN_OPENDATA_URL)
    if not raw:
        print("  ⚠ API AN indisponible, enrichissement id_an ignoré")
        return deputes

    try:
        result = json.loads(raw.decode("utf-8"))
        for item in result.get("deputes", []):
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
                deputes[slugify(f"{prenom} {nom}")] = {
                    "id_an": id_an, "slug_an": "", "region": region, "groupe": "",
                }
        print(f"  ✓ {len(deputes)} députés depuis l'API AN (fallback)")
    except Exception as exc:
        print(f"  ⚠ Parsing API AN : {exc}")

    return deputes


# ═════════════════════���════════════════════════════════════════════════════════
# Conversion enregistrement HATVP → élu
# ══════════════════════════════════════════════════════════════════════════════

def hatvp_record_to_elu(record: dict, an_map: dict[str, dict]) -> dict | None:
    """Convertir un enregistrement HATVP parsé en structure élu."""
    nom = record["nom"]
    prenom = record["prenom"]
    hatvp_id = record.get("hatvp_id", "")
    fonction_raw = record.get("fonction_raw", "")
    parti = record.get("parti", "")

    elu_id = slugify(f"{prenom} {nom}")
    if not elu_id:
        return None

    an_info = an_map.get(elu_id, {})
    id_an = an_info.get("id_an", "")
    slug_an = an_info.get("slug_an", "")
    # Priorité région : XML HATVP > nosdeputes.fr
    region = record.get("region", "") or an_info.get("region", "")
    groupe = an_info.get("groupe", "")

    revenus = INDEMNITE_DEPUTE
    mandats: list[str] = []
    fonction = fonction_raw or "Élu(e)"
    fl = fonction_raw.lower()

    if "sénateur" in fl or "sénatrice" in fl:
        revenus = INDEMNITE_SENATEUR
        mandats = ["Sénateur(trice)"]
        if not fonction_raw:
            fonction = "Sénateur(trice)"
    elif "député" in fl or "députée" in fl:
        mandats = ["Député(e)"]
        if region and "de" not in fl:
            fonction = f"Député(e) de {region}"
    elif "ministre" in fl:
        mandats = [fonction_raw]
        revenus = 0
    else:
        mandats = [fonction_raw] if fonction_raw else ["Élu(e)"]

    hatvp_url = (
        f"https://www.hatvp.fr/fiche-nominative/?declarant="
        f"{urllib.parse.quote(f'{nom}-{prenom}')}"
    )
    an_url = ""
    if id_an:
        an_url = f"https://www.assemblee-nationale.fr/dyn/deputes/{id_an}"
    elif slug_an:
        an_url = f"https://www.nosdeputes.fr/{slug_an}"

    patrimoine = record.get("patrimoine_total", 0)
    immobilier = record.get("immobilier_total", 0)
    placements_montant = record.get("placements_total", 0)
    placements_list = record.get("placements_list", [])
    patrimoine_source = "hatvp_xml" if patrimoine else "non_disponible"

    # Patrimoine estimé si non fourni explicitement
    if not patrimoine and (immobilier or placements_montant):
        patrimoine = immobilier + placements_montant
        patrimoine_source = "hatvp_xml_partiel"

    return {
        "id": elu_id,
        "nom": nom,
        "prenom": prenom,
        "fonction": fonction,
        "region": region,
        "groupe": groupe,
        "revenus": revenus,
        "patrimoine": patrimoine,
        "immobilier": immobilier,
        "placements_montant": placements_montant,
        "placements": placements_list,
        "patrimoine_source": patrimoine_source,
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


def enrich_with_json_detail(elu: dict, delay: float) -> None:
    """Enrichir un élu avec les données JSON individuelles HATVP (modifie en place)."""
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
            else sum(
                parse_amount(b.get("valeurVenale") or b.get("valeur") or 0)
                for b in immo_raw
            )
        )

    total_place, placements_list = _extract_placements_from_json(detail)
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
    """Dédupliquer une liste d'élus (par hatvp_id puis par (nom, prénom))."""
    by_hatvp_id: dict[str, dict] = {}
    by_name: dict[tuple, dict] = {}
    result_order: list[str] = []

    def _merge_into(base: dict, other: dict) -> None:
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
            else:
                by_hatvp_id[hatvp_id] = elu
                result_order.append(("hatvp_id", hatvp_id))
        else:
            name_key = (nom_norm, prenom_norm)
            if name_key in by_name:
                _merge_into(by_name[name_key], elu)
            else:
                by_name[name_key] = elu
                result_order.append(("name", nom_norm, prenom_norm))

    final: list[dict] = []
    seen: set = set()
    for key in result_order:
        k = str(key)
        if k in seen:
            continue
        seen.add(k)
        if key[0] == "hatvp_id":
            elu = by_hatvp_id.get(key[1])
        else:
            elu = by_name.get((key[1], key[2]))
        if elu:
            final.append(elu)

    return final


def merge_with_existing(new_elus: list[dict], existing_elus: list[dict]) -> list[dict]:
    """Fusionner les nouveaux élus avec les existants."""
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


# ═════════════════════════════════���════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    print("=" * 60)
    print("🗳️  GÉNÉRATEUR DE DONNÉES ÉLUS FRANÇAIS")
    print("   Source HATVP : XML open data officiel (hatvp.fr/livraison)")
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

    # ��─ Récupération HATVP (XML open data) ───────────────────────────────────
    xml_root = fetch_hatvp_xml()
    if xml_root is None:
        print("✗ Aucune source HATVP XML disponible. Arrêt.")
        sys.exit(1)

    hatvp_records = parse_hatvp_xml(xml_root)
    if not hatvp_records:
        print("✗ Aucun enregistrement HATVP extrait du XML. Arrêt.")
        sys.exit(1)

    # ── Conversion en élus ────────────────────────────────────────────────────
    raw_elus: list[dict] = []
    for record in hatvp_records:
        elu = hatvp_record_to_elu(record, an_map)
        if elu:
            raw_elus.append(elu)

    print(f"✓ {len(raw_elus)} élus convertis depuis HATVP XML (avant déduplication)")

    # ── Déduplication ─────────────────────────────────────────────────────────
    new_elus = deduplicate_elus(raw_elus)
    print(f"✓ {len(new_elus)} élus uniques (après déduplication)")
    if len(raw_elus) - len(new_elus) > 0:
        print(f"  → {len(raw_elus) - len(new_elus)} doublon(s) supprimé(s)")

    # ── Enrichissement JSON individuel HATVP ──────────────────────────────────
    if not args.no_detail:
        elus_with_id = [e for e in new_elus if e.get("hatvp_id")]
        total_detail = len(elus_with_id) if not args.limit else min(args.limit, len(elus_with_id))
        print(f"\n🔍 Enrichissement JSON individuel pour {total_detail} élus…")
        for i, elu in enumerate(elus_with_id[:total_detail], 1):
            print(
                f"  [{i}/{total_detail}] {elu['prenom']} {elu['nom']} "
                f"(id={elu['hatvp_id']})",
                end="", flush=True,
            )
            enrich_with_json_detail(elu, args.delay)
            n_place = len(elu.get("placements", []))
            print(f" → {n_place} placement(s), patrimoine={elu['patrimoine']:,}€")
    else:
        print("ℹ Enrichissement JSON individuel désactivé (--no-detail)")

    # ── Fusion avec les existants + tri ──────────────────────────────────────
    merged = merge_with_existing(new_elus, existing_elus)
    merged.sort(key=lambda e: (e.get("nom", ""), e.get("prenom", "")))

    if args.limit:
        merged = merged[: args.limit]

    # ── Sauvegarde ───────────────────────────────────────────────────────────
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
