from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
EXTENSIONS = {".png", ".jpg", ".jpeg"}

converted = skipped = errors = 0

for source in ROOT.rglob("*"):
    if not source.is_file() or source.suffix.lower() not in EXTENSIONS:
        continue

    destination = source.with_suffix(".webp")

    if destination.exists():
        print(f"Déjà présent : {destination.relative_to(ROOT)}")
        skipped += 1
        continue

    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)

            has_alpha = (
                "A" in image.getbands()
                or "transparency" in image.info
            )
            image = image.convert("RGBA" if has_alpha else "RGB")

            image.save(
                destination,
                "WEBP",
                quality=85,
                method=6,
            )

        print(f"Converti : {source.relative_to(ROOT)}")
        converted += 1

    except Exception as error:
        print(f"Erreur : {source.relative_to(ROOT)} — {error}")
        errors += 1

print(
    f"\nTerminé : {converted} converties, "
    f"{skipped} ignorées, {errors} erreurs."
)