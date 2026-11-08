from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent

for source in ROOT.rglob("*"):
    if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        continue

    webp = source.with_suffix(".webp")
    if not webp.is_file():
        continue

    try:
        # Vérifie que le WebP est lisible et possède les mêmes dimensions.
        with Image.open(source) as original, Image.open(webp) as converted:
            converted.load()
            if original.size != converted.size:
                print(f"Ignoré (dimensions différentes) : {source}")
                continue

        source.unlink()
        print(f"Supprimé : {source}")

    except Exception as error:
        print(f"Conservé : {source} — {error}")