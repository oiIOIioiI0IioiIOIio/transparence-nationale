#!/usr/bin/env python3
"""
Script de téléchargement des photos d'élus français.
Sources: API Assemblée Nationale, Wikipedia
Génère: public/photos/*.jpg
Met à jour: public/data/elus.json (champ photo)
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

# Chemins relatifs depuis la racine du projet (calculés à partir de __file__)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_PHOTOS_DIR = os.path.join(PROJECT_ROOT, "public", "photos")
OUTPUT_JSON = os.path.join(PROJECT_ROOT, "public", "data", "elus.json")

AN_PHOTO_URL = "https://www.assemblee-nationale.fr/dyn/deputes/{id_an}/photo"
WIKIPEDIA_API = "https://fr.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "TransparenceNationale/1.0 (https://github.com/transparence-nationale)"
}


def parse_args():
    parser = argparse.ArgumentParser(description="Télécharge les photos des élus français.")
    parser.add_argument("--dry-run", action="store_true", help="Tester sans télécharger")
    parser.add_argument("--force", action="store_true", help="Re-télécharger même si le fichier existe")
    parser.add_argument("--limit", type=int, default=None, help="Limiter le nombre de photos à télécharger")
    return parser.parse_args()


def create_directories():
    os.makedirs(OUTPUT_PHOTOS_DIR, exist_ok=True)
    print(f"✓ Dossier photos : {OUTPUT_PHOTOS_DIR}")


def create_placeholder_image():
    """Créer une belle image placeholder bleue avec une silhouette blanche."""
    placeholder_path = os.path.join(OUTPUT_PHOTOS_DIR, "placeholder.jpg")
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (400, 500), color=(37, 99, 235))
        draw = ImageDraw.Draw(img)

        # Silhouette : tête
        draw.ellipse([150, 80, 250, 180], fill=(255, 255, 255))
        # Silhouette : corps
        draw.ellipse([100, 190, 300, 420], fill=(255, 255, 255))

        img.save(placeholder_path, "JPEG", quality=85)
        print("✓ Image placeholder créée")
    except ImportError:
        print("⚠ Pillow non installé — placeholder JPEG non créé (pip install Pillow)")
    return placeholder_path


def resize_image(path):
    """Redimensionner l'image en 400x500px (conserver ratio, rogner/rembourrer)."""
    try:
        from PIL import Image

        img = Image.open(path).convert("RGB")
        target_w, target_h = 400, 500
        orig_w, orig_h = img.size

        # Calculer le ratio pour couvrir la cible
        ratio = max(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Rogner au centre
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        img = img.crop((left, top, left + target_w, top + target_h))

        img.save(path, "JPEG", quality=85)
    except Exception as exc:
        print(f"  ⚠ Redimensionnement échoué : {exc}")


def http_get(url, timeout=10):
    """Effectuer une requête GET et retourner le contenu binaire, ou None."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (404, 403):
            print(f"  ⚠ HTTP {exc.code} pour {url}")
    except Exception as exc:
        print(f"  ⚠ Erreur réseau : {exc}")
    return None


def try_download_an(id_an, dest_path, dry_run):
    """Tenter le téléchargement depuis l'Assemblée Nationale."""
    url = AN_PHOTO_URL.format(id_an=id_an)
    if dry_run:
        print(f"  [dry-run] AN : {url}")
        return True
    data = http_get(url)
    if data and len(data) > 1024:
        with open(dest_path, "wb") as f:
            f.write(data)
        resize_image(dest_path)
        return True
    return False


def try_download_wikipedia(nom, prenom, dest_path, dry_run):
    """Tenter le téléchargement via l'API Wikipedia (image principale)."""
    full_name = f"{prenom} {nom}"
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": full_name,
        "prop": "pageimages",
        "pithumbsize": 500,
        "format": "json",
    })
    url = f"{WIKIPEDIA_API}?{params}"
    time.sleep(0.5)

    if dry_run:
        print(f"  [dry-run] Wikipedia : {full_name}")
        return True

    data = http_get(url)
    if not data:
        return False
    try:
        result = json.loads(data.decode("utf-8"))
        pages = result.get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail", {}).get("source")
            if thumb:
                img_data = http_get(thumb)
                if img_data and len(img_data) > 1024:
                    with open(dest_path, "wb") as f:
                        f.write(img_data)
                    resize_image(dest_path)
                    return True
    except Exception as exc:
        print(f"  ⚠ Parsing Wikipedia : {exc}")
    return False


def download_photo_for_elu(elu, force, dry_run):
    """
    Télécharger la photo d'un élu.
    Retourne True si une vraie photo a été obtenue, False sinon.
    """
    elu_id = elu.get("id", "")
    id_an = elu.get("id_an", "")
    nom = elu.get("nom", "")
    prenom = elu.get("prenom", "")
    dest_path = os.path.join(OUTPUT_PHOTOS_DIR, f"{elu_id}.jpg")

    if not force and os.path.exists(dest_path):
        print(f"  ⏭ Déjà présente : {elu_id}.jpg")
        return None  # fichier existant, pas de changement

    # Source 1 : Assemblée Nationale
    if id_an:
        print(f"  🔄 AN ({id_an}) …")
        if try_download_an(id_an, dest_path, dry_run):
            print(f"  ✓ Photo AN : {elu_id}.jpg")
            return True

    # Source 2 : Wikipedia
    if nom and prenom:
        print(f"  🔄 Wikipedia ({prenom} {nom}) …")
        if try_download_wikipedia(nom, prenom, dest_path, dry_run):
            print(f"  ✓ Photo Wikipedia : {elu_id}.jpg")
            return True

    # Source 3 : placeholder
    print(f"  ✗ Pas de photo trouvée → placeholder")
    return False


def load_elus():
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def save_elus(elus):
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(elus, f, ensure_ascii=False, indent=2)
    print(f"✓ {OUTPUT_JSON} mis à jour")


def main():
    args = parse_args()

    print("=" * 60)
    print("📸 SCRAPER DE PHOTOS D'ÉLUS FRANÇAIS")
    if args.dry_run:
        print("   ⚠ MODE DRY-RUN — aucun fichier ne sera écrit")
    print("=" * 60)

    create_directories()
    create_placeholder_image()

    elus = load_elus()
    if args.limit:
        elus = elus[: args.limit]

    total = len(elus)
    downloaded = 0
    skipped = 0
    failed = 0
    updated_ids = []

    for i, elu in enumerate(elus, 1):
        elu_id = elu.get("id", f"elu-{i}")
        print(f"\n[{i}/{total}] {elu.get('prenom', '')} {elu.get('nom', '')} ({elu_id})")

        result = download_photo_for_elu(elu, args.force, args.dry_run)

        if result is True:
            downloaded += 1
            updated_ids.append(elu_id)
            if not args.dry_run:
                elu["photo"] = f"/photos/{elu_id}.jpg"
        elif result is None:
            skipped += 1
        else:
            failed += 1
            if not args.dry_run:
                elu["photo"] = "/photos/placeholder.jpg"

        time.sleep(0.2)

    # Sauvegarder le JSON avec les champs photo mis à jour
    if not args.dry_run and updated_ids:
        # Recharger le JSON complet et mettre à jour uniquement les élus traités
        all_elus = load_elus()
        id_to_photo = {e["id"]: e.get("photo") for e in elus if e.get("photo")}
        for e in all_elus:
            if e["id"] in id_to_photo:
                e["photo"] = id_to_photo[e["id"]]
        save_elus(all_elus)

    print("\n" + "=" * 60)
    print("📊 RAPPORT FINAL")
    print("=" * 60)
    print(f"  Total élus traités : {total}")
    print(f"  ✓ Photos téléchargées : {downloaded}")
    print(f"  ⏭ Fichiers déjà présents : {skipped}")
    print(f"  ✗ Pas de photo (placeholder) : {failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
