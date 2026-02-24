#!/usr/bin/env python3
"""
Script de téléchargement des photos d'élus français.
Sources officielles (par ordre de priorité) :
  1. Assemblée Nationale  — photos officielles haute résolution
  2. Sénat                — photos officielles sénateurs
  3. HATVP                — photo de la fiche nominative (si disponible)
  4. Placeholder          — image générée localement (aucune source trouvée)

Génère: public/photos/*.jpg
Met à jour: public/data/elus.json (champ photo)

NOTE : Wikipedia a été retiré car ce n'est pas une source officielle.
"""

import argparse
import json
import os
import re
import time
import urllib.request
import urllib.parse
import urllib.error

# ── Chemins ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_PHOTOS_DIR = os.path.join(PROJECT_ROOT, "public", "photos")
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")

# ── URLs photos officielles ────────────────────────────────────────────────────

# Assemblée Nationale – deux variantes d'URL selon les mandatures
# Format carré 400×400, disponible pour tous les députés avec un id_an
AN_PHOTO_SQUARE = (
    "https://www2.assemblee-nationale.fr/static/tribun/{id_an}/photos/carre/{id_an}.jpg"
)
# Format portrait (ancienne mandature ou secours)
AN_PHOTO_PORTRAIT = (
    "https://www2.assemblee-nationale.fr/static/tribun/{id_an}/photos/{id_an}.jpg"
)
# Fallback endpoint /dyn/ (redirige parfois vers la même image)
AN_PHOTO_DYN = (
    "https://www.assemblee-nationale.fr/dyn/deputes/{id_an}/photo"
)

# Sénat – URL officielle des photos sénateurs
# L'id_senat est l'identifiant numérique senat (ex : "14285"), parfois présent dans les données HATVP
SENAT_PHOTO = "https://www.senat.fr/senimg/photos/pho{id_senat}.jpg"

# HATVP – les fiches nominatives exposent parfois une photo de profil
# URL à construire à partir du nom/prénom (non garanti)
HATVP_PHOTO = "https://www.hatvp.fr/fiche-nominative/photo/?declarant={nom}-{prenom}"

# ── Headers ────────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (https://github.com/transparence-nationale)",
    "Accept": "image/jpeg,image/png,image/*,*/*;q=0.8",
}

# Taille minimale d'une image valide (évite les images vides ou erreurs HTML)
MIN_IMAGE_SIZE = 2048  # 2 Ko


def parse_args():
    parser = argparse.ArgumentParser(
        description="Télécharge les photos officielles des élus français."
    )
    parser.add_argument("--dry-run", action="store_true", help="Tester sans télécharger")
    parser.add_argument("--force", action="store_true", help="Re-télécharger même si le fichier existe")
    parser.add_argument("--limit", type=int, default=None, help="Limiter le nombre de photos à traiter")
    parser.add_argument("--delay", type=float, default=0.4, help="Délai entre requêtes (défaut 0.4 s)")
    parser.add_argument(
        "--no-hatvp", action="store_true",
        help="Ne pas essayer la source HATVP (peu fiable pour les photos)"
    )
    return parser.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
# Utilitaires réseau & image
# ══════════════════════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 15) -> bytes | None:
    """Télécharger une URL et retourner le contenu binaire, ou None."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = resp.read()
                # Vérifier que ce n'est pas une réponse HTML déguisée en image
                if data[:3] in (b"\xff\xd8\xff", b"\x89PN", b"GIF") or data[:4] == b"\x89PNG":
                    return data
                if len(data) > MIN_IMAGE_SIZE and b"<html" not in data[:200].lower():
                    return data
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 403, 410):
            print(f"  ⚠ HTTP {exc.code} → {url}")
    except Exception as exc:
        print(f"  ⚠ Réseau : {exc}")
    return None


def is_valid_image(data: bytes) -> bool:
    """Vérifier que les données sont bien une image JPEG/PNG."""
    if len(data) < MIN_IMAGE_SIZE:
        return False
    # JPEG : magic bytes FF D8 FF
    if data[:3] == b"\xff\xd8\xff":
        return True
    # PNG : magic bytes 89 50 4E 47
    if data[:4] == b"\x89PNG":
        return True
    # GIF
    if data[:3] == b"GIF":
        return True
    return False


def resize_image(path: str) -> None:
    """Redimensionner l'image en 400×500 px (ratio couverture, centré)."""
    try:
        from PIL import Image

        img = Image.open(path).convert("RGB")
        target_w, target_h = 400, 500
        orig_w, orig_h = img.size
        ratio = max(target_w / orig_w, target_h / orig_h)
        new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        img = img.crop((left, top, left + target_w, top + target_h))
        img.save(path, "JPEG", quality=88, optimize=True)
    except ImportError:
        pass  # Pillow non installé : on garde l'image brute
    except Exception as exc:
        print(f"  ⚠ Redimensionnement : {exc}")


def save_image(data: bytes, dest_path: str, dry_run: bool) -> bool:
    """Sauvegarder les données image si valides."""
    if not is_valid_image(data):
        return False
    if dry_run:
        return True
    with open(dest_path, "wb") as f:
        f.write(data)
    resize_image(dest_path)
    return True


# ══════════════════════════════════════════════════════════════════════════════
# Placeholder
# ══════════════════════════════════════════════════════════════════════════════

def create_placeholder_image() -> str:
    """Créer une image placeholder (silhouette bleue institutionnelle)."""
    placeholder_path = os.path.join(OUTPUT_PHOTOS_DIR, "placeholder.jpg")
    if os.path.exists(placeholder_path):
        return placeholder_path
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (400, 500), color=(30, 58, 138))  # bleu foncé
        draw = ImageDraw.Draw(img)
        # Tête
        draw.ellipse([145, 70, 255, 180], fill=(200, 215, 245))
        # Corps
        draw.ellipse([80, 195, 320, 450], fill=(200, 215, 245))
        img.save(placeholder_path, "JPEG", quality=88)
        print("✓ Placeholder créé")
    except ImportError:
        print("⚠ Pillow non installé — placeholder non créé (pip install Pillow)")
    return placeholder_path


# ══════════════════════════════════════════════════════════════════════════════
# Sources officielles
# ══════════════════════════════════════════════════════════════════════════════

def try_assemblee_nationale(id_an: str, dest_path: str, dry_run: bool) -> bool:
    """
    Télécharger la photo depuis l'Assemblée Nationale.
    Essaie trois variantes d'URL dans l'ordre.
    """
    if not id_an:
        return False

    for url_tpl in (AN_PHOTO_SQUARE, AN_PHOTO_PORTRAIT, AN_PHOTO_DYN):
        url = url_tpl.format(id_an=id_an)
        if dry_run:
            print(f"  [dry-run] AN : {url}")
            return True
        data = http_get(url)
        if data and save_image(data, dest_path, dry_run=False):
            return True

    return False


def try_senat(id_senat: str, dest_path: str, dry_run: bool) -> bool:
    """
    Télécharger la photo depuis le portail du Sénat.
    L'id_senat doit être fourni (ex : "14285").
    """
    if not id_senat:
        return False

    url = SENAT_PHOTO.format(id_senat=id_senat)
    if dry_run:
        print(f"  [dry-run] Sénat : {url}")
        return True

    data = http_get(url)
    if data and save_image(data, dest_path, dry_run=False):
        return True
    return False


def try_hatvp_photo(nom: str, prenom: str, dest_path: str, dry_run: bool) -> bool:
    """
    Tenter de récupérer la photo depuis la fiche HATVP.
    Cette source est peu fiable (pas toujours de photo) mais officielle.
    """
    if not nom or not prenom:
        return False

    nom_enc = urllib.parse.quote(nom, safe="")
    prenom_enc = urllib.parse.quote(prenom, safe="")
    url = HATVP_PHOTO.format(nom=nom_enc, prenom=prenom_enc)

    if dry_run:
        print(f"  [dry-run] HATVP : {url}")
        return True

    data = http_get(url)
    if data and save_image(data, dest_path, dry_run=False):
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Orchestration par élu
# ══════════════════════════════════════════════════════════════════════════════

def download_photo_for_elu(elu: dict, force: bool, dry_run: bool, no_hatvp: bool, delay: float) -> bool | None:
    """
    Télécharger la photo d'un élu en testant les sources officielles dans l'ordre.
    Retourne :
      True  → photo téléchargée avec succès
      None  → fichier déjà présent (skip)
      False → aucune photo trouvée (placeholder)
    """
    elu_id = elu.get("id", "")
    id_an = elu.get("id_an") or elu.get("liens", {}).get("assemblee", "").split("/")[-1]
    id_senat = elu.get("id_senat", "")
    nom = elu.get("nom", "")
    prenom = elu.get("prenom", "")
    mandats = elu.get("mandats", [])
    dest_path = os.path.join(OUTPUT_PHOTOS_DIR, f"{elu_id}.jpg")

    # id_an depuis l'URL assemblee si absent du champ direct
    if not id_an:
        lien_an = elu.get("liens", {}).get("assemblee", "")
        m = re.search(r"/deputes?/([A-Z0-9]+)", lien_an, re.IGNORECASE)
        if m:
            id_an = m.group(1)

    if not force and os.path.exists(dest_path):
        print(f"  ⏭ Déjà présente : {elu_id}.jpg")
        return None

    is_senateur = any(
        "sénat" in str(m).lower() or "sénateur" in str(m).lower()
        for m in mandats
    )

    # ── Source 1 : Assemblée Nationale ────────────────────────────────────────
    if id_an and not is_senateur:
        print(f"  🔄 Assemblée Nationale (id={id_an})…")
        time.sleep(delay)
        if try_assemblee_nationale(id_an, dest_path, dry_run):
            print(f"  ✓ Photo AN → {elu_id}.jpg")
            return True

    # ── Source 2 : Sénat ──────────────────────────────────────────────────────
    if is_senateur or id_senat:
        print(f"  🔄 Sénat (id={id_senat or '?'})…")
        time.sleep(delay)
        if try_senat(id_senat, dest_path, dry_run):
            print(f"  ✓ Photo Sénat → {elu_id}.jpg")
            return True

    # ── Source 3 : HATVP ��─────────────────────────────────────────────────────
    if not no_hatvp:
        print(f"  🔄 HATVP ({prenom} {nom})…")
        time.sleep(delay)
        if try_hatvp_photo(nom, prenom, dest_path, dry_run):
            print(f"  ✓ Photo HATVP → {elu_id}.jpg")
            return True

    # ── Source 4 : Assemblée Nationale même pour les autres mandats ───────────
    # (ministres, secrétaires d'État qui ont un id_an)
    if id_an and is_senateur:
        print(f"  🔄 AN fallback (id={id_an})…")
        time.sleep(delay)
        if try_assemblee_nationale(id_an, dest_path, dry_run):
            print(f"  ✓ Photo AN (fallback) → {elu_id}.jpg")
            return True

    print(f"  ✗ Aucune photo officielle trouvée → placeholder")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# I/O JSON
# ══════════════════════════════════════════════════════════════════════════════

def load_elus() -> list[dict]:
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def save_elus(elus: list[dict]) -> None:
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(elus, f, ensure_ascii=False, indent=2)
    print(f"✓ {OUTPUT_JSON} mis à jour")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    print("=" * 60)
    print("📸 SCRAPER DE PHOTOS OFFICIELLES D'ÉLUS FRANÇAIS")
    print("   Sources : Assemblée Nationale · Sénat · HATVP")
    if args.dry_run:
        print("   ⚠ MODE DRY-RUN — aucun fichier ne sera écrit")
    print("=" * 60)

    os.makedirs(OUTPUT_PHOTOS_DIR, exist_ok=True)
    print(f"✓ Dossier photos : {OUTPUT_PHOTOS_DIR}")
    create_placeholder_image()

    elus = load_elus()
    if args.limit:
        elus = elus[: args.limit]

    total = len(elus)
    downloaded = 0
    skipped = 0
    failed = 0
    updated: dict[str, str] = {}  # id → chemin photo

    for i, elu in enumerate(elus, 1):
        elu_id = elu.get("id", f"elu-{i}")
        print(f"\n[{i}/{total}] {elu.get('prenom', '')} {elu.get('nom', '')} ({elu_id})")

        result = download_photo_for_elu(
            elu,
            force=args.force,
            dry_run=args.dry_run,
            no_hatvp=args.no_hatvp,
            delay=args.delay,
        )

        if result is True:
            downloaded += 1
            photo_path = f"/photos/{elu_id}.jpg"
            updated[elu_id] = photo_path
            if not args.dry_run:
                elu["photo"] = photo_path
        elif result is None:
            skipped += 1
            # Mettre à jour le champ photo si le fichier existe mais le champ est vide
            dest = os.path.join(OUTPUT_PHOTOS_DIR, f"{elu_id}.jpg")
            if os.path.exists(dest) and not elu.get("photo", "").endswith(f"{elu_id}.jpg"):
                updated[elu_id] = f"/photos/{elu_id}.jpg"
        else:
            failed += 1
            if not args.dry_run and not elu.get("photo"):
                elu["photo"] = "/photos/placeholder.jpg"

    # ── Mettre à jour le JSON complet ─────────────────────────────────────────
    if not args.dry_run and updated:
        all_elus = load_elus()
        for e in all_elus:
            if e["id"] in updated:
                e["photo"] = updated[e["id"]]
        save_elus(all_elus)

    print("\n" + "=" * 60)
    print("📊 RAPPORT FINAL")
    print("=" * 60)
    print(f"  Total traités      : {total}")
    print(f"  ✓ Téléchargées     : {downloaded}")
    print(f"  ⏭ Déjà présentes   : {skipped}")
    print(f"  ✗ Non trouvées     : {failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
